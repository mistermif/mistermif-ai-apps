from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .agent import KnausAgent
from .config import Settings
from .home_assistant import HomeAssistantClient
from .memory import MemoryStore
from .permissions import PermissionPolicy


settings = Settings.load()
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("mistermif-ai")

memory = MemoryStore(settings.data_dir / "knaus_copilot.sqlite3")
policy = PermissionPolicy(settings.autonomy_mode)
ha = HomeAssistantClient(
    settings.ha_base_url,
    settings.supervisor_token,
    policy,
    settings.max_context_entities,
)
agent = KnausAgent(
    settings.openai_api_key,
    settings.model,
    memory,
    policy,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info(
        "mistermif AI avviato: modalità=%s, modello=%s",
        settings.autonomy_mode,
        settings.model,
    )
    yield


app = FastAPI(title="mistermif AI", version="0.1.1", lifespan=lifespan)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


class MemoryRequest(BaseModel):
    category: str = Field(min_length=1, max_length=50)
    title: str = Field(min_length=1, max_length=160)
    content: str = Field(min_length=1, max_length=8000)
    shared: bool = False


def user_identity(
    user_id: str | None,
    user_name: str | None,
) -> tuple[str, str]:
    return (user_id or "local-user", user_name or "Utente")


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(os.path.join(os.path.dirname(__file__), "static", "index.html"))


@app.get("/api/status")
async def status() -> dict:
    return {
        "version": "0.1.1",
        "model": settings.model,
        "openai_configured": bool(settings.openai_api_key),
        "permissions": policy.public_summary(),
        "home_assistant": await ha.health(),
    }


@app.get("/api/context")
async def context() -> dict:
    return {"entities": await ha.states()}


@app.get("/api/memories")
async def get_memories(
    x_remote_user_id: str | None = Header(default=None),
) -> dict:
    user_id, _ = user_identity(x_remote_user_id, None)
    return {"items": memory.list_memories(user_id)}


@app.post("/api/memories")
async def create_memory(
    payload: MemoryRequest,
    x_remote_user_id: str | None = Header(default=None),
) -> dict:
    user_id, _ = user_identity(x_remote_user_id, None)
    owner = "shared" if payload.shared else user_id
    memory_id = memory.add_memory(
        owner,
        payload.category,
        payload.title,
        payload.content,
    )
    return {"id": memory_id}


@app.post("/api/chat")
async def chat(
    payload: ChatRequest,
    request: Request,
    x_remote_user_id: str | None = Header(default=None),
    x_remote_user_display_name: str | None = Header(default=None),
) -> dict:
    user_id, display_name = user_identity(
        x_remote_user_id, x_remote_user_display_name
    )
    try:
        answer = await agent.chat(user_id, payload.message, await ha.states())
    except Exception as exc:
        logger.exception("Errore durante la conversazione")
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"answer": answer, "user": display_name}


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=os.getenv("KNAUS_HOST", "0.0.0.0"),
        port=int(os.getenv("KNAUS_PORT", "8099")),
        proxy_headers=True,
        forwarded_allow_ips="*",
    )
