import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from app.fridge_optimizer import FridgeOptimizer
from app.memory import MemoryStore
from app.permissions import PermissionPolicy


class FakeHA:
    def __init__(self, states=None):
        self.states = states or []
        self.notifications = []
        self.commands = []

    async def fridge_states(self):
        return self.states

    async def send_notification(self, service, title, message):
        self.notifications.append((service, title, message))

    async def set_fridge_fan(self, entity_id, percentage):
        self.commands.append((entity_id, percentage))


def state(entity_id, name, value, unit=None):
    return {"entity_id": entity_id, "name": name, "state": value, "unit": unit, "attributes": {}}


class FridgeOptimizerTest(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.memory = MemoryStore(Path(self.temp.name) / "memory.sqlite3")
        self.policy = PermissionPolicy(runtime_enabled=True)
        self.states = [
            state("sensor.frigo_temperatura_controllo_ventole", "Frigo Temperatura Controllo Ventole", "41", "°C"),
            state("sensor.frigo_temperatura_esterna", "Frigo Temperatura Esterna", "29", "°C"),
            state("sensor.frigo_temperatura_interna", "Frigo Temperatura Interna", "7", "°C"),
            state("number.frigo_manuale_pwm", "Frigo Manuale PWM", "40", "%"),
        ]
        self.ha = FakeHA(self.states)
        self.optimizer = FridgeOptimizer(self.memory, self.ha, self.policy, "notify.notify")

    def tearDown(self):
        self.temp.cleanup()

    def test_discovery_notifies_but_does_not_control(self):
        result = asyncio.run(self.optimizer.monitor_once())
        self.assertEqual("awaiting_details", result["status"])
        self.assertEqual(1, len(self.ha.notifications))
        self.assertEqual([], self.ha.commands)

    def test_explicit_authorization_is_scoped_and_boosts_at_40(self):
        asyncio.run(self.optimizer.monitor_once())
        answer = self.optimizer.handle_message(
            "Il frigorifero modello Dometic RM 7655L, autorizzo la gestione delle ventole frigo"
        )
        self.assertIn("Autorizzazione registrata", answer)
        self.assertTrue(self.policy.can_control_fridge("number.frigo_manuale_pwm"))
        self.assertFalse(self.policy.can_control_fridge("fan.inverter_cooling_ventola_destra"))

        result = asyncio.run(self.optimizer.monitor_once())
        self.assertEqual("fan_100", result["last_action"])
        self.assertEqual([("number.frigo_manuale_pwm", 100.0)], self.ha.commands)

    def test_kill_switch_blocks_real_command(self):
        asyncio.run(self.optimizer.monitor_once())
        self.optimizer.handle_message(
            "Frigorifero modello Dometic RM 7655L, autorizzo la gestione delle ventole frigo"
        )
        self.policy.runtime_enabled = False
        result = asyncio.run(self.optimizer.monitor_once())
        self.assertEqual("fan_100_blocked_by_autonomy", result["last_action"])
        self.assertEqual([], self.ha.commands)

    def test_authorized_profile_cannot_be_remapped_without_new_authorization(self):
        asyncio.run(self.optimizer.monitor_once())
        self.optimizer.handle_message(
            "Frigorifero modello Dometic RM 7655L, autorizzo la gestione delle ventole frigo"
        )
        answer = self.optimizer.handle_message(
            "Come va il frigorifero? ventola fan.inverter_cooling_ventola_destra"
        )
        self.assertIn("Gestione frigorifero attiva", answer)
        self.assertTrue(self.policy.can_control_fridge("number.frigo_manuale_pwm"))
        self.assertFalse(self.policy.can_control_fridge("fan.inverter_cooling_ventola_destra"))

    def test_inverter_cooling_cannot_be_authorized_as_fridge_fan(self):
        asyncio.run(self.optimizer.monitor_once())
        answer = self.optimizer.handle_message(
            "Frigorifero modello Dometic RM, ventola fan.inverter_cooling_ventola_frigo, autorizzo"
        )
        self.assertIn("Non autorizzo", answer)
        self.assertFalse(self.optimizer.public_status()["authorized"])
