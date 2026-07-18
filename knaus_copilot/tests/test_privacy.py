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
