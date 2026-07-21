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
            self.assertFalse(settings.codex_bridge_enabled)
            self.assertEqual("", settings.codex_bridge_token)
            self.assertEqual(8100, settings.codex_bridge_port)
            self.assertTrue(settings.weather_monitor_enabled)
            self.assertEqual(30, settings.weather_interval_minutes)
            self.assertTrue(settings.weather_ai_enabled)
            self.assertEqual(10, settings.weather_ai_daily_limit)
            self.assertTrue(settings.travel_tracker_enabled)
            self.assertEqual(30, settings.travel_poll_seconds)
            self.assertEqual(120, settings.travel_arrival_minutes)

    def test_codex_bridge_options_are_loaded_without_exposing_token(self):
        with TemporaryDirectory() as directory:
            options_file = Path(directory) / "options.json"
            options_file.write_text(
                json.dumps(
                    {
                        "codex_bridge_enabled": True,
                        "codex_bridge_token": "x" * 40,
                    }
                ),
                encoding="utf-8",
            )
            with patch.dict(
                os.environ,
                {
                    "KNAUS_DATA_DIR": directory,
                    "KNAUS_OPTIONS_FILE": str(options_file),
                },
                clear=True,
            ):
                settings = Settings.load()

            self.assertTrue(settings.codex_bridge_enabled)
            self.assertEqual("x" * 40, settings.codex_bridge_token)

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

    def test_gemini_defaults_and_cloud_limits(self):
        with TemporaryDirectory() as directory:
            options_file = Path(directory) / "options.json"
            options_file.write_text(
                json.dumps(
                    {
                        "ai_provider": "gemini",
                        "ai_api_key": "gemini-test-key",
                        "privacy_mode": "contextual_cloud",
                        "cloud_daily_limit": 999,
                        "cloud_automatic_limit": 70,
                    }
                ),
                encoding="utf-8",
            )
            with patch.dict(
                os.environ,
                {
                    "KNAUS_DATA_DIR": directory,
                    "KNAUS_OPTIONS_FILE": str(options_file),
                },
                clear=True,
            ):
                settings = Settings.load()

            self.assertEqual("gemini", settings.ai_provider)
            self.assertEqual("gemini-3.5-flash", settings.model)
            self.assertEqual(
                "https://generativelanguage.googleapis.com/v1beta",
                settings.ai_base_url,
            )
            self.assertEqual("contextual_cloud", settings.privacy_mode)
            self.assertEqual(490, settings.cloud_daily_limit)
            self.assertEqual(70, settings.cloud_automatic_limit)

    def test_gemini_free_defaults_are_conservative(self):
        with TemporaryDirectory() as directory:
            options_file = Path(directory) / "options.json"
            options_file.write_text(
                json.dumps(
                    {
                        "ai_provider": "gemini",
                        "ai_api_key": "test-key",
                        "privacy_mode": "contextual_cloud",
                    }
                ),
                encoding="utf-8",
            )
            with patch.dict(
                os.environ,
                {
                    "KNAUS_DATA_DIR": directory,
                    "KNAUS_OPTIONS_FILE": str(options_file),
                },
                clear=True,
            ):
                settings = Settings.load()

            self.assertEqual(15, settings.cloud_daily_limit)
            self.assertEqual(5, settings.cloud_automatic_limit)
            self.assertFalse(settings.gemini_search_enabled)
