import unittest

from app.stopover_search import (
    build_stopover_prompt,
    extract_radius_km,
    is_stopover_search,
)


class StopoverSearchTest(unittest.TestCase):
    def test_recognizes_common_stopover_requests(self):
        for message in (
            "Trovami aree di sosta gratuite",
            "Cerca un parcheggio camper",
            "Guarda su Park4night",
        ):
            with self.subTest(message=message):
                self.assertTrue(is_stopover_search(message))

    def test_does_not_capture_unrelated_parking_request(self):
        self.assertFalse(is_stopover_search("Dove ho parcheggiato l'auto?"))

    def test_extracts_and_clamps_radius(self):
        self.assertEqual(25, extract_radius_km("entro 25 km"))
        self.assertEqual(10, extract_radius_km("raggio 10"))
        self.assertEqual(2, extract_radius_km("2000 metri"))
        self.assertEqual(200, extract_radius_km("500 km"))
        self.assertEqual(15, extract_radius_km("15"))
        self.assertIsNone(extract_radius_km("vicino a me"))

    def test_prompt_requires_nearest_first_and_public_park4night(self):
        prompt = build_stopover_prompt(
            "aree gratuite",
            20,
            45.8,
            9.08,
        )
        self.assertIn("entro 20 km", prompt)
        self.assertIn("Park4night", prompt)
        self.assertIn("più vicina alla più lontana", prompt)
        self.assertIn("45.800000, 9.080000", prompt)
