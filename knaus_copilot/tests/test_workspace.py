from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from app.workspace import WorkspaceError, WorkspaceManager


class WorkspaceManagerTest(TestCase):
    def test_bootstrap_creates_dedicated_folders(self):
        with TemporaryDirectory() as directory:
            manager = WorkspaceManager(Path(directory))
            manager.bootstrap()
            self.assertTrue((manager.root / "plance").is_dir())
            self.assertTrue((manager.root / "automazioni").is_dir())
            self.assertTrue((manager.root / "laboratorio").is_dir())
            self.assertTrue((manager.root / "manifest/files.json").is_file())

    def test_path_escape_is_blocked(self):
        with TemporaryDirectory() as directory:
            manager = WorkspaceManager(Path(directory))
            manager.bootstrap()
            with self.assertRaises(WorkspaceError):
                manager.write_text("../configuration.yaml", "bad")

    def test_include_is_added_with_backup(self):
        with TemporaryDirectory() as directory:
            config_dir = Path(directory)
            (config_dir / "configuration.yaml").write_text(
                "default_config:\n",
                encoding="utf-8",
            )
            manager = WorkspaceManager(config_dir)
            manager.bootstrap()
            result = manager.install_include()
            content = (config_dir / "configuration.yaml").read_text(encoding="utf-8")
            self.assertTrue(result["changed"])
            self.assertIn(
                "packages: !include_dir_named mistermif_ai/packages",
                content,
            )
            self.assertTrue(any((manager.root / "backup").iterdir()))

    def test_existing_standard_packages_use_bridge_file(self):
        with TemporaryDirectory() as directory:
            config_dir = Path(directory)
            (config_dir / "configuration.yaml").write_text(
                "homeassistant:\n  packages: !include_dir_named packages\n",
                encoding="utf-8",
            )
            manager = WorkspaceManager(config_dir)
            manager.bootstrap()
            result = manager.install_include()

            self.assertTrue(result["changed"])
            self.assertEqual(
                "!include_dir_merge_named ../mistermif_ai/packages\n",
                (config_dir / "packages/mistermif_ai.yaml").read_text(
                    encoding="utf-8"
                ),
            )
            self.assertTrue(manager.summary()["include_installed"])

    def test_nonstandard_packages_are_never_overwritten(self):
        with TemporaryDirectory() as directory:
            config_dir = Path(directory)
            (config_dir / "configuration.yaml").write_text(
                "homeassistant:\n  packages: !include custom_packages.yaml\n",
                encoding="utf-8",
            )
            manager = WorkspaceManager(config_dir)
            manager.bootstrap()
            with self.assertRaises(WorkspaceError):
                manager.install_include()

    def test_energy_lab_bundle_stays_inside_workspace(self):
        with TemporaryDirectory() as directory:
            manager = WorkspaceManager(Path(directory))
            result = manager.create_energy_lab_bundle()

            self.assertEqual("simulation", result["mode"])
            self.assertFalse(result["real_services_called"])
            self.assertTrue(
                (
                    manager.root / "packages/mistermif_ai_energy_lab.yaml"
                ).is_file()
            )
            self.assertTrue(
                (manager.root / "plance/energy_safety_lab.yaml").is_file()
            )
            package = (
                manager.root / "packages/mistermif_ai_energy_lab.yaml"
            ).read_text(encoding="utf-8")
            self.assertIn("input_number:", package)
            self.assertNotIn("climate.turn_off", package)

    def test_overwrite_creates_rollback_copy(self):
        with TemporaryDirectory() as directory:
            manager = WorkspaceManager(Path(directory))
            manager.bootstrap()
            manager.write_text("helper/example.yaml", "version: 1\n")
            manager.write_text("helper/example.yaml", "version: 2\n")

            backups = list(
                (manager.root / "backup/generated").rglob("example.yaml")
            )
            self.assertEqual(1, len(backups))
            self.assertEqual(
                "version: 1\n",
                backups[0].read_text(encoding="utf-8"),
            )

    def test_generic_artifacts_are_drafts_and_not_loaded(self):
        with TemporaryDirectory() as directory:
            manager = WorkspaceManager(Path(directory))
            artifact = manager.create_artifact(
                "dashboard",
                "temperature_caravan",
                "title: Temperature\nviews: []",
                "Plancia temperature",
            )

            self.assertEqual("draft", artifact["state"])
            self.assertFalse(artifact["loaded_by_home_assistant"])
            self.assertTrue(
                (manager.root / "plance/temperature_caravan.yaml").is_file()
            )
            self.assertEqual(artifact, manager.list_artifacts()[0])

    def test_generic_artifact_rejects_unsafe_name(self):
        with TemporaryDirectory() as directory:
            manager = WorkspaceManager(Path(directory))
            with self.assertRaises(WorkspaceError):
                manager.create_artifact(
                    "helper",
                    "../outside",
                    "input_number: {}",
                )
