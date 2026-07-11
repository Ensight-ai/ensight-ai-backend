# EnsightLabs — Backend

FastAPI backend for EnsightLabs: custom AI chat/voice agents (Gemini + RAG),
lead qualification, content generation, meeting booking, financial-access
assessment, subscriptions (Paystack), and transactional email (ZeptoMail).

**Stack:** FastAPI · Supabase (Auth + Postgres) · Google Vertex AI (Gemini) ·
Chroma (local vector store) · Paystack · ZeptoMail · Google Calendar.

---

## Prerequisites

- **Python 3.12** (see `.python-version`)
- **[uv](https://docs.astral.sh/uv/)** for dependency management & running
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```
- **[gcloud CLI](https://cloud.google.com/sdk/docs/install)** (for Vertex AI auth)
- A **Supabase** project and a **Google Cloud** project with Vertex AI enabled

---

## Setup

### 1. Install dependencies
```bash
cd ensight-backend
uv sync
```

### 2. Configure environment
Copy the example and fill in your values:
```bash
cp .env.example .env
```
Key variables (see `.env.example` for the full list):

| Group | Variables |
|-------|-----------|
| Google Cloud / Vertex AI | `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION`, `LLM_MODEL` |
| Supabase | `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, `SUPABASE_SECRET_KEY`, `DATABASE_URL` |
| Sessions | `SESSION_SECRET` (use `openssl rand -hex 32`) |
| Google Calendar (OAuth) | `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, `GOOGLE_OAUTH_REDIRECT_URI` |
| Frontend | `FRONTEND_URL` |
| Billing (Paystack) | `PAYSTACK_SECRET_KEY`, plan codes/amounts |
| Email (ZeptoMail) | `ZEPTO_TOKEN`, `ZEPTO_API_URL`, `MAIL_FROM_EMAIL` |
| Admin | `ADMIN_EMAILS` (comma-separated) |

### 3. Authenticate to Google Cloud (Vertex AI + Speech)
Use Application Default Credentials — no key file needed:
```bash
gcloud auth application-default login
gcloud auth application-default set-quota-project <GOOGLE_CLOUD_PROJECT>
```
Leave `GOOGLE_APPLICATION_CREDENTIALS` **unset** in `.env` to use ADC.
(Only set it if you have a service-account JSON key.) Your account/service
account needs the **Vertex AI User** role, with the **Vertex AI**,
**Speech-to-Text**, and **Text-to-Speech** APIs enabled.

### 4. Run database migrations
Applies the SQL files in `supabase/migrations/` (needs `DATABASE_URL`):
```bash
uv run migrate.py                 # apply any new migrations
uv run migrate.py new <name>      # scaffold a new migration file
```

---

## Running the app

```bash
uv run fastapi dev app/main.py
```
Serves at **http://localhost:8000** with auto-reload.

Alternatives (all on port 8000):
```bash
uv run main.py                                   # repo entrypoint
uv run uvicorn app.main:app --reload --port 8000
```

### Verify it's up
```bash
curl http://localhost:8000/health      # -> {"status":"ok"}
```
Interactive API docs: **http://localhost:8000/docs**

---

## Notes

- **Vector store:** agent document embeddings are stored locally in
  `chroma_db/` — back this up / mount a volume in production.
- **Webhooks (local):** Paystack can't reach `localhost`. For local billing
  tests, expose the server with a tunnel (e.g. `ngrok http 8000`) and set that
  URL as the Paystack webhook (`…/billing/webhook`).
- **Production:** set `FRONTEND_URL`, `GOOGLE_OAUTH_REDIRECT_URI`, and Paystack
  webhook to your live domains, and use a strong `SESSION_SECRET`.
