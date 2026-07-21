#!/usr/bin/env python3
"""MCP STDIO adapter for the private mistermif AI collaboration bridge."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


SERVER_NAME = "mistermif-ai"
SERVER_VERSION = "0.9.0"
DEFAULT_PROTOCOL = "2025-06-18"
LOCAL_CONFIG = Path(__file__).resolve().parent.parent / ".mistermif-bridge.local.json"


TOOLS = [
    {
        "name": "mistermif_status",
        "description": (
            "Legge lo stato filtrato della caravan e i vincoli di Mistermif AI. "
            "Non esegue azioni."
        ),
        "inputSchema": {"type": "object", "properties": {}},
        "annotations": {"readOnlyHint": True, "destructiveHint": False},
    },
    {
        "name": "mistermif_discuss",
        "description": (
            "Apre un confronto consultivo con Mistermif AI e registra localmente "
            "la conclusione. Non esegue azioni."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "message": {"type": "string", "minLength": 1, "maxLength": 8000},
                "request_id": {"type": "string", "maxLength": 120},
            },
            "required": ["message"],
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False},
    },
    {
        "name": "mistermif_simulate",
        "description": (
            "Chiede al gemello digitale di simulare uno scenario descritto in "
            "linguaggio naturale e confronta il risultato. Zero azioni reali."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "message": {"type": "string", "minLength": 1, "maxLength": 8000},
                "request_id": {"type": "string", "maxLength": 120},
            },
            "required": ["message"],
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False},
    },
    {
        "name": "mistermif_self_check",
        "description": (
            "Esegue tutti gli scenari deterministici del gemello digitale e "
            "restituisce il verdetto di Mistermif AI. Zero azioni reali."
        ),
        "inputSchema": {"type": "object", "properties": {}},
        "annotations": {"readOnlyHint": True, "destructiveHint": False},
    },
    {
        "name": "mistermif_propose",
        "description": (
            "Sottopone una proposta a Mistermif AI. Può concordare analisi, bozze "
            "e simulazioni; modifiche e comandi restano bloccati e richiedono l'utente."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "message": {"type": "string", "minLength": 1, "maxLength": 8000},
                "request_id": {"type": "string", "maxLength": 120},
            },
            "required": ["message"],
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False},
    },
]


def load_connection() -> tuple[str, str]:
    data: dict[str, Any] = {}
    config_path = Path(os.getenv("MISTERMIF_BRIDGE_CONFIG", str(LOCAL_CONFIG)))
    if config_path.exists():
        parsed = json.loads(config_path.read_text(encoding="utf-8"))
        if isinstance(parsed, dict):
            data = parsed
    url = str(
        os.getenv("MISTERMIF_BRIDGE_URL")
        or data.get("url")
        or "http://knaus.local:8100"
    ).rstrip("/")
    token = str(os.getenv("MISTERMIF_BRIDGE_TOKEN") or data.get("token") or "")
    if len(token) < 32:
        raise RuntimeError(
            "Ponte non abbinato: esegui tools/setup_mistermif_bridge.py "
            "e usa lo stesso token configurato nell'add-on."
        )
    return url, token


def bridge_request(path: str, *, payload: dict[str, Any] | None = None) -> Any:
    url, token = load_connection()
    body = None
    method = "GET"
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        method = "POST"
    request = urllib.request.Request(
        f"{url}{path}",
        data=body,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Ponte HTTP {exc.code}: {detail[:500]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Ponte non raggiungibile: {exc.reason}") from exc


def call_tool(name: str, arguments: dict[str, Any]) -> Any:
    if name == "mistermif_status":
        return bridge_request("/v1/status")
    modes = {
        "mistermif_discuss": "discuss",
        "mistermif_simulate": "simulate",
        "mistermif_self_check": "self_check",
        "mistermif_propose": "proposal",
    }
    mode = modes.get(name)
    if mode is None:
        raise RuntimeError(f"Strumento MCP sconosciuto: {name}")
    message = str(arguments.get("message") or "Esegui il self-check completo")
    return bridge_request(
        "/v1/collaborate",
        payload={
            "mode": mode,
            "message": message,
            "sender": "codex",
            "request_id": arguments.get("request_id"),
        },
    )


def result_text(value: Any) -> dict[str, Any]:
    text = json.dumps(value, ensure_ascii=False, indent=2)
    return {
        "content": [{"type": "text", "text": text}],
        "structuredContent": value if isinstance(value, dict) else {"value": value},
        "isError": False,
    }


def handle(message: dict[str, Any]) -> dict[str, Any] | None:
    method = message.get("method")
    request_id = message.get("id")
    if request_id is None:
        return None
    if method == "initialize":
        requested = message.get("params", {}).get("protocolVersion")
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": requested or DEFAULT_PROTOCOL,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
                "instructions": (
                    "Usa questo ponte solo per leggere stato filtrato, discutere, "
                    "simulare e sottoporre proposte. Non dichiarare mai eseguita "
                    "un'azione reale: tutti gli strumenti sono consultivi e il "
                    "consenso non sostituisce l'autorizzazione dell'utente."
                ),
            },
        }
    if method == "ping":
        return {"jsonrpc": "2.0", "id": request_id, "result": {}}
    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {"tools": TOOLS},
        }
    if method == "tools/call":
        params = message.get("params") or {}
        try:
            value = call_tool(str(params.get("name", "")), params.get("arguments") or {})
            result = result_text(value)
        except Exception as exc:  # MCP must return tool errors, not terminate.
            result = {
                "content": [{"type": "text", "text": str(exc)}],
                "isError": True,
            }
        return {"jsonrpc": "2.0", "id": request_id, "result": result}
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": -32601, "message": f"Metodo non supportato: {method}"},
    }


def main() -> None:
    for raw_line in sys.stdin:
        try:
            message = json.loads(raw_line)
            response = handle(message)
            if response is not None:
                sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
                sys.stdout.flush()
        except Exception as exc:
            sys.stderr.write(f"mistermif MCP: {exc}\n")
            sys.stderr.flush()


if __name__ == "__main__":
    main()
