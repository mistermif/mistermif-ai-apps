from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from app.memory import MemoryStore


class MemoryStoreTest(TestCase):
    def test_runtime_setting_is_persisted(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "memory.sqlite3"
            store = MemoryStore(path)

            self.assertEqual("false", store.get_setting("autonomy_enabled", "false"))
            store.set_setting("autonomy_enabled", "true")

            reopened = MemoryStore(path)
            self.assertEqual("true", reopened.get_setting("autonomy_enabled"))

    def test_json_setting_is_persisted_locally(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "memory.sqlite3"
            store = MemoryStore(path)
            store.set_json_setting(
                "vehicle_profile",
                {"vehicle_type": "caravan", "brand": "Knaus"},
            )

            reopened = MemoryStore(path)
            self.assertEqual(
                {"vehicle_type": "caravan", "brand": "Knaus"},
                reopened.get_json_setting("vehicle_profile"),
            )

    def test_messages_are_returned_in_chronological_order(self):
        with TemporaryDirectory() as directory:
            store = MemoryStore(Path(directory) / "memory.sqlite3")
            store.add_message("utente_a", "user", "prima")
            store.add_message("utente_a", "assistant", "seconda")

            messages = store.recent_messages("utente_a")

            self.assertEqual(["prima", "seconda"], [m["content"] for m in messages])

    def test_shared_memories_are_visible_to_other_users(self):
        with TemporaryDirectory() as directory:
            store = MemoryStore(Path(directory) / "memory.sqlite3")
            store.add_memory("shared", "campeggio", "Sosta esempio", "Nota condivisa")
            store.add_memory("utente_a", "preferenza", "Energia", "Nota privata")

            altro_utente = store.list_memories("utente_b")

            self.assertEqual(1, len(altro_utente))
            self.assertEqual("Sosta esempio", altro_utente[0]["title"])
