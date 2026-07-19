from unittest import TestCase

from app.alerts import AlertLevel, public_alert_catalog


class AlertCatalogTest(TestCase):
    def test_three_levels_have_expected_response_windows(self):
        catalog = public_alert_catalog()

        self.assertEqual(
            ["emergenza", "urgenza", "allerta"],
            [item["level"] for item in catalog],
        )
        self.assertEqual(0, catalog[0]["response_window_minutes"])
        self.assertEqual(15, catalog[1]["response_window_minutes"])
        self.assertIsNone(catalog[2]["response_window_minutes"])
        self.assertFalse(catalog[2]["intervention_required"])
