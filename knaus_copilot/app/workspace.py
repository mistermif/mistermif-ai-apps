from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


WORKSPACE_NAME = "mistermif_ai"
WORKSPACE_FOLDERS = (
    "packages",
    "plance",
    "automazioni",
    "script",
    "template",
    "helper",
    "backup",
    "log",
    "manifest",
)
INCLUDE_LINE = "  packages: !include_dir_named mistermif_ai/packages"


class WorkspaceError(RuntimeError):
    pass


class WorkspaceManager:
    def __init__(self, config_dir: Path):
        self.config_dir = config_dir.resolve()
        self.root = (self.config_dir / WORKSPACE_NAME).resolve()
        if self.root.parent != self.config_dir:
            raise WorkspaceError("Percorso workspace non valido")

    def bootstrap(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        for folder in WORKSPACE_FOLDERS:
            (self.root / folder).mkdir(exist_ok=True)
        readme = self.root / "README.md"
        if not readme.exists():
            readme.write_text(
                "# mistermif AI workspace\n\n"
                "Tutti i file creati dall'assistente restano in questa cartella.\n"
                "La configurazione attiva è caricata da `packages/`.\n",
                encoding="utf-8",
            )
        self._write_manifest()
        self._journal("workspace_bootstrap", {"root": str(self.root)})

    def safe_path(self, relative_path: str) -> Path:
        candidate = (self.root / relative_path).resolve()
        if candidate != self.root and self.root not in candidate.parents:
            raise WorkspaceError("Scrittura fuori dal workspace bloccata")
        return candidate

    def write_text(self, relative_path: str, content: str) -> Path:
        destination = self.safe_path(relative_path)
        if destination.suffix not in {".yaml", ".yml", ".json", ".md", ".txt"}:
            raise WorkspaceError("Tipo di file non autorizzato")
        destination.parent.mkdir(parents=True, exist_ok=True)
        previous_hash = self._hash(destination) if destination.exists() else None
        destination.write_text(content, encoding="utf-8")
        self._journal(
            "write",
            {
                "path": str(destination.relative_to(self.root)),
                "previous_hash": previous_hash,
                "new_hash": self._hash(destination),
            },
        )
        self._write_manifest()
        return destination

    def install_include(self) -> dict:
        configuration = self.config_dir / "configuration.yaml"
        if not configuration.exists():
            raise WorkspaceError("configuration.yaml non trovato")
        text = configuration.read_text(encoding="utf-8")
        if "mistermif_ai/packages" in text:
            return {"changed": False, "message": "Include già presente"}
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = self.root / "backup" / f"configuration-{timestamp}.yaml"
        shutil.copy2(configuration, backup)

        lines = text.splitlines()
        homeassistant_index = next(
            (index for index, line in enumerate(lines) if line.strip() == "homeassistant:"),
            None,
        )
        if homeassistant_index is None:
            addition = [
                "",
                "# mistermif AI - unico collegamento gestito",
                "homeassistant:",
                INCLUDE_LINE,
            ]
            lines.extend(addition)
        else:
            section_end = len(lines)
            for index in range(homeassistant_index + 1, len(lines)):
                line = lines[index]
                if line and not line.startswith((" ", "\t", "#")):
                    section_end = index
                    break
            section = lines[homeassistant_index + 1 : section_end]
            if any(line.strip().startswith("packages:") for line in section):
                raise WorkspaceError(
                    "La sezione homeassistant/packages esiste già: intervento manuale richiesto"
                )
            lines.insert(homeassistant_index + 1, INCLUDE_LINE)

        configuration.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
        self._journal(
            "install_include",
            {"file": "configuration.yaml", "backup": str(backup.relative_to(self.root))},
        )
        return {"changed": True, "backup": str(backup)}

    def summary(self) -> dict:
        return {
            "root": str(self.root),
            "exists": self.root.exists(),
            "include_installed": self._include_installed(),
            "folders": list(WORKSPACE_FOLDERS),
        }

    def _include_installed(self) -> bool:
        configuration = self.config_dir / "configuration.yaml"
        return (
            configuration.exists()
            and "mistermif_ai/packages"
            in configuration.read_text(encoding="utf-8")
        )

    def _journal(self, action: str, details: dict) -> None:
        log_path = self.root / "log" / "changes.jsonl"
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "details": details,
        }
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def _write_manifest(self) -> None:
        manifest = {}
        for path in sorted(self.root.rglob("*")):
            if path.is_file() and "manifest" not in path.parts:
                manifest[str(path.relative_to(self.root))] = self._hash(path)
        (self.root / "manifest" / "files.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    @staticmethod
    def _hash(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()
