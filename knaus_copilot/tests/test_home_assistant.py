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
