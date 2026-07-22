from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from app.memory import MemoryStore
from app.weather_monitor import WeatherMonitor, WeatherRisk


class WeatherMonitorTest(TestCase):
    def test_forecast_summary_exposes_weather_and_wind(self):
        summary = WeatherMonitor.forecast_summary(
            {
                "current": {
                    "time": "2026-07-22T14:00",
                    "temperature_2m": 26.4,
                    "relative_humidity_2m": 58,
                    "apparent_temperature": 27.1,
                    "weather_code": 2,
                    "wind_speed_10m": 18.2,
                    "wind_direction_10m": 225,
                    "wind_gusts_10m": 31,
                    "surface_pressure": 1008.4,
                },
                "hourly": {
                    "precipitation_probability": [10, 20, 45],
                    "wind_gusts_10m": [31, 38, 42],
                },
            }
        )
        self.assertEqual("Parzialmente nuvoloso", summary["condition"])
        self.assertEqual("SO", summary["wind_direction"])
        self.assertEqual(42, summary["max_gust_8h_kmh"])
        self.assertEqual(45, summary["precipitation_probability_8h"])

    def test_forecast_hail_and_wind_raise_urgency(self):
        risks = WeatherMonitor.analyse_open_meteo(
            {
                "hourly": {
                    "weather_code": [1, 95, 96],
                    "wind_gusts_10m": [20, 55, 72],
                    "precipitation_probability": [10, 85, 90],
                    "showers": [0, 4, 12],
                    "cape": [100, 900, 1700],
                }
            }
        )
        assessment = WeatherMonitor.assess(risks)
        self.assertEqual("urgenza", assessment["severity"])
        self.assertIn("grandine", assessment["kinds"])
        self.assertIn("vento", assessment["kinds"])

    def test_same_event_is_not_notified_twice_but_hail_escalates(self):
        with TemporaryDirectory() as directory:
            memory = MemoryStore(Path(directory) / "memory.sqlite3")
            monitor = WeatherMonitor(memory, object(), "notify.test")
            first = WeatherMonitor.assess(
                [WeatherRisk("vento", "allerta", 50, "test", "raffiche")]
            )
            notify, _ = monitor.should_notify(first)
            self.assertTrue(notify)
            memory.set_json_setting("weather_monitor_state", first)

            notify, _ = monitor.should_notify(first)
            self.assertFalse(notify)

            worse = WeatherMonitor.assess(
                [
                    WeatherRisk("vento", "allerta", 50, "test", "raffiche"),
                    WeatherRisk("grandine", "urgenza", 85, "test", "sviluppata"),
                ]
            )
            notify, reason = monitor.should_notify(worse)
            self.assertTrue(notify)
            self.assertIn("peggiorate", reason)

    def test_dpc_hail_thresholds(self):
        self.assertEqual("emergenza", WeatherMonitor.analyse_dpc_hail(80)[0].severity)
        self.assertEqual("urgenza", WeatherMonitor.analyse_dpc_hail(50)[0].severity)
        self.assertEqual([], WeatherMonitor.analyse_dpc_hail(10))

    def test_windy_units_and_convective_risk(self):
        risks = WeatherMonitor.analyse_windy(
            {
                "units": {"gust-surface": "m*s-1"},
                "gust-surface": [10, 20],
                "past3hconvprecip-surface": [0, 9],
                "cape-surface": [500, 2600],
            }
        )
        assessment = WeatherMonitor.assess(risks)
        self.assertEqual("urgenza", assessment["severity"])
        self.assertIn("vento", assessment["kinds"])
        self.assertIn("temporale", assessment["kinds"])

    def test_external_barometer_temperature_and_humidity_are_read(self):
        observation = WeatherMonitor.extract_local_observation(
            [
                {
                    "entity_id": "sensor.caravan_sensor_esterno_temperatura",
                    "state": "23.4",
                },
                {
                    "entity_id": "sensor.caravan_sensor_esterno_umidita",
                    "state": "67",
                },
                {"entity_id": "sensor.barometro_pressione", "state": "1004.2"},
            ]
        )
        self.assertEqual(
            {"temperature": 23.4, "humidity": 67.0, "pressure": 1004.2},
            observation,
        )

    def test_falling_pressure_combined_with_external_change_is_urgent(self):
        risks = WeatherMonitor.analyse_local_trend(
            {
                "hours": 1.5,
                "pressure_delta": -3.2,
                "temperature_delta": -2.5,
                "humidity_delta": 14,
            }
        )
        self.assertEqual("urgenza", risks[0].severity)
        self.assertEqual("pressione_in_calo", risks[0].kind)

    def test_gemini_is_not_called_for_clear_or_unchanged_weather(self):
        with TemporaryDirectory() as directory:
            memory = MemoryStore(Path(directory) / "memory.sqlite3")
            monitor = WeatherMonitor(memory, object(), "notify.test")
            clear = WeatherMonitor.assess([])
            self.assertFalse(monitor.should_consult_ai(clear))
            concern = WeatherMonitor.assess(
                [WeatherRisk("vento", "allerta", 50, "test", "raffiche")]
            )
            self.assertTrue(monitor.should_consult_ai(concern))
            memory.set_json_setting(
                "weather_monitor_state", {"deterministic": concern}
            )
            self.assertFalse(monitor.should_consult_ai(concern))
