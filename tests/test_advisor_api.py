import importlib
import importlib.util
import os
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "poe2" / "quivers"
GAME_DATASET_ID = "poe2db-unknown-version-2026-08-12-task8c-fullx1"
CRAFTING_DATASET_ID = "crafting-actions-poe2-quiver-2026-08-12-research"
AFFIX_CAPACITY_DATASET_ID = "affix-capacity-poe2-2026-08-12-research"
LEAGUE = "Runes of Aldur"
AS_OF = "2026-08-11T13:30:00+00:00"


def fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


def base_request(clipboard_text: str | None = None) -> dict:
    return {
        "clipboard_text": clipboard_text if clipboard_text is not None else fixture("quiver_6_crafted_desecrated_advanced.txt"),
        "league": LEAGUE,
        "game_data_dataset_version": GAME_DATASET_ID,
        "crafting_dataset_version": CRAFTING_DATASET_ID,
        "affix_capacity_dataset_version": AFFIX_CAPACITY_DATASET_ID,
        "as_of": AS_OF,
    }


@unittest.skipIf(importlib.util.find_spec("fastapi") is None, "FastAPI is not installed")
class AdvisorApiTests(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient
        from services.api.app.dependencies import advisor as advisor_dependencies
        from services.api.app.main import app

        app.dependency_overrides.clear()
        advisor_dependencies.get_advisor_orchestrator.cache_clear()
        advisor_dependencies.get_economy_repository.cache_clear()
        advisor_dependencies.get_cached_settings.cache_clear()
        self.app = app
        self.client = TestClient(app)

    def tearDown(self):
        self.app.dependency_overrides.clear()

    def test_health(self):
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_items_parse_still_works(self):
        response = self.client.post(
            "/api/v1/items/parse",
            json={"raw_clipboard_text": fixture("quiver_6_crafted_desecrated_advanced.txt")},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["item"]["base_type"], "Primed Quiver")

    def test_advisor_analyze_exists_in_openapi(self):
        openapi = self.client.get("/openapi.json").json()

        self.assertIn("/api/v1/advisor/analyze", openapi["paths"])
        schema_names = set(openapi["components"]["schemas"])
        self.assertIn("AdvisorAnalyzeRequestDto", schema_names)
        self.assertIn("AdvisorAnalyzeResponseDto", schema_names)

    def test_valid_quiver_6_partial_response(self):
        response = self.client.post("/api/v1/advisor/analyze", json=base_request())

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "ANALYSIS_PARTIAL")
        self.assertEqual(body["context"]["league"], LEAGUE)
        self.assertEqual(body["context"]["game_data_dataset_version"], GAME_DATASET_ID)
        self.assertEqual(body["item"]["base_type"], "Primed Quiver")
        self.assertEqual(body["affix_state"]["observed_prefix_count"], 3)
        self.assertEqual(body["affix_state"]["observed_suffix_count"], 3)
        self.assertEqual(body["affix_state"]["open_prefix_count"], 0)
        self.assertEqual(body["affix_state"]["open_suffix_count"], 0)
        annulment = self._action(body, "dc:poe2:craft-action:orb-of-annulment")
        exalted = self._action(body, "dc:poe2:craft-action:exalted-orb")
        self.assertEqual(annulment["applicability"], "APPLICABLE")
        self.assertEqual(annulment["outcome_count"], 6)
        self.assertEqual(annulment["probability_completeness"], "UNKNOWN")
        self.assertFalse(annulment["expected_value"]["available"])
        self.assertEqual(exalted["applicability"], "NOT_APPLICABLE")
        self.assertEqual(body["decision"]["decision_type"], "NO_RECOMMENDATION")
        missing = {item["type"] for item in body["missing_requirements"]}
        self.assertIn("CURRENT_VALUATION_EVIDENCE_REQUIRED", missing)
        self.assertIn("PROBABILITY_EVIDENCE_REQUIRED", missing)

    def test_unsupported_item_response_is_successful(self):
        response = self.client.post("/api/v1/advisor/analyze", json=base_request(fixture("quiver_3_normal_advanced.txt")))

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "UNSUPPORTED_ITEM")
        self.assertEqual(body["item"]["rarity"], "NORMAL")
        self.assertEqual(body["actions"], [])
        self.assertIsNone(body["decision"])

    def test_empty_clipboard_returns_documented_400(self):
        response = self.client.post("/api/v1/advisor/analyze", json=base_request(""))

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"]["code"], "VALIDATION_ERROR")

    def test_configured_frontend_origin_receives_cors_preflight(self):
        response = self.client.options(
            "/api/v1/advisor/analyze",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["access-control-allow-origin"], "http://localhost:3000")
        self.assertIn("POST", response.headers["access-control-allow-methods"])

    def test_unconfigured_origin_does_not_receive_cors_allow_origin(self):
        response = self.client.options(
            "/api/v1/advisor/analyze",
            headers={
                "Origin": "https://example.invalid",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertNotIn("access-control-allow-origin", response.headers)

    def test_cors_allowed_origins_are_configurable(self):
        from fastapi.testclient import TestClient
        import services.api.app.config as api_config
        import services.api.app.main as api_main

        previous = os.environ.get("DCS_CORS_ALLOWED_ORIGINS")
        os.environ["DCS_CORS_ALLOWED_ORIGINS"] = "http://custom.local:3000"
        try:
            importlib.reload(api_config)
            api_main = importlib.reload(api_main)
            client = TestClient(api_main.app)
            response = client.options(
                "/api/v1/advisor/analyze",
                headers={
                    "Origin": "http://custom.local:3000",
                    "Access-Control-Request-Method": "POST",
                    "Access-Control-Request-Headers": "content-type",
                },
            )
        finally:
            if previous is None:
                os.environ.pop("DCS_CORS_ALLOWED_ORIGINS", None)
            else:
                os.environ["DCS_CORS_ALLOWED_ORIGINS"] = previous
            importlib.reload(api_config)
            importlib.reload(api_main)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["access-control-allow-origin"], "http://custom.local:3000")

    def test_decimal_timestamps_and_uuid_serialize_as_strings(self):
        response = self.client.post("/api/v1/advisor/analyze", json=base_request())

        body = response.json()
        self.assertTrue(body["analysis_id"].startswith("advisor-analysis-"))
        self.assertIn(body["context"]["as_of"], {AS_OF, "2026-08-11T13:30:00Z"})
        cost_line = self._action(body, "dc:poe2:craft-action:exalted-orb")["material_cost"]["lines"][0]
        self.assertIsInstance(cost_line["quantity"], str)

    def test_scenario_only_action_serialized_with_synthetic_manual_valuation(self):
        initial = self.client.post("/api/v1/advisor/analyze", json=base_request()).json()
        annulment = self._action(initial, "dc:poe2:craft-action:orb-of-annulment")
        request = base_request()
        request["current_valuation_evidence"] = self._valuation_evidence("100")
        request["outcome_valuation_evidence"] = [
            {"outcome_id": outcome_id, "evidence": self._valuation_evidence("110")}
            for outcome_id in annulment["outcome_ids"]
        ]

        response = self.client.post("/api/v1/advisor/analyze", json=request)

        self.assertEqual(response.status_code, 200)
        body = response.json()
        annulment = self._action(body, "dc:poe2:craft-action:orb-of-annulment")
        self.assertEqual(body["status"], "SCENARIO_READY")
        self.assertEqual(annulment["scenario"]["readiness"], "SCENARIO_ONLY")
        self.assertEqual(annulment["scenario"]["valued_outcome_count"], 6)
        self.assertEqual(body["decision"]["decision_type"], "NO_RECOMMENDATION")

    def test_synthetic_full_pipeline_dependency_override_serializes_ev_and_risk(self):
        self._install_synthetic_dependencies()
        initial = self.client.post("/api/v1/advisor/analyze", json=base_request()).json()
        annulment = self._action(initial, "dc:poe2:craft-action:orb-of-annulment")
        request = base_request()
        request["current_valuation_evidence"] = self._valuation_evidence("100")
        request["outcome_valuation_evidence"] = [
            {"outcome_id": outcome_id, "evidence": self._valuation_evidence("130")}
            for outcome_id in annulment["outcome_ids"]
        ]
        request["bankroll"] = {"amount": "1000", "unit": "EXALTED_ECONOMIC_UNIT"}
        request["risk_profile"] = "AGGRESSIVE"

        response = self.client.post("/api/v1/advisor/analyze", json=request)

        self.assertEqual(response.status_code, 200)
        body = response.json()
        annulment = self._action(body, "dc:poe2:craft-action:orb-of-annulment")
        self.assertEqual(body["status"], "DECISION_READY")
        self.assertEqual(body["decision"]["decision_type"], "CRAFT")
        self.assertEqual(body["risk_adjusted_decision"]["decision_type"], "CRAFT")
        self.assertTrue(annulment["expected_value"]["available"])
        self.assertEqual(annulment["expected_value"]["net_expected_value"]["amount"], "120.0000000000000000000000000")

    def test_unexpected_dependency_error_returns_5xx(self):
        from fastapi.testclient import TestClient
        from services.api.app.dependencies.advisor import get_advisor_orchestrator
        from services.api.app.main import app

        def broken():
            raise RuntimeError("synthetic dependency failure")

        app.dependency_overrides[get_advisor_orchestrator] = broken
        client = TestClient(app, raise_server_exceptions=False)
        response = client.post("/api/v1/advisor/analyze", json=base_request())

        self.assertEqual(response.status_code, 500)

    def _valuation_evidence(self, amount: str) -> dict:
        return {
            "strategy": "STRICT",
            "observations": [
                {
                    "amount": amount,
                    "currency_asset_id": "dc:poe2:economy-asset:currency:exalted-orb",
                    "external_listing_id": f"synthetic-{amount}-{index}",
                    "observed_at": AS_OF,
                    "item_summary": "synthetic test-only manual comparable",
                }
                for index in range(3)
            ],
            "notes": "synthetic test-only valuation evidence",
        }

    def _install_synthetic_dependencies(self):
        from packages.shared.donniecraftshell_contracts.advisor_orchestration import CraftAdvisorOrchestrator
        from packages.shared.donniecraftshell_contracts.affix_capacity import AffixStateResolver, load_affix_capacity_dataset
        from packages.shared.donniecraftshell_contracts.crafting_actions import CraftActionEngine, load_crafting_dataset
        from packages.shared.donniecraftshell_contracts.economy import (
            EXALTED_ASSET_ID,
            ORB_OF_ANNULMENT_ASSET_ID,
            EconomyCategory,
            EconomyQuote,
            EconomySnapshot,
            FreshnessState,
            normalized_exalted_value,
        )
        from packages.shared.donniecraftshell_contracts.economy_repository import EconomyRepository
        from packages.shared.donniecraftshell_contracts.game_data_repository import GameDataRepository
        from packages.shared.donniecraftshell_contracts.probability import OutcomeProbability, OutcomeProbabilityModel, ProbabilityCompleteness
        from services.api.app.dependencies.advisor import get_advisor_orchestrator, get_economy_repository

        class CompleteSyntheticProbabilityProvider:
            def get_probability_model(self, item, outcome_set, context=None):
                count = len(outcome_set.hypothetical_states)
                base = Decimal("1") / Decimal(count)
                probabilities = [base for _ in outcome_set.hypothetical_states]
                probabilities[-1] = Decimal("1") - sum(probabilities[:-1], Decimal("0"))
                return OutcomeProbabilityModel(
                    action_id=outcome_set.action_id,
                    source_outcome_set_id=f"{outcome_set.source_item_analysis_id}:{outcome_set.action_id}:synthetic-api-complete",
                    outcome_probabilities=tuple(
                        OutcomeProbability(state.outcome_id, probability)
                        for state, probability in zip(outcome_set.hypothetical_states, probabilities)
                    ),
                    probability_completeness=ProbabilityCompleteness.COMPLETE,
                    dataset_versions=("synthetic-api-probability-dataset",),
                    warnings=("synthetic complete probability model for API transport proof only",),
                )

        retrieved_at = datetime.fromisoformat(AS_OF)
        quote = EconomyQuote(
            asset_id=ORB_OF_ANNULMENT_ASSET_ID,
            league=LEAGUE,
            normalized_value=normalized_exalted_value("10"),
            source_native_value=Decimal("10"),
            native_reference_asset_id=EXALTED_ASSET_ID,
            source="synthetic-api-economy",
            snapshot_id="synthetic-api-economy-snapshot",
            category=EconomyCategory.CURRENCY,
            observed_at=retrieved_at,
            retrieved_at=retrieved_at,
            freshness=FreshnessState.FRESH,
        )
        economy = EconomyRepository(
            (
                EconomySnapshot(
                    snapshot_id="synthetic-api-economy-snapshot",
                    provider="synthetic-api-economy",
                    game="poe2",
                    league=LEAGUE,
                    retrieved_at=retrieved_at,
                    freshness=FreshnessState.FRESH,
                    quotes=(quote,),
                    exchange_rates=(),
                    observed_at=retrieved_at,
                ),
            )
        )
        orchestrator = CraftAdvisorOrchestrator(
            GameDataRepository.from_json_files((ROOT / "data" / "normalized" / GAME_DATASET_ID / "game_data.json",)),
            AffixStateResolver(load_affix_capacity_dataset(ROOT / "data" / "normalized" / "crafting" / AFFIX_CAPACITY_DATASET_ID / "capacity.json")),
            CraftActionEngine(load_crafting_dataset(ROOT / "data" / "normalized" / "crafting" / CRAFTING_DATASET_ID / "actions.json")),
            economy,
            probability_provider=CompleteSyntheticProbabilityProvider(),
        )
        self.app.dependency_overrides[get_economy_repository] = lambda: economy
        self.app.dependency_overrides[get_advisor_orchestrator] = lambda: orchestrator

    def _action(self, body: dict, action_id: str) -> dict:
        return next(action for action in body["actions"] if action["action_id"] == action_id)


if __name__ == "__main__":
    unittest.main()
