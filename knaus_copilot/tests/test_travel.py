from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from app.memory import MemoryStore
from app.travel import TravelTracker


class TravelTrackerTest(TestCase):
    def test_plan_is_extracted_from_natural_language(self):
        with TemporaryDirectory() as directory:
            tracker = TravelTracker(MemoryStore(Path(directory) / "memory.sqlite3"))
            plan = tracker.capture_plan(
                "Venerdì parto per il Camping Club degli Amici"
            )
            self.assertIsNotNone(plan)
            self.assertEqual("Camping Club degli Amici", plan["destination"])

    def test_gps_starts_trip_and_local_report_is_available(self):
        with TemporaryDirectory() as directory:
            memory = MemoryStore(Path(directory) / "memory.sqlite3")
            tracker = TravelTracker(memory)
            states = [
                {
                    "entity_id": "device_tracker.caravan",
                    "state": "not_home",
                    "attributes": {"latitude": 45.8, "longitude": 9.0},
                },
                {
                    "entity_id": "sensor.caravan_sensor_gps_velocita",
                    "name": "GPS Velocità",
                    "state": "42",
                },
            ]
            self.assertEqual("stationary", tracker.observe(states)["status"])
            self.assertEqual("started", tracker.observe(states)["status"])
            self.assertTrue(tracker.report()["available"])

    def test_csv_and_gpx_exports_are_local(self):
        with TemporaryDirectory() as directory:
            memory = MemoryStore(Path(directory) / "memory.sqlite3")
            tracker = TravelTracker(memory)
            trip_id = memory.start_trip(45.0, 9.0, "Campeggio prova")
            memory.add_trip_point(
                trip_id,
                datetime.now(timezone.utc).isoformat(),
                45.0,
                9.0,
                55,
                22,
                60,
                1015,
            )
            self.assertIn("latitude", tracker.export_csv(trip_id))
            self.assertIn("<trkpt", tracker.export_gpx(trip_id))

    def test_haversine_distance_is_reasonable(self):
        distance = TravelTracker.haversine_km(45.0, 9.0, 45.1, 9.0)
        self.assertGreater(distance, 11.0)
        self.assertLess(distance, 11.2)

    def test_dashboard_summary_has_total_partial_speed_and_stops(self):
        with TemporaryDirectory() as directory:
            memory = MemoryStore(Path(directory) / "memory.sqlite3")
            tracker = TravelTracker(memory)
            trip_id = memory.start_trip(45.0, 9.0, "Destinazione")
            memory.update_trip_progress(
                trip_id,
                distance_km=12.5,
                moving_seconds=900,
                max_speed_kmh=82,
                stop_count=2,
                stationary_since=None,
                metadata={"current_speed_kmh": 48},
            )
            summary = tracker.dashboard_summary()
            self.assertEqual(12.5, summary["total_distance_km"])
            self.assertEqual(12.5, summary["latest"]["distance_km"])
            self.assertEqual(50.0, summary["latest"]["average_speed_kmh"])
            self.assertEqual(82.0, summary["latest"]["max_speed_kmh"])
            self.assertEqual(2, summary["latest"]["stops"])
