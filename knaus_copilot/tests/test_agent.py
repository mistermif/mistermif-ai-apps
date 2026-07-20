import unittest
from unittest.mock import AsyncMock, Mock, call, patch

import httpx

from app.agent import GEMINI_FALLBACK_MODEL, KnausAgent


class FakeAsyncClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.urls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    async def post(self, url, **kwargs):
        self.urls.append(url)
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
        self.assertEqual(4, len(client.urls))
        self.assertTrue(
            client.urls[-1].endswith(
                f"/models/{GEMINI_FALLBACK_MODEL}:generateContent"
            )
        )
        self.assertEqual([call(1.0), call(2.0)], sleep.await_args_list)

    async def test_reports_clear_error_when_primary_and_fallback_are_down(self):
        client = FakeAsyncClient([response(503) for _ in range(5)])
        with (
            patch("app.agent.httpx.AsyncClient", return_value=client),
            patch("app.agent.asyncio.sleep", AsyncMock()),
        ):
            with self.assertRaisesRegex(RuntimeError, "temporaneamente sovraccarico"):
                await self.make_agent()._gemini(
                    [{"role": "user", "content": "prova"}],
                    web_search=False,
                )

    async def test_search_does_not_fallback_to_unsupported_free_grounding(self):
        client = FakeAsyncClient([response(503) for _ in range(3)])
        with (
            patch("app.agent.httpx.AsyncClient", return_value=client),
            patch("app.agent.asyncio.sleep", AsyncMock()),
        ):
            with self.assertRaisesRegex(RuntimeError, "temporaneamente sovraccarico"):
                await self.make_agent()._gemini(
                    [{"role": "user", "content": "meteo"}],
                    web_search=True,
                )

        self.assertEqual(3, len(client.urls))
        self.assertTrue(all(GEMINI_FALLBACK_MODEL not in url for url in client.urls))
