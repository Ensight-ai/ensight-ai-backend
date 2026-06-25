from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.agents.router import router as agents_router
from app.analytics.router import router as analytics_router
from app.auth.router import router as auth_router
from app.chat.router import router as chat_router
from app.chat.ws import ws_router
from app.content.router import router as content_router
from app.conversations.router import router as conversations_router
from app.exports.router import router as exports_router
from app.leads.router import router as leads_router
from app.sessions.router import router as sessions_router

app = FastAPI(title="ensight-backend")

# The chat widget is embedded on third-party websites, so it calls the API
# from many origins. Auth is via bearer tokens (not cookies), so a permissive
# origin policy is safe here. Tighten allow_origins if you ever use cookies.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(agents_router)
app.include_router(sessions_router)
app.include_router(chat_router)
app.include_router(analytics_router)
app.include_router(conversations_router)
app.include_router(exports_router)
app.include_router(leads_router)
app.include_router(content_router)
app.include_router(ws_router)

# Serve the realtime test client at /demo (separate top-level webclient/ module).
_webclient_dir = Path(__file__).resolve().parent.parent / "webclient"
if _webclient_dir.is_dir():
    app.mount(
        "/demo", StaticFiles(directory=_webclient_dir, html=True), name="demo"
    )


@app.get("/")
async def root():
    return {"message": "Hello from ensight-backend!"}


@app.get("/health")
async def health():
    return {"status": "ok"}
