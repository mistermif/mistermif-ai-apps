import asyncio
from datetime import datetime, timedelta, timezone
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
        self.parameters = []

    async def fridge_states(self):
        return self.states

    async def send_notification(self, service, title, message):
        self.notifications.append((service, title, message))

    async def set_fridge_fan(self, entity_id, percentage):
        self.commands.append((entity_id, percentage))

    async def set_fridge_parameter(self, entity_id, value):
        self.parameters.append((entity_id, value))
        return {"entity_id": entity_id, "value": value}


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
            state("fan.frigo_ventola_pwm", "Frigo Ventola PWM", "40", "%"),
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

    def test_observe_only_instruction_has_priority_over_missing_data(self):
        self.ha.states = self.states[:2]
        asyncio.run(self.optimizer.monitor_once())
        answer = self.optimizer.handle_message(
            "Per il momento sul frigorifero limitati ad osservare e basta, al massimo dammi suggerimenti"
        )
        self.assertIn("sola osservazione", answer)
        result = asyncio.run(self.optimizer.monitor_once())
        self.assertEqual("observing", result["status"])
        self.assertEqual("observe_only", result["user_mode"])
        self.assertFalse(result["authorized"])
        self.assertEqual([], self.ha.commands)

    def test_observe_only_is_understood_without_repeating_fridge_name(self):
        asyncio.run(self.optimizer.monitor_once())
        answer = self.optimizer.handle_message(
            "Limitati ad osservare e basta e dammi solo suggerimenti"
        )
        self.assertIn("sola osservazione", answer)
        asyncio.run(self.optimizer.monitor_once())
        followup = self.optimizer.handle_message("Come va il frigorifero?")
        self.assertIn("Modalità frigorifero: sola osservazione", followup)
        self.assertEqual(1, len(self.ha.notifications))

    def test_unrelated_location_request_is_not_intercepted_in_observe_mode(self):
        asyncio.run(self.optimizer.monitor_once())
        self.optimizer.set_observe_only()
        answer = self.optimizer.handle_message(
            "Quale posizione stai usando per consigliarmi un ristorante qui vicino?"
        )
        self.assertIsNone(answer)

    def test_semantic_interpretation_can_enable_observation_but_not_control(self):
        asyncio.run(self.optimizer.monitor_once())
        answer = self.optimizer.apply_interpreted_intent(
            {"intent": "observe_only", "confidence": 0.91}
        )
        self.assertIn("sola osservazione", answer)
        self.assertFalse(self.optimizer.public_status()["authorized"])

        answer = self.optimizer.apply_interpreted_intent(
            {"intent": "authorize_control", "confidence": 0.99}
        )
        self.assertIn("non uso un'interpretazione AI come autorizzazione", answer)
        self.assertFalse(self.optimizer.public_status()["authorized"])

    def test_low_confidence_semantics_asks_for_clarification(self):
        answer = self.optimizer.apply_interpreted_intent(
            {"intent": "observe_only", "confidence": 0.52}
        )
        self.assertIn("Non sono sicuro", answer)
        self.assertNotEqual("observe_only", self.optimizer.public_status()["user_mode"])

    def test_explicit_authorization_is_scoped_and_boosts_at_40(self):
        asyncio.run(self.optimizer.monitor_once())
        answer = self.optimizer.handle_message(
            "Il frigorifero modello Dometic RM 7655L, autorizzo la gestione delle ventole frigo"
        )
        self.assertIn("Autorizzazione registrata", answer)
        self.assertTrue(self.policy.can_control_fridge("fan.frigo_ventola_pwm"))
        self.assertFalse(self.policy.can_control_fridge("fan.inverter_cooling_ventola_destra"))

        result = asyncio.run(self.optimizer.monitor_once())
        self.assertEqual("direct_pwm:100", result["last_action"])
        self.assertEqual([("fan.frigo_ventola_pwm", 100.0)], self.ha.commands)

    def test_kill_switch_blocks_real_command(self):
        asyncio.run(self.optimizer.monitor_once())
        self.optimizer.handle_message(
            "Frigorifero modello Dometic RM 7655L, autorizzo la gestione delle ventole frigo"
        )
        self.policy.runtime_enabled = False
        result = asyncio.run(self.optimizer.monitor_once())
        self.assertEqual("control_blocked_by_autonomy", result["last_action"])
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
        self.assertTrue(self.policy.can_control_fridge("fan.frigo_ventola_pwm"))
        self.assertFalse(self.policy.can_control_fridge("fan.inverter_cooling_ventola_destra"))

    def test_inverter_cooling_cannot_be_authorized_as_fridge_fan(self):
        asyncio.run(self.optimizer.monitor_once())
        answer = self.optimizer.handle_message(
            "Frigorifero modello Dometic RM, ventola fan.inverter_cooling_ventola_frigo, autorizzo"
        )
        self.assertIn("Non autorizzo", answer)
        self.assertFalse(self.optimizer.public_status()["authorized"])

    def test_existing_local_controller_is_tuned_instead_of_forced_manual(self):
        parameter_states = []
        names = {
            "day_start_pwm": ("Frigo Giorno PWM Start", "30 %"),
            "day_start_temp": ("Frigo Giorno Temp Start", "35 °C"),
            "day_full_temp": ("Frigo Giorno Temp PWM 100", "45 °C"),
            "day_hysteresis": ("Frigo Giorno Isteresi", "2 °C"),
            "night_start_pwm": ("Frigo Notte PWM Start", "30 %"),
            "night_start_temp": ("Frigo Notte Temp Start", "38 °C"),
            "night_full_temp": ("Frigo Notte Temp PWM 100", "45 °C"),
            "night_hysteresis": ("Frigo Notte Isteresi", "2 °C"),
        }
        for key, (name, value) in names.items():
            parameter_states.append(state(f"select.frigo_{key}", name, value))
        self.ha.states = self.states[:3] + parameter_states
        asyncio.run(self.optimizer.monitor_once())
        result = self.optimizer.public_status()
        self.assertEqual("local_controller", result["control_mode"])
        answer = self.optimizer.handle_message(
            "Frigorifero modello Dometic RM 7655L, autorizzo la gestione delle ventole frigo"
        )
        self.assertIn("parametri giorno/notte", answer)

        result = asyncio.run(self.optimizer.monitor_once())
        self.assertTrue(result["last_action"].startswith("controller_tuned:"))
        changed = dict(self.ha.parameters)
        self.assertEqual(39, changed["select.frigo_day_full_temp"])
        self.assertNotIn(("fan.frigo_ventola_pwm", 100.0), self.ha.commands)

    def test_two_day_history_makes_weak_cooling_more_aggressive(self):
        start = datetime.now(timezone.utc) - timedelta(hours=48)
        for index in range(97):
            self.memory.add_learning_observation(
                "fridge:adaptive",
                {"internal_c": 8.5, "radiator_c": 36, "external_c": 28},
                observed_at=(start + timedelta(minutes=30 * index)).isoformat(),
            )
        targets = self.optimizer._controller_targets(6.5, 28)
        self.assertEqual(30, targets["day_start_temp"])
        self.assertEqual(80, targets["day_start_pwm"])
        self.assertEqual(1.0, self.optimizer.profile["learning_confidence"])

    def test_legacy_manual_pwm_authorization_is_revoked(self):
        self.memory.set_json_setting(
            "fridge_optimizer_profile",
            {
                "authorized": True,
                "status": "monitoring",
                "entities": {"fan": "number.frigo_manuale_pwm"},
            },
        )
        migrated = FridgeOptimizer(self.memory, self.ha, self.policy, "notify.notify")
        self.assertFalse(migrated.public_status()["authorized"])
        self.assertEqual("searching", migrated.public_status()["status"])
