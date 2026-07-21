from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from app.cloud_usage import CloudBudgetExceeded, CloudUsage
from app.memory import MemoryStore


class CloudUsageTest(TestCase):
    def test_automatic_budget_preserves_manual_requests(self):
        with TemporaryDirectory() as directory:
            store = MemoryStore(Path(directory) / "memory.sqlite3")
            usage = CloudUsage(store, daily_limit=3, automatic_limit=1)

            usage.consume(automatic=True)
            with self.assertRaises(CloudBudgetExceeded):
                usage.consume(automatic=True)

            remaining = usage.consume(automatic=False)
            self.assertEqual(2, remaining["total"])
            self.assertEqual(1, remaining["automatic"])

    def test_total_limit_is_never_exceeded(self):
        with TemporaryDirectory() as directory:
            store = MemoryStore(Path(directory) / "memory.sqlite3")
            usage = CloudUsage(store, daily_limit=1, automatic_limit=1)
            usage.consume()
            with self.assertRaises(CloudBudgetExceeded):
                usage.consume()

    def test_separate_budget_uses_an_independent_counter(self):
        with TemporaryDirectory() as directory:
            store = MemoryStore(Path(directory) / "memory.sqlite3")
            chat = CloudUsage(store, 2, 1)
            weather = CloudUsage(store, 10, 10, storage_key="weather_ai_usage")
            chat.consume(automatic=True)
            weather.consume(automatic=True)
            self.assertEqual(1, chat.snapshot()["automatic"])
            self.assertEqual(1, weather.snapshot()["automatic"])
