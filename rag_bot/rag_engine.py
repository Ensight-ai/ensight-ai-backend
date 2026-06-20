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
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_classic.chains.history_aware_retriever import (
    create_history_aware_retriever,
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
        llm_model: str = "gemini-2.0-flash",
        project: str | None = None,
        location: str | None = None,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        retrieval_k: int = 4,
    ) -> None:
        # Fall back to the standard Google Cloud environment variables.
        project = project or os.getenv("GOOGLE_CLOUD_PROJECT")
        location = location or os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")

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
        self.llm = ChatVertexAI(
            model=llm_model,
            project=project,
            location=location,
            temperature=0,
        )
        # The prompts and the answer-generation chain don't depend on the
        # per-request filter, so build them once. The retriever (and therefore
        # the full chain) is assembled per query so it can be scoped to a
        # specific user + agent.
        self._contextualize_q_prompt = self._make_contextualize_prompt()
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
    def _make_contextualize_prompt() -> ChatPromptTemplate:
        return ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "Given a chat history and the latest user question which "
                    "might reference context in the chat history, formulate a "
                    "standalone question which can be understood without the "
                    "chat history. Do NOT answer the question, just reformulate "
                    "it if needed and otherwise return it as is.",
                ),
                MessagesPlaceholder("chat_history"),
                ("human", "{input}"),
            ]
        )

    @staticmethod
    def _make_qa_prompt() -> ChatPromptTemplate:
        return ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are Ensight AI, an AI assistant that helps businesses "
                    "turn their knowledge, conversations, and content into "
                    "actionable insights. You support teams across customer "
                    "support, sales, content, and analytics with clear, "
                    "practical, business-focused guidance.\n\n"
                    "Use the following context to answer the user's question. "
                    "Ground your answer in the context; if the context does not "
                    "contain the answer, say so honestly rather than guessing. "
                    "Be concise, professional, and helpful, and answer without "
                    "markdown formatting.\n\n"
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
        """Assemble the full RAG chain scoped to one user + agent."""
        history_aware_retriever = create_history_aware_retriever(
            llm=self.llm,
            retriever=self._filtered_retriever(user_id, agent_id),
            prompt=self._contextualize_q_prompt,
        )
        return create_retrieval_chain(
            history_aware_retriever, self._question_answer_chain
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
        self, question: str, *, user_id: str, agent_id: str, chat_history=None
    ) -> str:
        """Answer ``question`` using only this user + agent's documents.

        Retrieval is filtered to chunks tagged with ``user_id`` and
        ``agent_id``, so conversations never leak across owners.
        """
        chain = self._chain_for(user_id, agent_id)
        result = chain.invoke(
            {"input": question, "chat_history": self._to_messages(chat_history)}
        )
        return result["answer"]

    def query(self, question: str, *, user_id: str, agent_id: str) -> str:
        """One-shot question with no conversation history."""
        return self.chat(
            question, user_id=user_id, agent_id=agent_id, chat_history=None
        )


# A lazily-created shared instance so routes reuse one engine (the Vertex AI
# clients and vector store are expensive to set up per request).
_engine: RagEngine | None = None


def get_engine() -> RagEngine:
    global _engine
    if _engine is None:
        _engine = RagEngine()
    return _engine
