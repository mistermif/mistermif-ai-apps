from unittest import TestCase

from app.permissions import PermissionPolicy


class PermissionPolicyTest(TestCase):
    def test_sensor_read_is_allowed(self):
        self.assertTrue(PermissionPolicy().can_read("sensor.livello_batteria_knaus"))

    def test_unrelated_control_is_not_readable(self):
        self.assertFalse(PermissionPolicy().can_read("switch.porta_garage"))

    def test_sensitive_parameters_are_recognized(self):
        policy = PermissionPolicy()
        self.assertTrue(
            policy.is_sensitive(
                "select.pow_hvm_2kw_12v_float_charging_voltage_lifepo4_12v"
            )
        )

    def test_observe_mode_cannot_execute_actions(self):
        self.assertFalse(PermissionPolicy("observe").can_execute("turn_off_climate"))

    def test_limited_mode_can_only_turn_off_authorized_climate(self):
        policy = PermissionPolicy("limited", "climate.caravan")
        self.assertTrue(policy.can_execute("turn_off_climate"))
        self.assertTrue(policy.can_control_entity("climate.caravan"))
        self.assertFalse(policy.can_control_entity("climate.casa"))
        self.assertFalse(policy.can_execute("set_sbu"))
