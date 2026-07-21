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
from .automation_lab import (
    evaluate_snapshot,
    public_scenarios,
    run_scenario,
    snapshot_from_home_assistant,
)
from .config import Settings
from .conversational_simulator import run_conversational_simulation
from .cloud_usage import CloudUsage
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
policy = PermissionPolicy(
    settings.autonomy_mode,
    settings.climate_entity,
    runtime_enabled=memory.get_setting("autonomy_enabled", "false") == "true",
)
ha = HomeAssistantClient(
    settings.ha_base_url,
    settings.supervisor_token,
    policy,
    settings.max_context_entities,
)
cloud_usage = CloudUsage(
    memory,
    settings.cloud_daily_limit,
    settings.cloud_automatic_limit,
)
agent = KnausAgent(
    settings.ai_api_key,
    settings.model,
    memory,
    policy,
    settings.privacy_mode,
    settings.ai_provider,
    settings.ai_base_url,
    cloud_usage,
    settings.gemini_search_enabled,
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


APP_VERSION = "0.7.1"


app = FastAPI(title="mistermif AI", version=APP_VERSION, lifespan=lifespan)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    web_search: bool = False
    automatic: bool = False


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


class LabRunRequest(BaseModel):
    scenario: str = Field(min_length=1, max_length=80)


class LabModeRequest(BaseModel):
    mode: str = Field(pattern="^(simulation|shadow|active)$")
    confirmed: bool = False


class ArtifactRequest(BaseModel):
    kind: str = Field(
        pattern="^(dashboard|helper|fixed_automation|dynamic_automation|script|template)$"
    )
    name: str = Field(pattern="^[a-z0-9][a-z0-9_-]{1,63}$")
    content: str = Field(min_length=1, max_length=100_000)
    description: str = Field(default="", max_length=500)


class LabMappingRequest(BaseModel):
    entities: dict[str, str] = Field(default_factory=dict)
    available_amps: int = Field(default=6, ge=3, le=16)


class AutonomyRequest(BaseModel):
    enabled: bool
    confirmed: bool = False


class AnimalsRequest(BaseModel):
    enabled: bool


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


def animals_on_board() -> bool:
    return memory.get_setting("animals_on_board", "false") == "true"


def require_autonomy() -> None:
    if not autonomy_enabled():
        raise HTTPException(
            status_code=423,
            detail="Autonomia AI disattivata dall'interruttore generale",
        )


def lab_mode() -> str:
    mode = memory.get_setting("lab_mode", "simulation") or "simulation"
    return mode if mode in {"simulation", "shadow", "active"} else "simulation"


LAB_MAPPING_KEYS = {
    "battery_soc",
    "battery_current",
    "battery_trend",
    "grid_power",
    "external_power",
    "solar_power",
    "available_amps",
    "climate",
    "external_charge",
    "animals_on_board",
    "external_socket_parallel",
}
LAB_REQUIRED_MAPPING_KEYS = {"battery_soc", "grid_power", "solar_power"}


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
        "version": APP_VERSION,
        "model": settings.model,
        "ai_provider": settings.ai_provider,
        "ai_configured": bool(settings.ai_api_key)
        if settings.ai_provider != "local"
        else True,
        "privacy_mode": settings.privacy_mode,
        "cloud_usage": cloud_usage.snapshot(),
        "gemini_search_enabled": settings.gemini_search_enabled,
        "permissions": policy.public_summary(),
        "autonomy_enabled": autonomy_enabled(),
        "animals_on_board": animals_on_board(),
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
        "lab": {
            "mode": lab_mode(),
            "bundle_installed": (
                workspace.safe_path("laboratorio/energy_safety_lab.json").exists()
                if settings.workspace_enabled and workspace.root.exists()
                else False
            ),
            "active_ready": False,
            "real_actions_during_simulation": False,
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
    simulation = run_conversational_simulation(
        payload.message,
        animals_default=animals_on_board(),
    )
    if simulation is not None:
        memory.add_message(user_id, "user", payload.message)
        memory.add_message(user_id, "assistant", simulation["answer"])
        try:
            if simulation["kind"] == "single":
                workspace.record_lab_result(simulation["result"])
            elif simulation["kind"] == "full":
                for item in simulation["items"]:
                    workspace.record_lab_result(item["result"])
        except WorkspaceError:
            logger.exception("Registrazione della simulazione conversazionale non riuscita")
        return {
            "answer": simulation["answer"],
            "user": display_name,
            "simulation": {
                key: value
                for key, value in simulation.items()
                if key != "answer"
            },
        }
    requests_climate_off = (
        ("spegni" in normalized or "disattiva" in normalized)
        and ("clima" in normalized or "climatizzatore" in normalized)
    )
    if requests_climate_off and animals_on_board():
        return {
            "answer": (
                "Non spengo il climatizzatore mentre Animali a bordo è attivo. "
                "Prima verifica personalmente la situazione e disattiva quella "
                "modalità con il pulsante dedicato."
            ),
            "user": display_name,
        }
    if requests_climate_off:
        if not policy.can_execute("turn_off_climate"):
            return {
                "answer": (
                    "Il potere decisionale è bloccato. Attivalo con il pulsante "
                    "dedicato se vuoi consentirmi di comandare il climatizzatore."
                ),
                "user": display_name,
            }
        require_autonomy()
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
        search_terms = (
            "cerca",
            "ristorant",
            "campegg",
            "meteo",
            "prevision",
            "allerta",
            "ricambio",
            "notizie",
            "google",
        )
        web_search = payload.web_search or any(
            term in normalized for term in search_terms
        )
        answer = await agent.chat(
            user_id,
            payload.message,
            await ha.states(),
            automatic=payload.automatic,
            web_search=web_search,
            runtime_context={"animals_on_board": animals_on_board()},
        )
    except Exception as exc:
        logger.exception("Errore durante la conversazione")
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"answer": answer, "user": display_name}


@app.post("/api/actions/execute")
async def execute_action(payload: ActionRequest) -> dict:
    require_autonomy()
    if payload.name == "turn_off_climate" and animals_on_board():
        raise HTTPException(
            status_code=423,
            detail="Climatizzatore protetto: animali a bordo",
        )
    if payload.name != "turn_off_climate":
        raise HTTPException(status_code=403, detail="Azione non autorizzata")
    if not payload.confirmed:
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
    policy.runtime_enabled = payload.enabled
    logger.warning(
        "Interruttore autonomia AI impostato su %s",
        "ATTIVO" if payload.enabled else "BLOCCATO",
    )
    return {"enabled": payload.enabled}


@app.post("/api/animals")
async def set_animals(payload: AnimalsRequest) -> dict:
    memory.set_setting("animals_on_board", "true" if payload.enabled else "false")
    logger.warning(
        "Modalità animali a bordo impostata su %s",
        "ATTIVA" if payload.enabled else "DISATTIVA",
    )
    return {
        "enabled": payload.enabled,
        "climate_protected": payload.enabled,
        "message": (
            "Animali a bordo attivo: il clima diventa prioritario."
            if payload.enabled
            else "Animali a bordo disattivato."
        ),
    }


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


@app.get("/api/workspace/artifacts")
async def list_workspace_artifacts() -> dict:
    if not settings.workspace_enabled:
        raise HTTPException(status_code=403, detail="Workspace disabilitato")
    return {
        "items": workspace.list_artifacts(),
        "creation_scope": "/config/mistermif_ai",
        "drafts_are_active": False,
    }


@app.post("/api/workspace/artifacts")
async def create_workspace_artifact(payload: ArtifactRequest) -> dict:
    if not settings.workspace_enabled:
        raise HTTPException(status_code=403, detail="Workspace disabilitato")
    try:
        return workspace.create_artifact(
            payload.kind,
            payload.name,
            payload.content,
            payload.description,
        )
    except WorkspaceError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/api/lab")
async def lab_status() -> dict:
    bundle_path = workspace.safe_path("laboratorio/energy_safety_lab.json")
    mapping = memory.get_json_setting("energy_lab_mapping") or {}
    mapped_entities = mapping.get("entities", {})
    return {
        "mode": lab_mode(),
        "scenarios": public_scenarios(),
        "bundle_installed": bundle_path.exists(),
        "mapping_configured": LAB_REQUIRED_MAPPING_KEYS.issubset(mapped_entities),
        "mapping": mapping,
        "active_ready": False,
        "active_block_reason": (
            "Prima occorre associare e convalidare i sensori reali in modalità ombra."
        ),
        "safety": {
            "simulation_calls_real_services": False,
            "simulation_changes_battery": False,
            "simulation_changes_inverter": False,
            "workspace_only_generation": True,
        },
    }


@app.get("/api/lab/entities")
async def lab_entities() -> dict:
    states = await ha.states()
    return {
        "items": states,
        "mapping": memory.get_json_setting("energy_lab_mapping"),
        "required_keys": sorted(LAB_REQUIRED_MAPPING_KEYS),
        "optional_keys": sorted(LAB_MAPPING_KEYS - LAB_REQUIRED_MAPPING_KEYS),
    }


@app.post("/api/lab/mapping")
async def save_lab_mapping(payload: LabMappingRequest) -> dict:
    unknown_keys = set(payload.entities) - LAB_MAPPING_KEYS
    if unknown_keys:
        raise HTTPException(
            status_code=422,
            detail=f"Chiavi mapping non riconosciute: {', '.join(sorted(unknown_keys))}",
        )
    invalid_entities = [
        entity_id
        for entity_id in payload.entities.values()
        if not policy.can_read(entity_id)
    ]
    if invalid_entities:
        raise HTTPException(
            status_code=403,
            detail=(
                "Entità fuori dal perimetro di lettura: "
                + ", ".join(sorted(invalid_entities))
            ),
        )
    mapping = {
        "entities": payload.entities,
        "available_amps": payload.available_amps,
    }
    memory.set_json_setting("energy_lab_mapping", mapping)
    return {
        "saved": True,
        "mapping": mapping,
        "ready_for_shadow": LAB_REQUIRED_MAPPING_KEYS.issubset(payload.entities),
        "ready_for_active": False,
    }


@app.post("/api/lab/install")
async def install_lab() -> dict:
    if not settings.workspace_enabled:
        raise HTTPException(status_code=403, detail="Workspace disabilitato")
    try:
        result = workspace.create_energy_lab_bundle()
    except WorkspaceError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        **result,
        "message": (
            "Laboratorio creato nella cartella dedicata. I suoi helper sono "
            "virtuali e non comandano apparati reali."
        ),
    }


