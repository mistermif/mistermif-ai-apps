from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager, suppress

import httpx
import uvicorn
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel, Field

from .agent import KnausAgent, asks_for_location
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
from .codex_bridge import CollaborationService, create_bridge_app
from .home_assistant import HomeAssistantClient
from .fridge_optimizer import FridgeOptimizer
from .learning import ContextLearner
from .memory import MemoryStore
from .permissions import PermissionPolicy
from .travel import TravelTracker
from .weather_monitor import WeatherMonitor
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
weather_ai_usage = CloudUsage(
    memory,
    settings.weather_ai_daily_limit,
    settings.weather_ai_daily_limit,
    storage_key="weather_ai_usage",
)
workspace = WorkspaceManager(settings.homeassistant_config_dir)
learner = ContextLearner(memory)
weather_monitor = WeatherMonitor(
    memory,
    ha,
    settings.notification_service,
    settings.telegram_targets,
    settings.dpc_radar_enabled,
    settings.windy_api_key,
    (
        agent.evaluate_weather
        if settings.weather_ai_enabled and agent.can_evaluate_weather()
        else None
    ),
    weather_ai_usage if settings.weather_ai_enabled else None,
)
travel_tracker = TravelTracker(memory, settings.travel_arrival_minutes)
fridge_optimizer = FridgeOptimizer(memory, ha, policy, settings.notification_service)


async def learning_loop() -> None:
    while True:
        try:
            learner.observe(await ha.states())
        except Exception:
            logger.exception("Campionamento locale non riuscito")
        await asyncio.sleep(300)


async def weather_loop() -> None:
    while True:
        try:
            await weather_monitor.monitor_once()
        except Exception:
            logger.exception("Sorveglianza meteo non riuscita")
        await asyncio.sleep(settings.weather_interval_minutes * 60)


async def travel_loop() -> None:
    while True:
        try:
            result = travel_tracker.observe(await ha.monitoring_states())
            if result.get("status") in {"started", "arrived"}:
                if result["status"] == "started":
                    message = (
                        "Partenza rilevata automaticamente. "
                        "Il diario GPS del viaggio è iniziato."
                    )
                else:
                    message = (
                        "Arrivo rilevato dopo la sosta prolungata. "
                        "Il diario del viaggio è stato chiuso e salvato."
                    )
                await ha.send_notification(
                    settings.notification_service,
                    "Mistermif AI · Diario viaggio",
                    message,
                )
        except Exception:
            logger.exception("Monitoraggio viaggio non riuscito")
        await asyncio.sleep(settings.travel_poll_seconds)


async def fridge_loop() -> None:
    while True:
        try:
            await fridge_optimizer.monitor_once()
        except Exception:
            logger.exception("Monitoraggio frigorifero non riuscito")
        await asyncio.sleep(60)


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
    weather_task = (
        asyncio.create_task(weather_loop())
        if settings.weather_monitor_enabled
        else None
    )
    travel_task = (
        asyncio.create_task(travel_loop())
        if settings.travel_tracker_enabled
        else None
    )
    fridge_task = asyncio.create_task(fridge_loop())
    bridge_server = None
    bridge_task = None
    if settings.codex_bridge_enabled:
        if len(settings.codex_bridge_token) < 32:
            logger.error(
                "Ponte Codex non avviato: configura un token di almeno 32 caratteri"
            )
        else:
            collaboration = CollaborationService(
                memory=memory,
                policy=policy,
                learner=learner,
                states_provider=ha.states,
                health_provider=ha.health,
                autonomy_provider=autonomy_enabled,
                animals_provider=animals_on_board,
                lab_mode_provider=lab_mode,
            )
            bridge_server = uvicorn.Server(
                uvicorn.Config(
                    create_bridge_app(settings.codex_bridge_token, collaboration),
                    host="0.0.0.0",
                    port=settings.codex_bridge_port,
                    log_level=settings.log_level,
                    access_log=False,
                )
            )
            bridge_task = asyncio.create_task(bridge_server.serve())
            logger.info(
                "Ponte privato Codex attivo sulla porta %d",
                settings.codex_bridge_port,
            )
    yield
    if bridge_server is not None:
        bridge_server.should_exit = True
    if bridge_task is not None:
        with suppress(asyncio.CancelledError):
            await bridge_task
    learning_task.cancel()
    with suppress(asyncio.CancelledError):
        await learning_task
    for task in (weather_task, travel_task, fridge_task):
        if task is not None:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task


