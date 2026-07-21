from unittest import TestCase

from app.conversational_simulator import (
    is_simulation_request,
    run_conversational_simulation,
)


class ConversationalSimulatorTest(TestCase):
    def test_normal_chat_is_not_intercepted(self):
        self.assertFalse(is_simulation_request("Ciao, sei connesso?"))

    def test_ambiguous_simulation_asks_for_energy_context(self):
        simulation = run_conversational_simulation("Puoi fare una simulazione?")

        self.assertEqual("clarification", simulation["kind"])
        self.assertIn("SOC", simulation["answer"])

    def test_custom_battery_request_is_parsed_and_self_checked(self):
        simulation = run_conversational_simulation(
            "Simula batteria al 19%, senza sole, corrente batteria -42 A e clima acceso"
        )

        self.assertIsNotNone(simulation)
        self.assertEqual("single", simulation["kind"])
        self.assertEqual(19, simulation["snapshot"]["battery_soc"])
        self.assertEqual(-42, simulation["snapshot"]["battery_current"])
        self.assertEqual("protect_battery", simulation["result"]["decision"])
        self.assertTrue(simulation["assessment"]["passed"])
        self.assertEqual([], simulation["result"]["executed_actions"])

    def test_custom_shore_request_adds_external_socket(self):
        simulation = run_conversational_simulation(
            "Simula colonnina 10 A, PZEM 720 W e presa esterna 1420 W"
        )

        self.assertEqual(10, simulation["snapshot"]["available_amps"])
        self.assertTrue(simulation["snapshot"]["external_socket_parallel"])
        self.assertEqual(2140, simulation["result"]["metrics"]["observed_grid_watts"])
        self.assertEqual("prevent_shore_trip", simulation["result"]["decision"])

    def test_animals_keep_climate_protected(self):
        simulation = run_conversational_simulation(
            "Simula batteria al 18%, niente sole, clima acceso e cani a bordo"
        )

        self.assertEqual(
            "protect_climate_and_escalate",
            simulation["result"]["decision"],
        )
        self.assertNotIn(
            "turn_off_climate",
            simulation["result"]["allowed_actions"],
        )
        self.assertTrue(simulation["assessment"]["passed"])

    def test_full_self_check_compares_all_known_scenarios(self):
        simulation = run_conversational_simulation(
            "Fai un test completo di tutte le simulazioni energetiche"
        )

        self.assertEqual("full", simulation["kind"])
        self.assertTrue(simulation["passed"])
        self.assertEqual(6, simulation["passed_count"])
        self.assertEqual(6, simulation["total"])
