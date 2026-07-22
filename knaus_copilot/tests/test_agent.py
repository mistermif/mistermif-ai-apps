import unittest
from unittest.mock import AsyncMock, Mock, call, patch

import httpx

from app.agent import (
    GEMINI_FALLBACK_MODEL,
    GEMINI_SEARCH_FALLBACK_MODELS,
    KnausAgent,
    SYSTEM_INSTRUCTIONS,
    asks_for_location,
)


class LocationIntentTest(unittest.TestCase):
    def test_natural_location_questions_are_recognized(self):
        questions = (
            "Sai dirmi dove ti trovi?",
            "Dove sei?",
            "Dove si trova la caravan?",
            "Vedi correttamente il GPS?",
            "Puoi dirmi dove si trova con la posizione precisa?",
            "Localizzami",
        )
        for question in questions:
            with self.subTest(question=question):
                self.assertTrue(asks_for_location(question))

    def test_unrelated_where_question_is_not_location(self):
        self.assertFalse(asks_for_location("Dove posso comprare gli pneumatici?"))


class FakeAsyncClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.urls = []
        self.requests = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    async def post(self, url, **kwargs):
        self.urls.append(url)
        self.requests.append(kwargs)
        return self.responses.pop(0)


def response(status_code, payload=None):
    return httpx.Response(
        status_code,
        json=payload or {},
        request=httpx.Request("POST", "https://example.invalid"),
    )