APP_VERSION = "1.4.3"


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
    return FileResponse(
        os.path.join(os.path.dirname(__file__), "static", "index.html"),
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@app.get("/caravan-eyes.png")
async def caravan_icon() -> FileResponse:
    return FileResponse(
        os.path.join(os.path.dirname(__file__), "static", "caravan-eyes.png"),
        headers={"Cache-Control": "no-cache, must-revalidate, max-age=0"},
    )


@app.get("/api/status")
async def status() -> dict:
    learning = learner.summary()
    weather_state = memory.get_json_setting("weather_monitor_state") or {}
    trip_state = travel_tracker.report()
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
        "codex_bridge": {
            "enabled": settings.codex_bridge_enabled,
            "ready": settings.codex_bridge_enabled
            and len(settings.codex_bridge_token) >= 32,
            "port": settings.codex_bridge_port,
            "real_actions": False,
        },
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
        "weather_monitor": {
            "enabled": settings.weather_monitor_enabled,
            "interval_minutes": settings.weather_interval_minutes,
            "severity": weather_state.get("severity", "non ancora analizzato"),
            "notified": bool(weather_state.get("notified", False)),
            "sources": weather_state.get("sources", {}),
            "local_decisions": True,
            "gemini_enabled": settings.weather_ai_enabled,
            "gemini_ready": agent.can_evaluate_weather(),
            "gemini_budget": weather_ai_usage.snapshot(),
            "local_observation": weather_state.get("local_observation", {}),
            "local_trend": weather_state.get("local_trend", {}),
        },
        "travel_tracker": {
            "enabled": settings.travel_tracker_enabled,
            "poll_seconds": settings.travel_poll_seconds,
            "arrival_minutes": settings.travel_arrival_minutes,
            "latest": trip_state,
        },
        "fridge_optimizer": fridge_optimizer.public_status(),
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


@app.get("/api/weather-monitor")
async def weather_monitor_status() -> dict:
    return memory.get_json_setting("weather_monitor_state") or {
        "severity": "non ancora analizzato",
        "enabled": settings.weather_monitor_enabled,
    }


@app.post("/api/weather-monitor/check")
async def weather_monitor_check() -> dict:
    return await weather_monitor.monitor_once()


@app.get("/api/trips")
async def trips() -> dict:
    return {"items": memory.list_trips(), "latest_report": travel_tracker.report()}


@app.get("/api/trips/{trip_id}")
async def trip_detail(trip_id: int) -> dict:
    result = memory.trip_detail(trip_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Viaggio non trovato")
    return {"trip": result, "report": travel_tracker.report(trip_id)}


@app.get("/api/trips/{trip_id}/export.csv")
async def export_trip_csv(trip_id: int) -> PlainTextResponse:
    try:
        content = travel_tracker.export_csv(trip_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Viaggio non trovato") from exc
    return PlainTextResponse(
        content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="viaggio-{trip_id}.csv"'},
    )


@app.get("/api/trips/{trip_id}/export.gpx")
async def export_trip_gpx(trip_id: int) -> PlainTextResponse:
    try:
        content = travel_tracker.export_gpx(trip_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Viaggio non trovato") from exc
    return PlainTextResponse(
        content,
        media_type="application/gpx+xml; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="viaggio-{trip_id}.gpx"'},
    )


@app.get("/api/context")
async def context() -> dict:
    return {"entities": await ha.states()}


@app.get("/api/dashboard")
async def dashboard() -> dict:
    return {
        "metrics": await ha.dashboard_snapshot(),
        "weather": memory.get_json_setting("weather_monitor_state") or {},
        "fridge": fridge_optimizer.public_status(),
        "autonomy_enabled": autonomy_enabled(),
        "animals_on_board": animals_on_board(),
    }


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
    fridge_answer = fridge_optimizer.handle_message(payload.message)
    fridge_status_snapshot = fridge_optimizer.public_status()
    semantic_hints = (
        "lascia",
        "per ora",
        "per adesso",
        "niente",
        "non tocc",
        "non fare",
        "preferisco",
        "come prima",
        "stai fermo",
        "occupatene",
    )
    semantic_candidate = (
        fridge_answer is not None
        and (
            fridge_answer.startswith("Per attivare")
            or fridge_answer.startswith("Ho identificato")
        )
    ) or (
        fridge_answer is None
        and bool(fridge_status_snapshot.get("entities"))
        and any(hint in normalized for hint in semantic_hints)
    )
    interpretation = None
    if semantic_candidate and agent.can_interpret_intent():
        try:
            interpretation = await agent.interpret_fridge_intent(
                payload.message,
                fridge_status_snapshot,
            )
            interpreted_answer = fridge_optimizer.apply_interpreted_intent(
                interpretation
            )
            if interpreted_answer is not None:
                fridge_answer = interpreted_answer
        except Exception:
            logger.exception("Interpretazione semantica frigorifero non riuscita")
    if fridge_answer is not None:
        memory.add_message(user_id, "user", payload.message)
        memory.add_message(user_id, "assistant", fridge_answer)
        return {
            "answer": fridge_answer,
            "user": display_name,
            "fridge_optimizer": fridge_optimizer.public_status(),
            "semantic_interpretation": interpretation,
        }
    plan = travel_tracker.capture_plan(payload.message)
    if plan is not None:
        answer = (
            f'Ho memorizzato la prossima destinazione: {plan["destination"]}. '
            "Quando il GPS rileverà la partenza avvierò automaticamente il diario; "
            "dopo una sosta prolungata riconoscerò l'arrivo e chiuderò il viaggio."
        )
        memory.add_message(user_id, "user", payload.message)
        memory.add_message(user_id, "assistant", answer)
        return {"answer": answer, "user": display_name, "travel_plan": plan}
    if "report" in normalized and any(
        term in normalized for term in ("viaggio", "tragitto", "spostamento")
    ):
        report = travel_tracker.report()
        if report.get("available"):
            answer = (
                f'Viaggio #{report["id"]} verso {report["destination"]}: '
                f'{report["distance_km"]} km in {report["duration_minutes"]} minuti totali, '
                f'di cui {report["moving_minutes"]} in movimento, '
                f'velocità media {report["average_speed_kmh"]} km/h, '
                f'massima {report["max_speed_kmh"]} km/h e {report["stops"]} soste.'
            )
        else:
            answer = str(report["message"])
        return {"answer": answer, "user": display_name, "travel_report": report}
    if "esport" in normalized and any(
        term in normalized for term in ("viaggio", "tragitto", "spostamento")
    ):
        report = travel_tracker.report()
        if report.get("available"):
            trip_id = int(report["id"])
            answer = (
                f"Il viaggio #{trip_id} è pronto: CSV api/trips/{trip_id}/export.csv "
                f"oppure traccia GPX api/trips/{trip_id}/export.gpx."
            )
        else:
            answer = str(report["message"])
        return {"answer": answer, "user": display_name, "travel_report": report}
    asks_location = asks_for_location(payload.message)
    if asks_location:
        try:
            location = await ha.location_snapshot()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("Lettura locale GPS non riuscita: %s", exc)
            location = {"available": False, "reason": "home_assistant_non_raggiungibile"}
        if location.get("available"):
            accuracy = location.get("accuracy_m")
            accuracy_text = (
                f", precisione dichiarata circa {accuracy:g} m"
                if isinstance(accuracy, (int, float))
                else ""
            )
            updated_text = (
                f', ultimo aggiornamento {location["last_updated"]}'
                if location.get("last_updated")
                else ""
            )
            answer = (
                "Sì: Home Assistant mi fornisce una posizione GPS valida "
                f'({location["latitude"]:.6f}, {location["longitude"]:.6f})'
                f"{accuracy_text}{updated_text}. I sensori risultano leggibili; "
                "la posizione viene verificata localmente e non la considero un guasto."
            )
        else:
            answer = (
                "Al momento non riesco a ricavare una coppia completa di coordinate "
                "GPS da Home Assistant. Questo non significa automaticamente che il "
                "sensore sia guasto: potrebbe essere offline, non ancora aggiornato o "
                "avere un entity_id non riconosciuto."
            )
        memory.add_message(user_id, "user", payload.message)
        memory.add_message(user_id, "assistant", answer)
        return {
            "answer": answer,
            "user": display_name,
            "location": location,
            "resolved_locally": True,
        }
    simulation = run_conversational_simulation(
        payload.message,
        animals_default=animals_on_board(),
    )
    if simulation is not None:
        memory.add_message(user_id, "user", payload.message)
        memory.add_message(user_id, "assistant", simulation["answer"])
        if settings.workspace_enabled:
            try:
                if simulation["kind"] == "single":
                    workspace.record_lab_result(simulation["result"])
                elif simulation["kind"] == "full":
                    for item in simulation["items"]:
                        workspace.record_lab_result(item["result"])
            except (OSError, WorkspaceError):
                logger.exception(
                    "Registrazione della simulazione conversazionale non riuscita"
                )
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


@app.get("/api/fridge")
async def fridge_status() -> dict:
    return fridge_optimizer.public_status()


@app.post("/api/fridge/check")
async def fridge_check() -> dict:
    try:
        return await fridge_optimizer.monitor_once()
    except (PermissionError, RuntimeError, httpx.HTTPError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


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
