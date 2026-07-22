import unittest

from app.home_assistant import HomeAssistantClient
from app.permissions import PermissionPolicy


def raw(entity_id, value, name, unit):
    return {
        "entity_id": entity_id,
        "state": str(value),
        "attributes": {"friendly_name": name, "unit_of_measurement": unit},
        "last_updated": "2026-07-22T10:00:00+00:00",
    }


def tracker(entity_id, state, name, latitude, longitude, accuracy=None):
    attributes = {
        "friendly_name": name,
        "latitude": latitude,
        "longitude": longitude,
    }
    if accuracy is not None:
        attributes["gps_accuracy"] = accuracy
    return {
        "entity_id": entity_id,
        "state": state,
        "attributes": attributes,
        "last_updated": "2026-07-22T10:00:00+00:00",
    }


class FakeDashboardClient(HomeAssistantClient):
    def __init__(self, states):
        super().__init__("http://ha.invalid", "token", PermissionPolicy())
        self.test_states = states

    async def _raw_states(self):
        return self.test_states


class DashboardSnapshotTest(unittest.IsolatedAsyncioTestCase):
    async def test_selects_relevant_metrics_without_daily_counters(self):
        client = FakeDashboardClient(
            [
                raw("sensor.batteria_knaus_soc", 82, "Batteria Knaus SOC", "%"),
                raw("sensor.batteria_knaus_corrente", -14.2, "Batteria Knaus Corrente", "A"),
                raw("sensor.pv_input_power", 436, "PV Input Power", "W"),
                raw("sensor.pv_energia_giornaliera", 1200, "PV Energia giornaliera", "Wh"),
                raw("sensor.pzem_power", 680, "PZEM Power", "W"),
                raw("sensor.caravan_temperatura_interna", 23.4, "Caravan Temperatura Interna", "°C"),
                raw("sensor.caravan_temperatura_esterna", 28.1, "Caravan Temperatura Esterna", "°C"),
                raw("sensor.frigo_temperatura_interna", 6.2, "Frigo Temperatura Interna", "°C"),
            ]
        )
        result = await client.dashboard_snapshot()
        self.assertEqual("82", result["battery_soc"]["state"])
        self.assertEqual("-14.2", result["battery_current"]["state"])
        self.assertEqual("sensor.pv_input_power", result["solar_power"]["entity_id"])
        self.assertEqual("sensor.pzem_power", result["grid_power"]["entity_id"])
        self.assertEqual("23.4", result["internal_temperature"]["state"])
        self.assertEqual("28.1", result["external_temperature"]["state"])

    async def test_location_uses_valid_caravan_tracker_attributes(self):
        client = FakeDashboardClient(
            [tracker("device_tracker.caravan_gps", "home", "GPS Knaus", 45.81, 8.97, 6)]
        )
        result = await client.location_snapshot()
        self.assertTrue(result["available"])
        self.assertEqual(45.81, result["latitude"])
        self.assertEqual(8.97, result["longitude"])
        self.assertEqual(6.0, result["accuracy_m"])

    async def test_location_uses_separate_gps_sensors(self):
        client = FakeDashboardClient(
            [
                raw("sensor.caravan_gps_latitudine", "45,81", "GPS Latitudine Knaus", "°"),
                raw("sensor.caravan_gps_longitudine", 8.97, "GPS Longitudine Knaus", "°"),
            ]
        )
        result = await client.location_snapshot()
        self.assertTrue(result["available"])
        self.assertEqual(45.81, result["latitude"])
        self.assertEqual(8.97, result["longitude"])

    async def test_location_does_not_call_unknown_coordinates_a_fault(self):
        client = FakeDashboardClient(
            [
                raw("sensor.caravan_gps_latitudine", "unknown", "GPS Latitudine Knaus", "°"),
                raw("sensor.caravan_gps_longitudine", "unavailable", "GPS Longitudine Knaus", "°"),
            ]
        )
        result = await client.location_snapshot()
        self.assertFalse(result["available"])
        self.assertEqual("coordinate_gps_non_disponibili", result["reason"])
