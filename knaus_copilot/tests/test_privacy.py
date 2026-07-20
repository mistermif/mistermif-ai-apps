from unittest import TestCase

from app.privacy import PrivacyFilter


class PrivacyFilterTest(TestCase):
    def setUp(self):
        self.privacy = PrivacyFilter()

    def test_redacts_contacts_network_and_coordinates(self):
        source = (
            "Scrivi a privacy-test@example.invalid, IP 192.0.2.55, "
            "coordinate 45.123456, 9.123456 e token sk-test1234567890"
        )
        result = self.privacy.sanitize_text(source)

        self.assertNotIn("privacy-test@example.invalid", result)
        self.assertNotIn("192.0.2.55", result)
        self.assertNotIn("45.123456", result)
        self.assertNotIn("sk-test1234567890", result)

    def test_drops_location_entities(self):
        states = [
            {"entity_id": "device_tracker.caravan", "name": "GPS caravan", "state": "home"},
            {"entity_id": "sensor.temperatura_interna", "name": "Temperatura", "state": "22"},
        ]

        result = self.privacy.sanitize_states(states)

        self.assertEqual(["sensor.temperatura_interna"], [item["entity_id"] for item in result])

    def test_keeps_sensitive_memories_local(self):
        memories = [
            {"category": "viaggio", "title": "Puglia", "content": "Percorso privato"},
            {"category": "preferenza", "title": "Temperatura", "content": "Preferisco 22 C"},
        ]

        result = self.privacy.sanitize_memories(memories)

        self.assertEqual(1, len(result))
        self.assertEqual("preferenza", result[0]["category"])

    def test_contextual_cloud_keeps_location_but_removes_secrets(self):
        privacy = PrivacyFilter(allow_location=True)
        fake_key = "AIza" + ("1" * 30)
        text = (
            "Sono a 45.123456, 9.123456; "
            f"api_key={fake_key}"
        )
        result = privacy.sanitize_text(text)
        states = privacy.sanitize_states(
            [
                {
                    "entity_id": "device_tracker.caravan",
                    "name": "GPS caravan",
                    "state": "not_home",
                    "attributes": {"latitude": 45.1, "longitude": 9.1},
                }
            ]
        )

        self.assertIn("45.123456", result)
        self.assertNotIn(fake_key, result)
        self.assertEqual("device_tracker.caravan", states[0]["entity_id"])

    def test_nested_state_attributes_are_redacted_recursively(self):
        privacy = PrivacyFilter(allow_location=True)
        states = [
            {
                "entity_id": "sensor.router_diagnostics",
                "name": "Diagnostica router",
                "state": "online",
                "attributes": {
                    "network": {
                        "ip_address": "192.0.2.55",
                        "ssid": "Knaus privata",
                        "access_token": "token-di-prova-non-reale",
                    },
                    "samples": [
                        {"authorization": "Bearer test-token"},
                        {"voltage": 12.8},
                    ],
                },
            }
        ]

        attributes = privacy.sanitize_states(states)[0]["attributes"]

        self.assertEqual(
            "[DATO SENSIBILE RIMOSSO]",
            attributes["network"]["ip_address"],
        )
        self.assertEqual(
            "[DATO SENSIBILE RIMOSSO]",
            attributes["network"]["ssid"],
        )
        self.assertEqual(
            "[DATO SENSIBILE RIMOSSO]",
            attributes["network"]["access_token"],
        )
        self.assertEqual(
            "[DATO SENSIBILE RIMOSSO]",
            attributes["samples"][0]["authorization"],
        )
        self.assertEqual(12.8, attributes["samples"][1]["voltage"])
