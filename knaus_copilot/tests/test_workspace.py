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

    def test_existing_packages_are_never_overwritten(self):
        with TemporaryDirectory() as directory:
            config_dir = Path(directory)
            (config_dir / "configuration.yaml").write_text(
                "homeassistant:\n  packages: !include_dir_named packages\n",
                encoding="utf-8",
            )
            manager = WorkspaceManager(config_dir)
            manager.bootstrap()
            with self.assertRaises(WorkspaceError):
                manager.install_include()
