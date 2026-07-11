"""Modular RAG engine, powered by Google Cloud Vertex AI.

Wraps document ingestion, vector storage and a conversational
retrieval chain behind a small class so it can be driven from a route
(or any caller) instead of running as a script on import.

Stack: Gemini chat model + Vertex AI embeddings (both via Vertex AI) with
a local Chroma vector store, wired together with LangChain.

Auth: Vertex AI uses Application Default Credentials. Set up with either
``gcloud auth application-default login`` (local dev) or a service-account
key referenced by ``GOOGLE_APPLICATION_CREDENTIALS``. The GCP project and
region are read from ``GOOGLE_CLOUD_PROJECT`` / ``GOOGLE_CLOUD_LOCATION``.
"""

import os
from typing import Iterable

from dotenv import load_dotenv

from langchain_community.document_loaders import (
    Docx2txtLoader,
    PyPDFLoader,
    TextLoader,
)
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_google_vertexai import ChatVertexAI, VertexAIEmbeddings
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_classic.chains.retrieval import create_retrieval_chain

load_dotenv()


class RagEngine:
    """A reusable RAG pipeline backed by Vertex AI.

    Construct once (sets up the Vertex AI clients + opens the vector store),
    then call :meth:`ingest_file` to add documents and :meth:`chat` /
    :meth:`query` to ask questions.
    """

    # Map a file extension to the loader that knows how to read it.
    _LOADERS = {
        ".pdf": PyPDFLoader,
        ".docx": Docx2txtLoader,
        ".txt": TextLoader,
    }

    def __init__(
        self,
        *,
        persist_directory: str = "./chroma_db",
        collection_name: str = "my_collection",
        embedding_model: str = "text-embedding-004",
        llm_model: str | None = None,
        project: str | None = None,
        location: str | None = None,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        retrieval_k: int = 4,
    ) -> None:
        # Fall back to the standard Google Cloud environment variables.
        project = project or os.getenv("GOOGLE_CLOUD_PROJECT")
        location = location or os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
        # Which Gemini model to use. Override with LLM_MODEL; the model must be
        # available in your project + region (newer projects may only have the
        # latest, e.g. gemini-2.5-flash).
        llm_model = llm_model or os.getenv("LLM_MODEL", "gemini-2.5-flash")

        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        # Embeddings served by Vertex AI (e.g. "text-embedding-004").
        self.embedding_func = VertexAIEmbeddings(
            model_name=embedding_model,
            project=project,
            location=location,
        )

        # Open (or create) a persistent collection. Unlike Chroma.from_documents
        # this does not require any documents up front, so the store survives
        # across requests and we add to it as files are ingested.
        self.vector_store = Chroma(
            collection_name=collection_name,
            embedding_function=self.embedding_func,
            persist_directory=persist_directory,
        )
        self.retrieval_k = retrieval_k
        # Gemini chat model on Vertex AI (e.g. "gemini-2.0-flash",
        # "gemini-1.5-pro").
        # thinking_budget=0 turns OFF Gemini 2.5's internal "thinking" tokens.
        # For grounded RAG answers that reasoning adds latency with little gain,
        # so disabling it makes replies noticeably faster (and avoids the
        # thinking-block output format entirely).
        self.llm = ChatVertexAI(
            model=llm_model,
            project=project,
            location=location,
            temperature=0,
            thinking_budget=0,
        )
        # The answer-generation chain doesn't depend on the per-request filter,
        # so build it once. The retriever (and therefore the full chain) is
        # assembled per query so it can be scoped to a specific user + agent.
        self._question_answer_chain = create_stuff_documents_chain(
            llm=self.llm,
            prompt=self._make_qa_prompt(),
            output_parser=StrOutputParser(),
        )

    # ------------------------------------------------------------------
    # Ingestion
    # ------------------------------------------------------------------
    def _load_documents(self, file_path: str):
        ext = os.path.splitext(file_path)[1].lower()
        loader_cls = self._LOADERS.get(ext)
        if loader_cls is None:
            supported = ", ".join(sorted(self._LOADERS))
            raise ValueError(
                f"Unsupported file type {ext!r}. Supported types: {supported}"
            )
        return loader_cls(file_path).load()

    def ingest_file(self, file_path: str, *, user_id: str, agent_id: str) -> int:
        """Load, split and index a single file. Returns the chunk count.

        ``file_path`` is whatever a route hands us — e.g. the path of an
        uploaded file written to a temp location. Every resulting chunk is
        tagged with ``user_id`` and ``agent_id`` in its metadata so retrieval
        can be scoped to that owner later.
        """
        documents = self._load_documents(file_path)
        splits = self.text_splitter.split_documents(documents)
        for split in splits:
            split.metadata["user_id"] = user_id
            split.metadata["agent_id"] = agent_id
        if splits:
            self.vector_store.add_documents(splits)
        return len(splits)

    def ingest_files(
        self, file_paths: Iterable[str], *, user_id: str, agent_id: str
    ) -> int:
        """Ingest several files; returns the total chunk count added."""
        return sum(
            self.ingest_file(path, user_id=user_id, agent_id=agent_id)
            for path in file_paths
        )

    # ------------------------------------------------------------------
    # Querying
    # ------------------------------------------------------------------
    @staticmethod
    def _make_qa_prompt() -> ChatPromptTemplate:
        return ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are the official AI assistant for this business, "
                    "speaking directly with its customers on its behalf. You "
                    "represent the business and own the conversation.\n\n"
                    "Always speak in the first person as the business: use "
                    '"we", "us", and "our" (e.g. "We\'re located at...", '
                    '"You can reach us at..."). NEVER refer to the business in '
                    'the third person (never "they", "them", or talk about the '
                    "company as an outsider), and never reveal that you are a "
                    "third-party tool or AI platform — to the customer, you are "
                    "the business.\n\n"
                    "Use the following context — the business's own "
                    "information — to answer the customer's question. Ground "
                    "your answer in the context; if it doesn't contain the "
                    "answer, say so honestly and point the customer to how they "
                    "can reach us. Be warm, helpful, and concise, and answer "
                    "without markdown formatting.\n\n"
                    "Always write your entire answer in {language}.\n\n"
                    "Context: {context}",
                ),
                MessagesPlaceholder("chat_history"),
                ("human", "{input}"),
            ]
        )

    def _filtered_retriever(self, user_id: str, agent_id: str):
        """A retriever scoped to a single user + agent via metadata filtering.

        Chroma requires ``$and`` to combine more than one equality condition.
        """
        return self.vector_store.as_retriever(
            search_kwargs={
                "k": self.retrieval_k,
                "filter": {
                    "$and": [
                        {"user_id": user_id},
                        {"agent_id": agent_id},
                    ]
                },
            }
        )

    def _chain_for(self, user_id: str, agent_id: str):
        """Assemble the full RAG chain scoped to one user + agent.

        We retrieve directly on the raw question rather than first asking the
        LLM to rewrite it into a standalone query. That "history-aware" rewrite
        cost a whole extra LLM round trip on every follow-up message; the answer
        step still receives the full chat history, so multi-turn answers stay
        coherent while responses come back roughly twice as fast on follow-ups.
        """
        return create_retrieval_chain(
            self._filtered_retriever(user_id, agent_id),
            self._question_answer_chain,
        )

    @staticmethod
    def _to_messages(chat_history) -> list[BaseMessage]:
        """Convert route-friendly history into LangChain messages.

        Accepts a list of ``{"role": "user"|"assistant", "content": ...}``
        dicts (what a JSON request body naturally carries) or pre-built
        LangChain messages, which are passed through untouched.
        """
        messages: list[BaseMessage] = []
        for turn in chat_history or []:
            if isinstance(turn, BaseMessage):
                messages.append(turn)
                continue
            role = turn.get("role")
            content = turn.get("content", "")
            if role in ("user", "human"):
                messages.append(HumanMessage(content=content))
            elif role in ("assistant", "ai"):
                messages.append(AIMessage(content=content))
        return messages

    def chat(
        self,
        question: str,
        *,
        user_id: str,
        agent_id: str,
        chat_history=None,
        language: str | None = None,
    ) -> str:
        """Answer ``question`` using only this user + agent's documents.

        Retrieval is filtered to chunks tagged with ``user_id`` and
        ``agent_id``, so conversations never leak across owners. ``language``
        is the language to answer in (e.g. "Spanish"); when omitted, the agent
        mirrors the language the user wrote in.
        """
        chain = self._chain_for(user_id, agent_id)
        result = chain.invoke(
            {
                "input": question,
                "chat_history": self._to_messages(chat_history),
                "language": language or "the same language the user is using",
            }
        )
        return result["answer"]

    async def astream_chat(
        self,
        question: str,
        *,
        user_id: str,
        agent_id: str,
        chat_history=None,
        language: str | None = None,
    ):
        """Stream the answer as it is generated, yielding text deltas.

        Same scoping as :meth:`chat`; used by the realtime WebSocket routes.
        """
        chain = self._chain_for(user_id, agent_id)
        async for chunk in chain.astream(
            {
                "input": question,
                "chat_history": self._to_messages(chat_history),
                "language": language or "the same language the user is using",
            }
        ):
            # The retrieval chain emits dicts; answer text arrives under "answer".
            token = chunk.get("answer") if isinstance(chunk, dict) else None
            if token:
                yield token

    def query(
        self,
        question: str,
        *,
        user_id: str,
        agent_id: str,
        language: str | None = None,
    ) -> str:
        """One-shot question with no conversation history."""
        return self.chat(
            question,
            user_id=user_id,
            agent_id=agent_id,
            chat_history=None,
            language=language,
        )

    # Persona shared with the retrieval chain, reused for the tool-calling path.
    _TOOL_SYSTEM_PROMPT = (
        "You are the official AI assistant for this business, speaking directly "
        "with its customers on its behalf. Speak in the first person as the "
        'business ("we", "us", "our") and never reveal you are a third-party '
        "tool.\n\n"
        "Answer questions using the business context below; if it doesn't "
        "contain the answer, say so honestly. Always write in {language}.\n\n"
        "You can also book meetings. When a visitor wants to meet or talk to a "
        "person:\n"
        "1. Collect their full name and email address (and phone if they offer "
        "it). You need at least a name and email to book.\n"
        "2. Call check_availability to get real open times, then SUGGEST a few "
        "specific options to the visitor. Never invent times.\n"
        "3. When they choose one, call book_meeting with their details and the "
        "exact start_time string from check_availability.\n"
        "4. Confirm the booking in plain language and share the Google Meet "
        "link the tool returns. Never claim a meeting is booked unless "
        "book_meeting succeeded.\n\n"
        "Context: {context}"
    )

    def chat_with_tools(
        self,
        question: str,
        *,
        user_id: str,
        agent_id: str,
        tools: list,
        chat_history=None,
        language: str | None = None,
        max_iterations: int = 5,
    ) -> str:
        """Answer like :meth:`chat`, but the model can call ``tools``.

        Runs a bounded tool-calling loop: the model may call a tool (e.g. check
        availability, book a meeting), we run it, feed the result back, and let
        the model continue until it produces a final text answer. ``tools`` are
        LangChain tools supplied by the caller, so this engine stays decoupled
        from the booking/app layer.
        """
        context = self.retrieve_context(
            question, user_id=user_id, agent_id=agent_id
        )
        system = self._TOOL_SYSTEM_PROMPT.format(
            language=language or "the same language the user is using",
            context=context,
        )
        messages: list[BaseMessage] = [SystemMessage(content=system)]
        messages.extend(self._to_messages(chat_history))
        messages.append(HumanMessage(content=question))

        llm_with_tools = self.llm.bind_tools(tools)
        tools_by_name = {t.name: t for t in tools}

        for _ in range(max_iterations):
            response = llm_with_tools.invoke(messages)
            messages.append(response)
            tool_calls = getattr(response, "tool_calls", None)
            if not tool_calls:
                return self._extract_text(response.content)

            for call in tool_calls:
                tool = tools_by_name.get(call["name"])
                if tool is None:
                    output = f"Unknown tool: {call['name']}"
                else:
                    try:
                        output = tool.invoke(call["args"])
                    except Exception as exc:  # surface to the model, don't crash
                        output = f"Tool error: {exc}"
                messages.append(
                    ToolMessage(content=str(output), tool_call_id=call["id"])
                )

        # Ran out of iterations — make one final call without tools for a reply.
        final = self.llm.invoke(messages)
        return self._extract_text(final.content)

    @staticmethod
    def _extract_text(content) -> str:
        """Flatten a LangChain message's content into plain text.

        Gemini 2.5 (a thinking model) returns content as a list of blocks like
        ``[{"type": "text", "text": "...", "thought_signature": "..."}]`` rather
        than a string. Concatenate the visible text blocks and drop reasoning/
        thought blocks so the user never sees the raw structure.
        """
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for block in content:
                if isinstance(block, str):
                    parts.append(block)
                elif isinstance(block, dict):
                    # Keep plain text blocks; skip 'thinking'/reasoning ones.
                    if block.get("type") in (None, "text") and block.get("text"):
                        parts.append(block["text"])
            return "".join(parts).strip()
        return str(content)

    def retrieve_context(
        self, query: str, *, user_id: str, agent_id: str
    ) -> str:
        """Return the business's relevant document text for ``query``.

        Scoped to one user + agent (same metadata filter as chat retrieval).
        Used to *ground* content generation so drafts stay grounded in the
        business's own documents rather than the model's general knowledge.
        Returns an empty string if the agent has no matching documents.
        """
        docs = self._filtered_retriever(user_id, agent_id).invoke(query)
        return "\n\n".join(doc.page_content for doc in docs)


# A lazily-created shared instance so routes reuse one engine (the Vertex AI
# clients and vector store are expensive to set up per request).
_engine: RagEngine | None = None


def get_engine() -> RagEngine:
    global _engine
    if _engine is None:
        _engine = RagEngine()
    return _engine
