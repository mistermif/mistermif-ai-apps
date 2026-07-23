import unittest
from unittest.mock import patch

import httpx

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


class FakeReverseClient:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    async def get(self, url, **kwargs):
        self.url = url
        self.kwargs = kwargs
        return httpx.Response(
            200,
            json={
                "display_name": "Via Roma, Como, Lombardia, Italia",
                "address": {"road": "Via Roma", "city": "Como"},
            },
            request=httpx.Request("GET", url),
        )


class DashboardSnapshotTest(unittest.IsolatedAsyncioTestCase):
    async def test_local_inventory_is_not_truncated_by_cloud_context_limit(self):
        client = FakeDashboardClient(
            [
                raw(f"sensor.test_{index}", index, f"Test {index}", "W")
                for index in range(12)
            ]
            + [raw("switch.presa_esterna", "on", "Presa esterna", None)]
        )
        client.max_entities = 10

        states = await client.states()
        health = await client.health()

        self.assertEqual(13, len(states))
        self.assertIn("switch.presa_esterna", {item["entity_id"] for item in states})
        self.assertEqual(13, health["total_entities"])
        self.assertEqual(13, health["visible_entities"])
        self.assertEqual(10, health["cloud_context_limit"])

    async def test_external_ip_is_marked_sensitive_for_bridge_filtering(self):
        client = FakeDashboardClient(
            [
                raw(
                    "sensor.archer_mr600_ip_esterno",
                    "192.0.2.55",
                    "IP esterno",
                    None,
                )
            ]
        )

        states = await client.states()

        self.assertTrue(states[0]["sensitive"])

    async def test_prefers_knaus_soc_over_link_quality(self):
        client = FakeDashboardClient(
            [
                raw(
                    "sensor.batteria_knaus_link_quality",
                    100,
                    "Link quality",
                    "%",
                ),
                raw(
                    "sensor.batteria_knaus_battery_health",
                    103,
                    "Battery health",
                    "%",
                ),
                raw(
                    "sensor.livello_batteria_knaus",
                    74,
                    "livello_batteria_knaus",
                    "%",
                ),
            ]
        )
        result = await client.dashboard_snapshot()
        self.assertEqual(
            "sensor.livello_batteria_knaus",
            result["battery_soc"]["entity_id"],
        )
        self.assertEqual("74", result["battery_soc"]["state"])

    async def test_selects_relevant_metrics_without_daily_counters(self):
        client = FakeDashboardClient(
            [
                raw("sensor.batteria_knaus_soc", 82, "Batteria Knaus SOC", "%"),
                raw("sensor.batteria_knaus_corrente", -14.2, "Batteria Knaus Corrente", "A"),
                raw("sensor.batteria_knaus_tensione", 13.3, "Batteria Knaus Tensione", "V"),
                raw("sensor.batteria_knaus_potenza", -188, "Batteria Knaus Potenza", "W"),
                raw("sensor.pv_input_power", 436, "PV Input Power", "W"),
                raw("sensor.pv_energia_giornaliera", 1200, "PV Energia giornaliera", "Wh"),
                raw("sensor.pzem_power", 680, "PZEM Power", "W"),
                raw("sensor.inverter_cooling_pzem_voltage", 228, "Inverter Cooling PZEM Voltage", "V"),
                raw("sensor.inverter_cooling_pzem_current", 3.1, "Inverter Cooling PZEM Current", "A"),
                raw("sensor.inverter_load_power", 910, "Inverter Load Power", "W"),
                raw("sensor.caravan_temperatura_interna", 23.4, "Caravan Temperatura Interna", "°C"),
                raw("sensor.caravan_temperatura_esterna", 28.1, "Caravan Temperatura Esterna", "°C"),
                raw("sensor.caravan_umidita_esterna", 61, "Caravan Umidità Esterna", "%"),
                raw("sensor.barometro_pressione", 1009, "Barometro Pressione", "hPa"),
                raw("sensor.frigo_temperatura_interna", 6.2, "Frigo Temperatura Interna", "°C"),
            ]
        )
        result = await client.dashboard_snapshot()
        self.assertEqual("82", result["battery_soc"]["state"])
        self.assertEqual("-14.2", result["battery_current"]["state"])
        self.assertEqual("13.3", result["battery_voltage"]["state"])
        self.assertEqual("-188", result["battery_power"]["state"])
        self.assertEqual("sensor.pv_input_power", result["solar_power"]["entity_id"])
        self.assertEqual("sensor.pzem_power", result["grid_power"]["entity_id"])
        self.assertEqual("228", result["grid_voltage"]["state"])
        self.assertEqual("3.1", result["grid_current"]["state"])
        self.assertEqual("910", result["load_power"]["state"])
        self.assertEqual("23.4", result["internal_temperature"]["state"])
        self.assertEqual("28.1", result["external_temperature"]["state"])
        self.assertEqual("61", result["external_humidity"]["state"])
        self.assertEqual("1009", result["pressure"]["state"])

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

    async def test_reverse_geocode_returns_nearest_osm_place(self):
        fake = FakeReverseClient()
        client = FakeDashboardClient([])
        with patch("app.home_assistant.httpx.AsyncClient", return_value=fake):
            result = await client.reverse_geocode(45.81, 9.08)
        self.assertEqual("Como", result["locality"])
        self.assertIn("Via Roma", result["display_name"])
        self.assertEqual("OpenStreetMap Nominatim", result["source"])
        self.assertEqual("45.8100000", fake.kwargs["params"]["lat"])
