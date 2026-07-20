from __future__ import annotations

import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

from .automation_lab import (
    LAB_DASHBOARD_YAML,
    LAB_DYNAMIC_POLICY_YAML,
    LAB_FIXED_AUTOMATION_YAML,
    LAB_HELPERS_YAML,
    LAB_PACKAGE_YAML,
    LAB_VERSION,
)


WORKSPACE_NAME = "mistermif_ai"
WORKSPACE_FOLDERS = (
    "packages",
    "plance",
    "automazioni",
    "script",
    "template",
    "helper",
    "laboratorio",
    "backup",
    "log",
    "manifest",
)
INCLUDE_LINE = "  packages: !include_dir_named mistermif_ai/packages"
STANDARD_PACKAGES_LINE = "packages: !include_dir_named packages"
BRIDGE_NAME = "mistermif_ai.yaml"
BRIDGE_CONTENT = "!include_dir_merge_named ../mistermif_ai/packages\n"
ARTIFACT_FOLDERS = {
    "dashboard": "plance",
    "helper": "helper",
    "fixed_automation": "automazioni",
    "dynamic_automation": "automazioni",
    "script": "script",
    "template": "template",
}
SAFE_ARTIFACT_NAME = re.compile(r"^[a-z0-9][a-z0-9_-]{1,63}$")
MAX_ARTIFACT_SIZE = 100_000


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
        backup = None
        if destination.exists() and destination.read_text(encoding="utf-8") != content:
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            backup = self.safe_path(
                str(
                    Path("backup")
                    / "generated"
                    / timestamp
                    / destination.relative_to(self.root)
                )
            )
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(destination, backup)
        destination.write_text(content, encoding="utf-8")
        self._journal(
            "write",
            {
                "path": str(destination.relative_to(self.root)),
                "previous_hash": previous_hash,
                "new_hash": self._hash(destination),
                "backup": str(backup.relative_to(self.root)) if backup else None,
            },
        )
        self._write_manifest()
        return destination

    def create_energy_lab_bundle(self) -> dict:
        self.bootstrap()
        files = {
            "packages/mistermif_ai_energy_lab.yaml": LAB_PACKAGE_YAML,
            "plance/energy_safety_lab.yaml": LAB_DASHBOARD_YAML,
            "helper/energy_safety_lab.yaml": LAB_HELPERS_YAML,
            "automazioni/energy_safety_lab_fixed.yaml": LAB_FIXED_AUTOMATION_YAML,
            "automazioni/energy_safety_lab_dynamic_policy.yaml": (
                LAB_DYNAMIC_POLICY_YAML
            ),
        }
        written = []
        for relative_path, content in files.items():
            self.write_text(relative_path, content)
            written.append(relative_path)
        manifest = {
            "name": "Energy Safety Lab",
            "version": LAB_VERSION,
            "files": written,
            "mode": "simulation",
            "real_services_called": False,
            "requires_home_assistant_restart": self._include_installed(),
        }
        self.write_text(
            "laboratorio/energy_safety_lab.json",
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        )
        self._journal("create_energy_lab_bundle", manifest)
        return manifest

    def create_artifact(
        self,
        kind: str,
        name: str,
        content: str,
        description: str = "",
    ) -> dict:
        self.bootstrap()
        folder = ARTIFACT_FOLDERS.get(kind)
        if not folder:
            raise WorkspaceError("Tipo di artefatto non autorizzato")
        if not SAFE_ARTIFACT_NAME.fullmatch(name):
            raise WorkspaceError(
                "Nome non valido: usa solo lettere minuscole, numeri, _ o -"
            )
        if not content.strip():
            raise WorkspaceError("Il contenuto non può essere vuoto")
        if len(content.encode("utf-8")) > MAX_ARTIFACT_SIZE:
            raise WorkspaceError("Artefatto troppo grande")
        if "\x00" in content:
            raise WorkspaceError("Contenuto non valido")

        relative_path = f"{folder}/{name}.yaml"
        self.write_text(relative_path, content.rstrip() + "\n")
        metadata = {
            "kind": kind,
            "name": name,
            "path": relative_path,
            "description": description[:500],
            "state": "draft",
            "loaded_by_home_assistant": False,
            "external_changes": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self.write_text(
            f"manifest/artifact-{kind}-{name}.json",
            json.dumps(metadata, indent=2, ensure_ascii=False) + "\n",
        )
        self._journal("create_artifact_draft", metadata)
        return metadata

    def list_artifacts(self) -> list[dict]:
        if not self.root.exists():
            return []
        result = []
        for path in sorted((self.root / "manifest").glob("artifact-*.json")):
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if isinstance(value, dict):
                result.append(value)
        return result

    def record_lab_result(self, result: dict) -> None:
        self.bootstrap()
        log_path = self.safe_path("log/energy_safety_lab.jsonl")
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(result, ensure_ascii=False) + "\n")
        self._write_manifest()

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
            packages_lines = [
                line.strip()
                for line in section
                if line.strip().startswith("packages:")
            ]
            if packages_lines:
                if packages_lines != [STANDARD_PACKAGES_LINE]:
                    raise WorkspaceError(
                        "La sezione homeassistant/packages usa una struttura non "
                        "supportata: intervento manuale richiesto"
                    )
                bridge_dir = self.config_dir / "packages"
                bridge_dir.mkdir(exist_ok=True)
                bridge = bridge_dir / BRIDGE_NAME
                if bridge.exists() and bridge.read_text(encoding="utf-8") != BRIDGE_CONTENT:
                    raise WorkspaceError(
                        "Il file ponte packages/mistermif_ai.yaml esiste già con "
                        "contenuto diverso"
                    )
                bridge.write_text(BRIDGE_CONTENT, encoding="utf-8")
                self._journal(
                    "install_bridge",
                    {
                        "file": f"packages/{BRIDGE_NAME}",
                        "backup": str(backup.relative_to(self.root)),
                    },
                )
                return {"changed": True, "backup": str(backup), "bridge": str(bridge)}
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
        if not configuration.exists():
            return False
        text = configuration.read_text(encoding="utf-8")
        if "mistermif_ai/packages" in text:
            return True
        bridge = self.config_dir / "packages" / BRIDGE_NAME
        return (
            STANDARD_PACKAGES_LINE in text
            and bridge.exists()
            and bridge.read_text(encoding="utf-8") == BRIDGE_CONTENT
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
