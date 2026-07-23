from unittest import TestCase

from app.permissions import PermissionPolicy


class PermissionPolicyTest(TestCase):
    def test_sensor_read_is_allowed(self):
        self.assertTrue(PermissionPolicy().can_read("sensor.livello_batteria_knaus"))

    def test_complete_inventory_is_readable_without_authorizing_control(self):
        policy = PermissionPolicy()
        self.assertTrue(policy.can_read("switch.porta_garage"))
        self.assertFalse(policy.can_control_entity("switch.porta_garage"))

    def test_sensitive_parameters_are_recognized(self):
        policy = PermissionPolicy()
        self.assertTrue(
            policy.is_sensitive(
                "select.pow_hvm_2kw_12v_float_charging_voltage_lifepo4_12v"
            )
        )
        self.assertTrue(
            policy.is_sensitive(
                "sensor.archer_mr600_ip_esterno",
                "Indirizzo IP pubblico",
            )
        )
        self.assertTrue(policy.is_sensitive("sensor.roulotte_ip_wan"))
        self.assertTrue(policy.is_sensitive("sensor.roulotte_ip_locale"))
        self.assertTrue(policy.is_sensitive("device_tracker.iphone_mirco"))
        self.assertTrue(policy.is_sensitive("camera.roulotte"))
        self.assertFalse(policy.is_sensitive("device_tracker.caravan"))

    def test_observe_mode_cannot_execute_actions(self):
        self.assertFalse(PermissionPolicy("observe").can_execute("turn_off_climate"))

    def test_limited_mode_can_only_turn_off_authorized_climate(self):
        policy = PermissionPolicy("limited", "climate.caravan", runtime_enabled=True)
        self.assertTrue(policy.can_execute("turn_off_climate"))
        self.assertTrue(policy.can_control_entity("climate.caravan"))
        self.assertFalse(policy.can_control_entity("climate.casa"))
        self.assertFalse(policy.can_execute("set_sbu"))

    def test_runtime_switch_enables_and_blocks_authorized_control(self):
        policy = PermissionPolicy("observe", "climate.caravan")
        self.assertFalse(policy.can_execute("turn_off_climate"))

        policy.runtime_enabled = True
        self.assertTrue(policy.can_control_entity("climate.caravan"))

        policy.runtime_enabled = False
        self.assertFalse(policy.can_execute("turn_off_climate"))

    def test_fridge_control_is_exact_and_requires_runtime_switch(self):
        policy = PermissionPolicy(runtime_enabled=True)
        policy.authorize_fridge_control(
            {"number.frigo_pwm", "fan.inverter_cooling_ventola_frigo"}
        )
        self.assertTrue(policy.can_control_fridge("number.frigo_pwm"))
        self.assertFalse(policy.can_control_fridge("fan.inverter_cooling"))
        policy.runtime_enabled = False
        self.assertFalse(policy.can_control_fridge("number.frigo_pwm"))
