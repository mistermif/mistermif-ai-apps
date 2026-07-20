from unittest import TestCase

from app.automation_lab import (
    LabSnapshot,
    evaluate_snapshot,
    run_scenario,
    snapshot_from_home_assistant,
)


class AutomationLabTest(TestCase):
    def test_offline_sensors_never_trigger_actions(self):
        result = run_scenario("sensori_offline")

        self.assertFalse(result["conclusive"])
        self.assertEqual([], result["allowed_actions"])
        self.assertFalse(result["safety"]["real_services_called"])

    def test_critical_battery_proposes_authorized_climate_protection(self):
        result = run_scenario("batteria_critica_senza_sole")

        self.assertEqual("protect_battery", result["decision"])
        self.assertIn("turn_off_climate", result["allowed_actions"])
        self.assertEqual([], result["executed_actions"])

    def test_solar_recovery_avoids_premature_climate_shutdown(self):
        result = run_scenario("batteria_bassa_in_recupero")

        self.assertEqual("observe_recovery", result["decision"])
        self.assertNotIn("turn_off_climate", result["allowed_actions"])

    def test_external_socket_is_added_only_when_parallel(self):
        result = run_scenario("colonnina_10a_presa_esterna")

        self.assertEqual(2140, result["metrics"]["observed_grid_watts"])
        self.assertEqual("prevent_shore_trip", result["decision"])
        self.assertIn(
            "request_inverter_sbu",
            result["protected_recommendations"],
        )

    def test_animal_mode_never_turns_off_climate(self):
        result = run_scenario("animali_batteria_bassa")

        self.assertEqual("protect_climate_and_escalate", result["decision"])
        self.assertNotIn("turn_off_climate", result["allowed_actions"])
        self.assertIn("send_notification", result["allowed_actions"])

    def test_custom_snapshot_never_marks_real_actions_as_executed(self):
        result = evaluate_snapshot(
            LabSnapshot(
                battery_soc=8,
                battery_current=-80,
                grid_power=1400,
                external_power=0,
                solar_power=0,
                available_amps=6,
                climate_on=True,
                external_charge=False,
                hour=20,
            )
        )

        self.assertEqual([], result["executed_actions"])
        self.assertFalse(result["safety"]["battery_discharged_by_test"])

    def test_shadow_snapshot_uses_mapped_entities(self):
        states = [
            {"entity_id": "sensor.soc", "state": "78"},
            {"entity_id": "sensor.grid", "state": "1240"},
            {"entity_id": "sensor.solar", "state": "210"},
            {"entity_id": "sensor.battery_current", "state": "-18"},
            {"entity_id": "climate.thermal_control", "state": "cool"},
        ]
        snapshot = snapshot_from_home_assistant(
            states,
            {
                "battery_soc": "sensor.soc",
                "grid_power": "sensor.grid",
                "solar_power": "sensor.solar",
                "battery_current": "sensor.battery_current",
                "climate": "climate.thermal_control",
            },
            default_available_amps=6,
            hour=12,
        )

        self.assertTrue(snapshot.sensors_available)
        self.assertEqual(78, snapshot.battery_soc)
        self.assertEqual(1240, snapshot.grid_power)
        self.assertTrue(snapshot.climate_on)

    def test_shadow_snapshot_marks_unknown_required_sensor_unavailable(self):
        snapshot = snapshot_from_home_assistant(
            [
                {"entity_id": "sensor.soc", "state": "unknown"},
                {"entity_id": "sensor.grid", "state": "800"},
                {"entity_id": "sensor.solar", "state": "0"},
            ],
            {
                "battery_soc": "sensor.soc",
                "grid_power": "sensor.grid",
                "solar_power": "sensor.solar",
            },
        )

        self.assertFalse(snapshot.sensors_available)
