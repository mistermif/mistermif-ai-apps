from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager, suppress

import httpx
import uvicorn
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .agent import KnausAgent
from .alerts import public_alert_catalog
from .config import Settings
from .home_assistant import HomeAssistantClient
from .learning import ContextLearner
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
    settings.ai_api_key,
    settings.model,
    memory,
    policy,
    settings.privacy_mode,
    settings.ai_provider,
    settings.ai_base_url,
)
workspace = WorkspaceManager(settings.homeassistant_config_dir)
learner = ContextLearner(memory)


async def learning_loop() -> None:
    while True:
        try:
            learner.observe(await ha.states())
        except Exception:
            logger.exception("Campionamento locale non riuscito")
        await asyncio.sleep(300)


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info(
        "mistermif AI avviato: modalità=%s, provider=%s, modello=%s",
        settings.autonomy_mode,
        settings.ai_provider,
        settings.model,
    )
    if settings.workspace_enabled:
        workspace.bootstrap()
    learning_task = asyncio.create_task(learning_loop())
    yield
    learning_task.cancel()
    with suppress(asyncio.CancelledError):
        await learning_task


app = FastAPI(title="mistermif AI", version="0.4.0", lifespan=lifespan)


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


class CrewMember(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    role: str = Field(default="equipaggio", min_length=1, max_length=80)


class OnboardingRequest(BaseModel):
    vehicle_type: str = Field(pattern="^(caravan|camper)$")
    brand: str = Field(min_length=1, max_length=100)
    model: str = Field(min_length=1, max_length=120)
    year: int | None = Field(default=None, ge=1950, le=2100)
    tow_vehicle: str | None = Field(default=None, max_length=160)
    crew: list[CrewMember] = Field(default_factory=list, max_length=20)


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
    learning = learner.summary()
    return {
        "version": "0.4.0",
        "model": settings.model,
        "ai_provider": settings.ai_provider,
        "ai_configured": bool(settings.ai_api_key)
        if settings.ai_provider != "local"
        else True,
        "privacy_mode": settings.privacy_mode,
        "permissions": policy.public_summary(),
        "autonomy_enabled": autonomy_enabled(),
        "home_assistant": await ha.health(),
        "workspace": workspace.summary() if settings.workspace_enabled else None,
        "onboarding": {
            "completed": memory.get_setting("onboarding_completed", "false")
            == "true"
        },
        "alert_levels": public_alert_catalog(),
        "learning": {
            "site_key": learning.site_key,
            "samples": learning.samples,
            "confidence": learning.confidence,
            "learned_sites": learning.learned_sites,
        },
    }


@app.get("/api/learning")
async def learning_status() -> dict:
    summary = learner.summary()
    return {
        "site_key": summary.site_key,
        "samples": summary.samples,
        "confidence": summary.confidence,
        "learned_sites": summary.learned_sites,
        "averages": summary.averages,
        "local_only": True,
        "self_modifying": False,
    }


@app.get("/api/context")
async def context() -> dict:
    return {"entities": await ha.states()}


@app.get("/api/alerts")
async def alert_catalog() -> dict:
    return {"levels": public_alert_catalog()}


@app.get("/api/onboarding")
async def onboarding_status() -> dict:
    profile = memory.get_json_setting("vehicle_profile")
    return {
        "completed": memory.get_setting("onboarding_completed", "false") == "true",
        "profile": profile,
    }


@app.post("/api/onboarding")
async def save_onboarding(payload: OnboardingRequest) -> dict:
    profile = payload.model_dump()
    if payload.vehicle_type == "caravan" and not (payload.tow_vehicle or "").strip():
        raise HTTPException(
            status_code=422,
            detail="Per una caravan indica la motrice utilizzata",
        )
    memory.set_json_setting("vehicle_profile", profile)
    memory.set_setting("onboarding_completed", "true")
    memory.add_memory(
        "shared",
        "profilo_mezzo",
        f"{payload.brand} {payload.model}",
        (
            f"Tipo: {payload.vehicle_type}; anno: {payload.year or 'non indicato'}; "
            f"motrice: {payload.tow_vehicle or 'non applicabile'}"
        ),
        {"source": "onboarding"},
    )
    for member in payload.crew:
        memory.add_memory(
            "shared",
            "persona",
            member.name,
            f"Ruolo nell'equipaggio: {member.role}",
            {"source": "onboarding"},
        )
    logger.info(
        "Intervista iniziale completata per mezzo tipo=%s, membri=%d",
        payload.vehicle_type,
        len(payload.crew),
    )
    return {"completed": True}


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
