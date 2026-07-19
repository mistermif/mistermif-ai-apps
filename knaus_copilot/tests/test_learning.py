from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from app.learning import ContextLearner
from app.memory import MemoryStore


class ContextLearnerTest(TestCase):
    def test_site_history_is_separated_by_location(self):
        with TemporaryDirectory() as directory:
            learner = ContextLearner(
                MemoryStore(Path(directory) / "learning.sqlite3")
            )
            first = [
                {
                    "entity_id": "device_tracker.caravan",
                    "state": "home",
                    "attributes": {"latitude": 45.81, "longitude": 8.97},
                },
                {
                    "entity_id": "sensor.pv_power",
                    "name": "Potenza PV",
                    "state": "120",
                },
            ]
            second = [
                {
                    "entity_id": "device_tracker.caravan",
                    "state": "away",
                    "attributes": {"latitude": 41.12, "longitude": 16.87},
                },
                {
                    "entity_id": "sensor.pv_power",
                    "name": "Potenza PV",
                    "state": "900",
                },
            ]

            first_summary = learner.observe(first)
            second_summary = learner.observe(second)

            self.assertNotEqual(first_summary.site_key, second_summary.site_key)
            self.assertEqual(1, learner.summary(first_summary.site_key).samples)
            self.assertEqual(
                120.0,
                learner.summary(first_summary.site_key).averages["sensor.pv_power"],
            )
            self.assertEqual(2, second_summary.learned_sites)

    def test_unlocated_data_does_not_build_site_confidence(self):
        with TemporaryDirectory() as directory:
            learner = ContextLearner(
                MemoryStore(Path(directory) / "learning.sqlite3")
            )
            summary = learner.observe(
                [
                    {
                        "entity_id": "sensor.pv_power",
                        "name": "Potenza PV",
                        "state": "350",
                    }
                ]
            )

            self.assertEqual("unknown", summary.site_key)
            self.assertEqual(0, summary.samples)
            self.assertEqual(0.0, summary.confidence)

    def test_decision_outcome_is_bounded(self):
        with TemporaryDirectory() as directory:
            store = MemoryStore(Path(directory) / "learning.sqlite3")
            decision_id = store.add_decision(
                "site-test",
                "attendi produzione solare",
                {"soc": 40},
            )
            store.resolve_decision(decision_id, "produzione arrivata", 5)

            with store._connect() as db:
                row = db.execute(
                    "SELECT score FROM decision_outcomes WHERE id = ?",
                    (decision_id,),
                ).fetchone()
            self.assertEqual(1.0, row["score"])