class GeminiFallbackTests(unittest.IsolatedAsyncioTestCase):
    def make_agent(self):
        return KnausAgent(
            api_key="test-key",
            model="gemini-3.5-flash",
            memory=Mock(),
            policy=Mock(),
            privacy_mode="contextual_cloud",
            provider="gemini",
            base_url="https://generativelanguage.googleapis.com/v1beta",
        )

    async def test_retries_primary_then_uses_free_fallback(self):
        client = FakeAsyncClient(
            [
                response(503),
                response(503),
                response(
                    200,
                    {
                        "candidates": [
                            {"content": {"parts": [{"text": "Gemini operativo"}]}}
                        ]
                    },
                ),
            ]
        )
        sleep = AsyncMock()
        with (
            patch("app.agent.httpx.AsyncClient", return_value=client),
            patch("app.agent.asyncio.sleep", sleep),
        ):
            answer = await self.make_agent()._gemini(
                [{"role": "user", "content": "prova"}],
                web_search=False,
            )

        self.assertEqual("Gemini operativo", answer)
        self.assertEqual(3, len(client.urls))
        self.assertTrue(
            client.urls[-1].endswith(
                f"/models/{GEMINI_FALLBACK_MODEL}:generateContent"
            )
        )
        self.assertEqual([call(1.0)], sleep.await_args_list)

    async def test_reports_clear_error_when_primary_and_fallback_are_down(self):
        client = FakeAsyncClient([response(503) for _ in range(3)])
        with (
            patch("app.agent.httpx.AsyncClient", return_value=client),
            patch("app.agent.asyncio.sleep", AsyncMock()),
        ):
            with self.assertRaisesRegex(RuntimeError, "temporaneamente sovraccarico"):
                await self.make_agent()._gemini(
                    [{"role": "user", "content": "prova"}],
                    web_search=False,
                )

    async def test_search_falls_back_to_free_grounding_model(self):
        client = FakeAsyncClient(
            [
                response(429),
                response(429),
                response(404),
                response(
                    200,
                    {
                        "candidates": [
                            {"content": {"parts": [{"text": "Soste trovate"}]}}
                        ]
                    },
                ),
            ]
        )
        with (
            patch("app.agent.httpx.AsyncClient", return_value=client),
            patch("app.agent.asyncio.sleep", AsyncMock()),
        ):
            answer = await self.make_agent()._gemini(
                [{"role": "user", "content": "soste"}],
                web_search=True,
                thinking_level="medium",
            )

        self.assertEqual("Soste trovate", answer)
        self.assertEqual(4, len(client.urls))
        self.assertIn(GEMINI_SEARCH_FALLBACK_MODELS[1], client.urls[-1])
        self.assertNotIn(
            "thinkingConfig",
            client.requests[-1]["json"]["generationConfig"],
        )

    async def test_short_chat_uses_fast_lite_model_with_minimal_thinking(self):
        client = FakeAsyncClient(
            [
                response(
                    200,
                    {
                        "candidates": [
                            {"content": {"parts": [{"text": "Sì, sono connesso."}]}}
                        ]
                    },
                )
            ]
        )
        with patch("app.agent.httpx.AsyncClient", return_value=client):
            answer = await self.make_agent()._gemini(
                [{"role": "user", "content": "sei connesso?"}],
                web_search=False,
                thinking_level="minimal",
            )

        self.assertEqual("Sì, sono connesso.", answer)
        self.assertIn(GEMINI_FALLBACK_MODEL, client.urls[0])
        generation = client.requests[0]["json"]["generationConfig"]
        self.assertEqual(192, generation["maxOutputTokens"])

    async def test_weather_review_is_one_compact_json_call(self):
        client = FakeAsyncClient(
            [
                response(
                    200,
                    {
                        "candidates": [
                            {
                                "content": {
                                    "parts": [
                                        {
                                            "text": (
                                                '{"severity":"urgenza","worsening":true,'
                                                '"confidence":0.82,"summary":"Pressione in calo",'
                                                '"recommendations":["Chiudi il tendalino"]}'
                                            )
                                        }
                                    ]
                                }
                            }
                        ]
                    },
                )
            ]
        )
        with patch("app.agent.httpx.AsyncClient", return_value=client):
            result = await self.make_agent().evaluate_weather(
                {"severity": "allerta", "risks": []},
                {"pressure": 999, "trend": {"pressure_delta": -4}},
            )
        self.assertEqual("urgenza", result["severity"])
        self.assertEqual(1, len(client.urls))
        generation = client.requests[0]["json"]["generationConfig"]
        self.assertEqual("application/json", generation["responseMimeType"])

    async def test_fridge_intent_uses_structured_gemini_without_authorizing(self):
        client = FakeAsyncClient(
            [
                response(
                    200,
                    {
                        "candidates": [{"content": {"parts": [{"text": (
                            '{"intent":"observe_only","confidence":0.94,'
                            '"reason":"Vuole solo monitoraggio"}'
                        )}]}}]
                    },
                )
            ]
        )
        agent = self.make_agent()
        with patch("app.agent.httpx.AsyncClient", return_value=client):
            result = await agent.interpret_fridge_intent(
                "Per adesso lascialo stare e dimmi solo se noti problemi",
                {"status": "awaiting_details", "authorized": False, "missing": ["internal"]},
            )
        self.assertEqual("observe_only", result["intent"])
        self.assertEqual(0.94, result["confidence"])
        schema = client.requests[0]["json"]["generationConfig"]["responseSchema"]
        self.assertIn("authorize_control", schema["properties"]["intent"]["enum"])

    async def test_minimal_chat_does_not_send_old_memories_or_history(self):
        memory = Mock()
        memory.recent_messages.return_value = [
            {"role": "user", "content": "Ciao, sei connesso?"}
        ]
        memory.list_memories.return_value = [
            {
                "category": "pneumatici",
                "title": "Vecchio controllo",
                "content": "Ricordare la pressione",
            }
        ]
        policy = Mock()
        policy.public_summary.return_value = {"mode": "observe"}
        agent = KnausAgent(
            api_key="test-key",
            model="gemini-3.5-flash",
            memory=memory,
            policy=policy,
            privacy_mode="contextual_cloud",
            provider="gemini",
            base_url="https://generativelanguage.googleapis.com/v1beta",
        )
        agent._gemini = AsyncMock(return_value="Sì, sono connesso.")

        answer = await agent.chat(
            "mirco",
            "Ciao, sei connesso?",
            [{"entity_id": "sensor.batteria_soc", "state": "80"}],
        )

        self.assertEqual("Sì, sono connesso.", answer)
        memory.list_memories.assert_not_called()
        conversation = agent._gemini.await_args.args[0]
        self.assertEqual(1, len(conversation))
        self.assertNotIn("pneumatici", conversation[0]["content"])
        self.assertIn('"memories": []', conversation[0]["content"])

    def test_thinking_level_follows_request_complexity(self):
        agent = self.make_agent()
        self.assertEqual("minimal", agent._thinking_level("Ciao, sei connesso?"))
        self.assertEqual(
            "low",
            agent._thinking_level("Mi puoi spiegare come stai funzionando oggi?"),
        )
        self.assertEqual(
            "low",
            agent._thinking_level("Come sta la caravan?"),
        )
        self.assertEqual(
            "medium",
            agent._thinking_level(
                "Analizza la batteria e prepara una strategia energetica."
            ),
        )

    def test_simple_chat_sends_no_sensor_dump(self):
        agent = self.make_agent()
        states = [
            {"entity_id": "sensor.batteria_soc", "name": "Batteria SOC"},
            {"entity_id": "sensor.temperatura", "name": "Temperatura"},
        ]
        self.assertEqual(
            [],
            agent._select_states(states, "Ciao, sei connesso?", "minimal"),
        )

    def test_energy_question_keeps_only_relevant_states(self):
        agent = self.make_agent()
        states = [
            {"entity_id": "sensor.batteria_soc", "name": "Batteria SOC"},
            {"entity_id": "sensor.inverter_power", "name": "Potenza inverter"},
            {"entity_id": "sensor.porta", "name": "Porta ingresso"},
        ]
        selected = agent._select_states(
            states,
            "Analizza energia e batteria",
            "medium",
        )
        self.assertEqual(
            {"sensor.batteria_soc", "sensor.inverter_power"},
            {item["entity_id"] for item in selected},
        )

    def test_location_dependent_advice_keeps_gps_context(self):
        agent = self.make_agent()
        states = [
            {
                "entity_id": "device_tracker.caravan_gps",
                "name": "GPS Knaus",
                "attributes": {"latitude": 45.8, "longitude": 8.96},
            },
            {"entity_id": "sensor.batteria_soc", "name": "Batteria SOC"},
        ]
        for question in (
            "Consigliami un ristorante qui vicino",
            "Che meteo è previsto in questa zona?",
            "Cerca un campeggio nei dintorni",
            "Quali coordinate numeriche hai ricevuto nel contesto?",
        ):
            with self.subTest(question=question):
                selected = agent._select_states(states, question, "low")
                self.assertIn(
                    "device_tracker.caravan_gps",
                    {item["entity_id"] for item in selected},
                )

    def test_system_prompt_does_not_treat_offline_data_as_an_emergency(self):
        self.assertIn(
            "da solo non dimostra un guasto, un pericolo o un'emergenza",
            SYSTEM_INSTRUCTIONS,
        )
        self.assertIn("Per pneumatici e TPMS", SYSTEM_INSTRUCTIONS)
