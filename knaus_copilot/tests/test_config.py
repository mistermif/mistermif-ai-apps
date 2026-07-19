import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from app.config import Settings


class SettingsTest(TestCase):
    def test_missing_api_key_is_allowed(self):
        with TemporaryDirectory() as directory:
            options_file = Path(directory) / "options.json"
            options_file.write_text("{}", encoding="utf-8")
            environment = {
                "KNAUS_DATA_DIR": directory,
                "KNAUS_OPTIONS_FILE": str(options_file),
            }
            with patch.dict(os.environ, environment, clear=True):
                settings = Settings.load()

            self.assertEqual("", settings.openai_api_key)
            self.assertEqual("local", settings.ai_provider)
            self.assertEqual("", settings.ai_api_key)
            self.assertEqual("local-rules", settings.model)
            self.assertEqual("observe", settings.autonomy_mode)
            self.assertEqual("local_only", settings.privacy_mode)

    def test_context_limit_is_clamped(self):
        with TemporaryDirectory() as directory:
            options_file = Path(directory) / "options.json"
            options_file.write_text(
                json.dumps({"max_context_entities": 999}),
                encoding="utf-8",
            )
            environment = {
                "KNAUS_DATA_DIR": directory,
                "KNAUS_OPTIONS_FILE": str(options_file),
            }
            with patch.dict(os.environ, environment, clear=True):
                settings = Settings.load()

            self.assertEqual(200, settings.max_context_entities)

    def test_groq_uses_compatible_defaults_and_migrates_key(self):
        with TemporaryDirectory() as directory:
            options_file = Path(directory) / "options.json"
            options_file.write_text(
                json.dumps(
                    {
                        "ai_provider": "groq",
                        "ai_api_key": "groq-test-key",
                        "privacy_mode": "redacted_cloud",
                    }
                ),
                encoding="utf-8",
            )
            environment = {
                "KNAUS_DATA_DIR": directory,
                "KNAUS_OPTIONS_FILE": str(options_file),
            }
            with patch.dict(os.environ, environment, clear=True):
                settings = Settings.load()

            self.assertEqual("groq", settings.ai_provider)
            self.assertEqual("groq-test-key", settings.ai_api_key)
            self.assertEqual("https://api.groq.com/openai/v1", settings.ai_base_url)
            self.assertEqual("openai/gpt-oss-20b", settings.model)