@app.post("/api/lab/run")
async def execute_lab_scenario(payload: LabRunRequest) -> dict:
    try:
        result = run_scenario(payload.scenario)
        workspace.record_lab_result(result)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except WorkspaceError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return result


@app.post("/api/lab/shadow/run")
async def execute_lab_shadow() -> dict:
    mapping = memory.get_json_setting("energy_lab_mapping") or {}
    entities = mapping.get("entities", {})
    if not LAB_REQUIRED_MAPPING_KEYS.issubset(entities):
        raise HTTPException(
            status_code=409,
            detail=(
                "Associa prima almeno SOC batteria, potenza rete e potenza solare."
            ),
        )
    snapshot = snapshot_from_home_assistant(
        await ha.states(),
        entities,
        default_available_amps=int(mapping.get("available_amps", 6)),
    )
    result = evaluate_snapshot(snapshot, source="shadow")
    workspace.record_lab_result(result)
    return result


@app.post("/api/lab/mode")
async def set_lab_mode(payload: LabModeRequest) -> dict:
    if payload.mode == "active":
        require_autonomy()
        if not payload.confirmed:
            raise HTTPException(
                status_code=403,
                detail="Conferma esplicita richiesta per la modalità attiva",
            )
        raise HTTPException(
            status_code=409,
            detail=(
                "Modalità attiva non ancora pronta: associazione sensori e "
                "collaudo ombra sono obbligatori."
            ),
        )
    memory.set_setting("lab_mode", payload.mode)
    return {
        "mode": payload.mode,
        "real_actions_enabled": False,
        "message": (
            "La modalità simulazione usa solo dati virtuali."
            if payload.mode == "simulation"
            else "La modalità ombra osserva, registra e non esegue comandi."
        ),
    }


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=os.getenv("KNAUS_HOST", "0.0.0.0"),
        port=int(os.getenv("KNAUS_PORT", "8099")),
        proxy_headers=True,
        forwarded_allow_ips="*",
    )
