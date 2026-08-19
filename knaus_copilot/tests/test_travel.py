from datetime import datetime, timedelta, timezone
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
            tracker = TravelTracker(
                memory,
                base_latitude=45.8,
                base_longitude=9.0,
                base_radius_km=5,
            )
            states = [
                {
                    "entity_id": "device_tracker.caravan",
                    "state": "not_home",
                    "attributes": {"latitude": 45.86, "longitude": 9.0},
                },
                {
                    "entity_id": "sensor.caravan_sensor_gps_velocita",
                    "name": "GPS Velocità",
                    "state": "42",
                },
            ]
            self.assertEqual("departure_candidate", tracker.observe(states)["status"])
            self.assertEqual("departure_candidate", tracker.observe(states)["status"])
            self.assertEqual("started", tracker.observe(states)["status"])
            self.assertTrue(tracker.report()["available"])

    def test_stationary_gps_drift_does_not_start_or_add_distance(self):
        with TemporaryDirectory() as directory:
            memory = MemoryStore(Path(directory) / "memory.sqlite3")
            tracker = TravelTracker(
                memory,
                base_latitude=45.8,
                base_longitude=9.0,
                base_radius_km=5,
            )
            states = [
                {
                    "entity_id": "sensor.caravan_sensor_gps_latitudine",
                    "state": "45.8",
                },
                {
                    "entity_id": "sensor.caravan_sensor_gps_longitudine",
                    "state": "9.0",
                },
                {
                    "entity_id": "sensor.caravan_sensor_gps_velocita",
                    "state": "1.2",
                },
            ]
            for offset in (0, 0.001, 0.003, 0.006):
                states[0]["state"] = str(45.8 + offset)
                self.assertEqual("at_base", tracker.observe(states)["status"])
            self.assertFalse(tracker.report()["available"])

    def test_return_to_base_closes_trip_and_creates_dated_archive(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            memory = MemoryStore(root / "memory.sqlite3")
            clock = [datetime(2026, 8, 10, 8, 0, tzinfo=timezone.utc)]
            tracker = TravelTracker(
                memory,
                base_latitude=45.8,
                base_longitude=9.0,
                base_radius_km=5,
                archive_dir=root / "viaggi salvati",
                now_provider=lambda: clock[0],
            )
            states = [
                {
                    "entity_id": "device_tracker.caravan",
                    "state": "not_home",
                    "attributes": {"latitude": 45.86, "longitude": 9.0},
                },
                {
                    "entity_id": "sensor.caravan_sensor_gps_velocita",
                    "name": "GPS Velocità",
                    "state": "40",
                },
            ]
            tracker.observe(states)
            tracker.observe(states)
            self.assertEqual("started", tracker.observe(states)["status"])
            states[0]["attributes"]["latitude"] = 45.8
            self.assertEqual("return_candidate", tracker.observe(states)["status"])
            self.assertEqual("return_candidate", tracker.observe(states)["status"])
            result = tracker.observe(states)
            self.assertEqual("returned_to_base", result["status"])
            self.assertEqual("completed", tracker.report()["status"])
            archive = Path(result["archive_path"])
            self.assertEqual("2026-08-10-viaggio-1", archive.name)
            self.assertTrue((archive / "2026-08-10-viaggio-1-resoconto.md").exists())
            self.assertTrue((archive / "2026-08-10-viaggio-1.gpx").exists())

    def test_long_stop_creates_one_leg_but_keeps_journey_open(self):
        with TemporaryDirectory() as directory:
            memory = MemoryStore(Path(directory) / "memory.sqlite3")
            clock = [datetime(2026, 8, 10, 8, 0, tzinfo=timezone.utc)]
            tracker = TravelTracker(
                memory,
                base_latitude=45.8,
                base_longitude=9.0,
                base_radius_km=5,
                stop_minutes=10,
                now_provider=lambda: clock[0],
            )
            states = [
                {"entity_id": "sensor.gps_latitudine", "state": "45.86"},
                {"entity_id": "sensor.gps_longitudine", "state": "9.0"},
                {"entity_id": "sensor.gps_velocita", "state": "40"},
            ]
            tracker.observe(states)
            tracker.observe(states)
            tracker.observe(states)
            states[2]["state"] = "0"
            clock[0] += timedelta(minutes=1)
            tracker.observe(states)
            clock[0] += timedelta(minutes=11)
            self.assertEqual("stopped", tracker.observe(states)["status"])
            detail = memory.active_trip()
            self.assertIsNotNone(detail)
            self.assertEqual(1, detail["stop_count"])
            self.assertEqual(1, len(detail["metadata"]["legs"]))
            self.assertIsNotNone(detail["metadata"]["legs"][0]["ended_at"])
            for _ in range(3):
                clock[0] += timedelta(seconds=30)
                states[2]["state"] = "35"
                tracker.observe(states)
            detail = memory.active_trip()
            self.assertEqual(2, len(detail["metadata"]["legs"]))
            self.assertEqual("active", detail["status"])

    def test_base_geofence_blocks_false_departure(self):
        with TemporaryDirectory() as directory:
            memory = MemoryStore(Path(directory) / "memory.sqlite3")
            memory.set_json_setting(
                "vehicle_profile",
                {"base": {"name": "Casa", "latitude": 45.8, "longitude": 9.0, "radius_m": 250}},
            )
            tracker = TravelTracker(memory)
            states = [
                {"entity_id": "sensor.caravan_sensor_gps_latitudine", "state": "45.8"},
                {"entity_id": "sensor.caravan_sensor_gps_longitudine", "state": "9.0"},
                {"entity_id": "sensor.caravan_sensor_gps_velocita", "state": "64.6"},
            ]
            self.assertEqual("at_base", tracker.observe(states)["status"])
            for offset in (0.0002, 0.0004, 0.0006, 0.0008):
                states[0]["state"] = str(45.8 + offset)
                self.assertEqual("at_base", tracker.observe(states)["status"])
            self.assertFalse(tracker.report()["available"])

    def test_confirmed_trip_can_be_deleted(self):
        with TemporaryDirectory() as directory:
            memory = MemoryStore(Path(directory) / "memory.sqlite3")
            trip_id = memory.start_trip(45.0, 9.0)
            self.assertTrue(memory.delete_trip(trip_id))
            self.assertIsNone(memory.trip_detail(trip_id))

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
