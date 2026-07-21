#!/usr/bin/env python3
"""Create the local, git-ignored pairing file used by the Codex MCP adapter."""

from __future__ import annotations

import getpass
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / ".mistermif-bridge.local.json"


def main() -> None:
    print("Abbinamento privato Codex ↔ mistermif AI")
    url = input("Indirizzo ponte [http://knaus.local:8100]: ").strip()
    url = (url or "http://knaus.local:8100").rstrip("/")
    token = getpass.getpass("Token (minimo 32 caratteri, non verrà mostrato): ").strip()
    if len(token) < 32:
        raise SystemExit("Token troppo corto: servono almeno 32 caratteri.")
    TARGET.write_text(
        json.dumps({"url": url, "token": token}, indent=2) + "\n",
        encoding="utf-8",
    )
    os.chmod(TARGET, 0o600)
    print(f"Abbinamento salvato localmente in {TARGET}")
    print("Il file è escluso da Git e non contiene dati destinati alla repo.")


if __name__ == "__main__":
    main()
