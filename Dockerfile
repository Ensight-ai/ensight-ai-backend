# syntax=docker/dockerfile:1
FROM python:3.12-slim

# uv — fast, reproducible Python installs
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies first (cached until pyproject/uv.lock change).
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy the application source.
COPY . .

# Run the app straight from the venv.
ENV PATH="/app/.venv/bin:$PATH"

# Expose the port the app runs on and we should use 8001 for the RAG API and 8000 for the main API. The RAG API is used for the RAG engine and the main API is used for the main application. 
EXPOSE 8001
# One worker keeps memory sane (each loads its own RAG/voice engines). Scale
# with compose replicas or bump --workers if the box has RAM to spare.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
