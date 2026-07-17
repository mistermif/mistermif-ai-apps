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

    def test_no_action_is_executable_in_version_one(self):
        policy = PermissionPolicy("limited")
        self.assertFalse(policy.can_execute("set_sbu"))

