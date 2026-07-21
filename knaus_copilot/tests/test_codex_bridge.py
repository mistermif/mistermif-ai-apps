from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import IsolatedAsyncioTestCase

import httpx

from app.codex_bridge import (
    CollaborationRequest,
    CollaborationService,
    create_bridge_app,
)
from app.learning import ContextLearner
from app.memory import MemoryStore
from app.permissions import PermissionPolicy


class CodexBridgeTest(IsolatedAsyncioTestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.memory = MemoryStore(Path(self.directory.name) / "memory.sqlite3")
        self.policy = PermissionPolicy(runtime_enabled=True)

        async def states():
            return [
                {
                    "entity_id": "sensor.battery_soc",
                    "state": "78",
                    "sensitive": False,
                },
                {
                    "entity_id": "sensor.max_total_charge",
                    "state": "50",
                    "sensitive": True,
                },
            ]

        async def health():
            return {"connected": True, "visible_entities": 2}

        self.service = CollaborationService(
            memory=self.memory,
            policy=self.policy,
            learner=ContextLearner(self.memory),
            states_provider=states,
            health_provider=health,
            autonomy_provider=lambda: True,
            animals_provider=lambda: False,
            lab_mode_provider=lambda: "simulation",
        )

    def tearDown(self):
        self.directory.cleanup()

    async def test_status_omits_sensitive_entities(self):
        status = await self.service.status()

        self.assertEqual(1, len(status["visible_states"]))
        self.assertEqual(1, status["sensitive_states_omitted"])
        self.assertFalse(status["bridge_policy"]["real_actions"])

    async def test_private_endpoints_require_the_exact_token(self):
        token = "s" * 40
        app = create_bridge_app(token, self.service)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://bridge.test",
        ) as client:
            denied = await client.get("/v1/status")
            wrong = await client.get(
                "/v1/status",
                headers={"Authorization": "Bearer wrong"},
            )
            allowed = await client.get(
                "/v1/status",
                headers={"Authorization": f"Bearer {token}"},
            )

        self.assertEqual(401, denied.status_code)
        self.assertEqual(401, wrong.status_code)
        self.assertEqual(200, allowed.status_code)

    async def test_simulation_reaches_safe_consensus_without_actions(self):
        response = await self.service.collaborate(
            CollaborationRequest(
                mode="simulate",
                message="batteria al 19%, senza sole e clima acceso",
            )
        )

        self.assertEqual("agreed_in_simulation", response["consensus"]["status"])
        self.assertEqual([], response["real_actions_executed"])
        self.assertFalse(response["safety"]["bridge_can_execute"])

    async def test_protected_proposal_requires_user_authorization(self):
        response = await self.service.collaborate(
            CollaborationRequest(
                mode="proposal",
                message="Modifica i parametri BMS e riavvia Home Assistant",
            )
        )

        self.assertEqual(
            "requires_user_authorization",
            response["consensus"]["status"],
        )
        self.assertTrue(response["consensus"]["requires_user_authorization"])
        self.assertEqual([], response["real_actions_executed"])

    async def test_action_proposal_is_draft_only(self):
        response = await self.service.collaborate(
            CollaborationRequest(
                mode="proposal",
                message="Crea una nuova plancia nel workspace dedicato",
            )
        )

        self.assertEqual(
            "agreement_for_draft_only",
            response["consensus"]["status"],
        )
        self.assertTrue(response["consensus"]["requires_user_authorization"])
