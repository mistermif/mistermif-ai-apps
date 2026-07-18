from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

import httpx
import uvicorn
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .agent import KnausAgent
from .config import Settings
from .home_assistant import HomeAssistantClient
from .memory import MemoryStore
from .permissions import PermissionPolicy
from .workspace import WorkspaceError, WorkspaceManager


settings = Settings.load()
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("mistermif-ai")

memory = MemoryStore(settings.data_dir / "knaus_copilot.sqlite3")
policy = PermissionPolicy(settings.autonomy_mode, settings.climate_entity)
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
workspace = WorkspaceManager(settings.homeassistant_config_dir)


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info(
        "mistermif AI avviato: modalità=%s, modello=%s",
        settings.autonomy_mode,
        settings.model,
    )
    if settings.workspace_enabled:
        workspace.bootstrap()
    yield


app = FastAPI(title="mistermif AI", version="0.3.1", lifespan=lifespan)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


class MemoryRequest(BaseModel):
    category: str = Field(min_length=1, max_length=50)
    title: str = Field(min_length=1, max_length=160)
    content: str = Field(min_length=1, max_length=8000)
    shared: bool = False


class ActionRequest(BaseModel):
    name: str
    confirmed: bool = False


class WorkspaceInstallRequest(BaseModel):
    confirmed: bool = False


class AutonomyRequest(BaseModel):
    enabled: bool
    confirmed: bool = False


class NotificationRequest(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    message: str = Field(min_length=1, max_length=2000)


def autonomy_enabled() -> bool:
    return memory.get_setting("autonomy_enabled", "false") == "true"


def require_autonomy() -> None:
    if not autonomy_enabled():
        raise HTTPException(
            status_code=423,
            detail="Autonomia AI disattivata dall'interruttore generale",
        )


def user_identity(
    user_id: str | None,
    user_name: str | None,
) -> tuple[str, str]:
    return (user_id or "local-user", user_name or "Utente")


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(os.path.join(os.path.dirname(__file__), "static", "index.html"))


@app.get("/caravan-eyes.png")
async def caravan_icon() -> FileResponse:
    return FileResponse(
        os.path.join(os.path.dirname(__file__), "static", "caravan-eyes.png")
    )


@app.get("/api/status")
async def status() -> dict:
    return {
        "version": "0.3.1",
        "model": settings.model,
        "openai_configured": bool(settings.openai_api_key),
        "permissions": policy.public_summary(),
        "autonomy_enabled": autonomy_enabled(),
        "home_assistant": await ha.health(),
        "workspace": workspace.summary() if settings.workspace_enabled else None,
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
    normalized = payload.message.casefold()
    requests_climate_off = (
        ("spegni" in normalized or "disattiva" in normalized)
        and ("clima" in normalized or "climatizzatore" in normalized)
    )
    if requests_climate_off and policy.can_execute("turn_off_climate"):
        require_autonomy()
        if policy.autonomy_mode == "confirm":
            return {
                "answer": (
                    "Posso spegnere il climatizzatore autorizzato. "
                    "Premi Conferma per eseguire il comando."
                ),
                "user": display_name,
                "pending_action": {
                    "name": "turn_off_climate",
                    "label": "Conferma spegnimento clima",
                },
            }
        try:
            action_result = await ha.turn_off_climate()
        except (PermissionError, RuntimeError, httpx.HTTPError) as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        return {
            "answer": "Ho spento il climatizzatore autorizzato.",
            "user": display_name,
            "action_result": action_result,
        }
    try:
        answer = await agent.chat(user_id, payload.message, await ha.states())
    except Exception as exc:
        logger.exception("Errore durante la conversazione")
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"answer": answer, "user": display_name}


@app.post("/api/actions/execute")
async def execute_action(payload: ActionRequest) -> dict:
    require_autonomy()
    if payload.name != "turn_off_climate":
        raise HTTPException(status_code=403, detail="Azione non autorizzata")
    if policy.autonomy_mode != "confirm" or not payload.confirmed:
        raise HTTPException(status_code=403, detail="Conferma esplicita richiesta")
    try:
        return await ha.turn_off_climate()
    except (PermissionError, RuntimeError, httpx.HTTPError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/autonomy")
async def set_autonomy(payload: AutonomyRequest) -> dict:
    if payload.enabled and not payload.confirmed:
        raise HTTPException(
            status_code=403,
            detail="Conferma esplicita richiesta per riattivare l'autonomia",
        )
    memory.set_setting("autonomy_enabled", "true" if payload.enabled else "false")
    logger.warning(
        "Interruttore autonomia AI impostato su %s",
        "ATTIVO" if payload.enabled else "BLOCCATO",
    )
    return {"enabled": payload.enabled}


@app.post("/api/notifications")
async def send_notification(payload: NotificationRequest) -> dict:
    try:
        return await ha.send_notification(
            settings.notification_service,
            payload.title,
            payload.message,
        )
    except (PermissionError, RuntimeError, httpx.HTTPError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/workspace/install")
async def install_workspace(payload: WorkspaceInstallRequest) -> dict:
    if not settings.workspace_enabled:
        raise HTTPException(status_code=403, detail="Workspace disabilitato")
    if not payload.confirmed:
        raise HTTPException(status_code=403, detail="Conferma esplicita richiesta")
    try:
        workspace.bootstrap()
        return workspace.install_include()
    except WorkspaceError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=os.getenv("KNAUS_HOST", "0.0.0.0"),
        port=int(os.getenv("KNAUS_PORT", "8099")),
        proxy_headers=True,
        forwarded_allow_ips="*",
    )
