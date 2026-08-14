import copy
import importlib
import importlib.util
import json
import os
import tempfile
import unittest
from dataclasses import replace
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
        self._previous_registry_path = os.environ.get("DCS_EMPIRICAL_REGISTRY_PATH")
        os.environ["DCS_EMPIRICAL_REGISTRY_PATH"] = "disabled"
        from fastapi.testclient import TestClient
        from services.api.app.dependencies import advisor as advisor_dependencies
        from services.api.app.main import app

        app.dependency_overrides.clear()
        advisor_dependencies.get_advisor_orchestrator.cache_clear()
        advisor_dependencies.get_economy_repository.cache_clear()
        advisor_dependencies.get_probability_provider.cache_clear()
        advisor_dependencies.get_empirical_probability_registry.cache_clear()
        advisor_dependencies.get_cached_settings.cache_clear()
        self.app = app
        self.client = TestClient(app)

    def tearDown(self):
        self.app.dependency_overrides.clear()
        if self._previous_registry_path is None:
            os.environ.pop("DCS_EMPIRICAL_REGISTRY_PATH", None)
        else:
            os.environ["DCS_EMPIRICAL_REGISTRY_PATH"] = self._previous_registry_path

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
        self.assertIn("/api/v1/observations/record", openapi["paths"])
        schema_names = set(openapi["components"]["schemas"])
        self.assertIn("AdvisorAnalyzeRequestDto", schema_names)
        self.assertIn("AdvisorAnalyzeResponseDto", schema_names)
        self.assertIn("ProbabilitySummaryDto", schema_names)
        self.assertIn("CraftObservationRecordRequestDto", schema_names)
        self.assertIn("/api/v1/observations/review", openapi["paths"])
        self.assertIn("/api/v1/observations/build-empirical-datasets", openapi["paths"])
        self.assertIn("/api/v1/observations/empirical-datasets", openapi["paths"])
        self.assertIn("/api/v1/observations/empirical-datasets/register", openapi["paths"])
        self.assertIn("ObservationReviewRequestDto", schema_names)
        self.assertIn("ObservationReviewResponseDto", schema_names)
        self.assertIn("CuratedObservationBuildRequestDto", schema_names)
        self.assertIn("CuratedObservationBuildResponseDto", schema_names)
        self.assertIn("EmpiricalDatasetRegisterRequestDto", schema_names)
        self.assertIn("EmpiricalDatasetRegisterResponseDto", schema_names)
        self.assertIn("EmpiricalDatasetListResponseDto", schema_names)

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
        self.assertEqual(annulment["probability"]["completeness"], "UNKNOWN")
        self.assertEqual(annulment["probability"]["known_outcome_count"], 0)
        self.assertTrue(
            all(item["probability"] is None for item in annulment["probability"]["outcome_probabilities"])
        )
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

    def test_empirical_probability_dataset_version_is_serialized(self):
        request = base_request()
        request["empirical_probability_dataset_version"] = "synthetic-api-empirical-dataset"

        response = self.client.post("/api/v1/advisor/analyze", json=request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["context"]["empirical_probability_dataset_version"],
            "synthetic-api-empirical-dataset",
        )

    def test_default_dependency_assembly_skips_synthetic_empirical_fixtures(self):
        from services.api.app.dependencies import advisor as advisor_dependencies

        previous = os.environ.get("DCS_EMPIRICAL_PROBABILITY_DATASET_PATHS")
        os.environ["DCS_EMPIRICAL_PROBABILITY_DATASET_PATHS"] = str(
            ROOT / "data" / "raw" / "probability" / "synthetic_empirical_annulment_outcomes.json"
        )
        try:
            advisor_dependencies.get_cached_settings.cache_clear()
            advisor_dependencies.get_probability_provider.cache_clear()
            advisor_dependencies.get_empirical_probability_registry.cache_clear()
            registry = advisor_dependencies.get_empirical_probability_registry()
        finally:
            if previous is None:
                os.environ.pop("DCS_EMPIRICAL_PROBABILITY_DATASET_PATHS", None)
            else:
                os.environ["DCS_EMPIRICAL_PROBABILITY_DATASET_PATHS"] = previous
            advisor_dependencies.get_cached_settings.cache_clear()
            advisor_dependencies.get_probability_provider.cache_clear()
            advisor_dependencies.get_empirical_probability_registry.cache_clear()

        self.assertEqual(registry.list_summaries(), ())

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

    def test_synthetic_empirical_probability_flows_through_api_response(self):
        self._install_synthetic_empirical_dependencies()
        initial = self.client.post("/api/v1/advisor/analyze", json=base_request()).json()
        annulment = self._action(initial, "dc:poe2:craft-action:orb-of-annulment")
        request = base_request()
        request["empirical_probability_dataset_version"] = "synthetic-api-empirical-probability"
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
        self.assertEqual(annulment["probability"]["completeness"], "COMPLETE")
        self.assertEqual(annulment["probability"]["known_outcome_count"], annulment["outcome_count"])
        self.assertEqual(annulment["probability"]["outcome_probabilities"][0]["evidence"][0]["probability_type"], "EMPIRICAL_ESTIMATE")
        self.assertEqual(annulment["probability"]["outcome_probabilities"][0]["evidence"][0]["sample_size"], 60)
        self.assertIsInstance(annulment["probability"]["outcome_probabilities"][0]["probability"], str)
        self.assertTrue(annulment["expected_value"]["available"])
        self.assertEqual(body["decision"]["decision_type"], "CRAFT")

    def test_context_incompatible_empirical_probability_surfaces_unknown_warning(self):
        self._install_synthetic_empirical_dependencies()
        request = base_request()
        request["empirical_probability_dataset_version"] = "synthetic-api-empirical-probability"
        request["league"] = "Different League"

        response = self.client.post("/api/v1/advisor/analyze", json=request)

        self.assertEqual(response.status_code, 200)
        annulment = self._action(response.json(), "dc:poe2:craft-action:orb-of-annulment")
        self.assertEqual(annulment["probability"]["completeness"], "UNKNOWN")
        self.assertTrue(any("does not match" in warning for warning in annulment["warnings"]))

    def test_observation_record_endpoint_exports_importer_compatible_record(self):
        from packages.shared.donniecraftshell_contracts.empirical_observation_import import (
            ObservationImportBatch,
            aggregate_observations,
            empirical_observation_from_dict,
        )

        before = fixture("quiver_6_crafted_desecrated_advanced.txt")
        removed_raw = (
            '{ Prefix Modifier "Entombing" (Tier: 1) — Damage, Elemental, Cold, Attack }\n'
            "Adds 22(21-24) to 37(32-37) Cold damage to Attacks"
        )
        after = before.replace(
            removed_raw + "\n",
            "",
        )
        response = self.client.post(
            "/api/v1/observations/record",
            json={
                "before_clipboard_text": before,
                "after_clipboard_text": after,
                "action_id": "dc:poe2:craft-action:orb-of-annulment",
                "source_outcome_set_id": "analysis-test:dc:poe2:craft-action:orb-of-annulment",
                "item_class": "Quivers",
                "league": LEAGUE,
                "observed_at": AS_OF,
                "source_id": "api-test-recorder",
                "game_version": "synthetic-test-version",
                "crafting_dataset_version": CRAFTING_DATASET_ID,
                "modifier_dataset_version": GAME_DATASET_ID,
                "synthetic": True,
                "outcome_candidates": [
                    {
                        "outcome_id": "outcome-entombing-removed",
                        "removed_modifier_raw_text": removed_raw,
                    }
                ],
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["classification"]["method"], "AUTOMATIC")
        self.assertTrue(body["classification"]["outcome_id"].startswith("outcome-"))
        self.assertNotEqual(body["classification"]["outcome_id"], "outcome-entombing-removed")
        observation = empirical_observation_from_dict(body["export_record"])
        self.assertEqual(observation.raw_record_id, body["raw_record_id"])
        result = aggregate_observations(ObservationImportBatch((observation,)))
        self.assertEqual(result.accepted_record_count, 1)

    def test_fabricated_client_outcome_candidate_cannot_create_automatic_classification(self):
        before = fixture("quiver_6_crafted_desecrated_advanced.txt")
        removed_raw = (
            '{ Prefix Modifier "Entombing" (Tier: 1) — Damage, Elemental, Cold, Attack }\n'
            "Adds 22(21-24) to 37(32-37) Cold damage to Attacks"
        )
        response = self.client.post(
            "/api/v1/observations/record",
            json={
                "before_clipboard_text": before,
                "after_clipboard_text": before.replace(removed_raw + "\n", ""),
                "action_id": "dc:poe2:craft-action:orb-of-annulment",
                "source_outcome_set_id": "analysis-test:dc:poe2:craft-action:orb-of-annulment",
                "item_class": "Quivers",
                "league": LEAGUE,
                "observed_at": AS_OF,
                "outcome_candidates": [
                    {
                        "outcome_id": "fabricated-client-outcome-id",
                        "removed_modifier_raw_text": removed_raw,
                    }
                ],
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["classification"]["method"], "AUTOMATIC")
        self.assertNotEqual(body["classification"]["outcome_id"], "fabricated-client-outcome-id")

    def test_fabricated_source_outcome_set_id_is_not_exported_as_trusted_context(self):
        before = fixture("quiver_6_crafted_desecrated_advanced.txt")
        removed_raw = (
            '{ Prefix Modifier "Entombing" (Tier: 1) — Damage, Elemental, Cold, Attack }\n'
            "Adds 22(21-24) to 37(32-37) Cold damage to Attacks"
        )
        response = self.client.post(
            "/api/v1/observations/record",
            json={
                "before_clipboard_text": before,
                "after_clipboard_text": before.replace(removed_raw + "\n", ""),
                "action_id": "dc:poe2:craft-action:orb-of-annulment",
                "source_outcome_set_id": "fabricated-client-source-outcome-set",
                "item_class": "Quivers",
                "league": LEAGUE,
                "observed_at": AS_OF,
                "crafting_dataset_version": CRAFTING_DATASET_ID,
                "modifier_dataset_version": GAME_DATASET_ID,
            },
        )

        self.assertEqual(response.status_code, 200)
        exported = response.json()["export_record"]
        self.assertNotEqual(exported["source_outcome_set_id"], "fabricated-client-source-outcome-set")
        self.assertTrue(exported["source_outcome_set_id"].startswith("backend-outcome-set:"))
        self.assertEqual(exported["crafting_dataset_version"], CRAFTING_DATASET_ID)
        self.assertEqual(exported["modifier_dataset_version"], GAME_DATASET_ID)

    def test_observation_review_endpoint_exports_only_accepted_records(self):
        from packages.shared.donniecraftshell_contracts.empirical_observation_import import (
            ObservationImportBatch,
            aggregate_observations,
            empirical_observation_from_dict,
        )

        accepted = self._observation_export_record("manual-craft-observation-api-accepted", "outcome-api-1")
        rejected = self._observation_export_record("manual-craft-observation-api-rejected", "outcome-api-2")

        response = self.client.post(
            "/api/v1/observations/review",
            json={
                "batches": [{"observations": [accepted, rejected]}],
                "decisions": [
                    {
                        "raw_record_id": accepted["raw_record_id"],
                        "status": "ACCEPTED",
                        "note": "reviewed from screenshot",
                    },
                    {
                        "raw_record_id": rejected["raw_record_id"],
                        "status": "REJECTED",
                        "note": "wrong context",
                    },
                ],
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["accepted_export"]["observations"], [accepted])
        self.assertEqual(body["review_manifest"]["accepted_count"], 1)
        self.assertEqual(body["review_manifest"]["rejected_count"], 1)
        self.assertEqual(body["review_manifest"]["records"][1]["note"], "wrong context")
        imported = tuple(empirical_observation_from_dict(record) for record in body["accepted_export"]["observations"])
        result = aggregate_observations(ObservationImportBatch(imported))
        self.assertEqual(result.accepted_record_count, 1)

    def test_observation_review_endpoint_surfaces_invalid_records_and_absent_decisions(self):
        response = self.client.post(
            "/api/v1/observations/review",
            json={
                "observations": [{"raw_record_id": "manual-craft-observation-api-malformed"}],
                "decisions": [
                    {
                        "raw_record_id": "manual-craft-observation-api-malformed",
                        "status": "ACCEPTED",
                    },
                    {
                        "raw_record_id": "manual-craft-observation-api-absent",
                        "status": "REJECTED",
                    },
                ],
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["accepted_export"]["observations"], [])
        self.assertFalse(body["records"][0]["valid_for_import"])
        self.assertFalse(body["records"][0]["exported"])
        self.assertTrue(any("Task 15C import validation failed" in warning for warning in body["records"][0]["warnings"]))
        self.assertTrue(any("manual-craft-observation-api-absent" in warning for warning in body["warnings"]))

    def test_curated_observation_build_endpoint_aggregates_accepted_export(self):
        accepted = self._observation_export_record("manual-craft-observation-build-accepted", "outcome-api-1")
        unclassified = self._observation_export_record("manual-craft-observation-build-unclassified", None)
        unclassified["unclassified"] = True

        response = self.client.post(
            "/api/v1/observations/build-empirical-datasets",
            json={
                "accepted_export": {
                    "review_version": "dc-observation-review-v1",
                    "observations": [accepted, unclassified],
                    "warnings": ["review warning carried forward"],
                },
                "dataset_id_prefix": "api-curated-test",
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["source_record_count"], 2)
        self.assertEqual(body["imported_record_count"], 2)
        self.assertEqual(body["accepted_record_count"], 2)
        self.assertEqual(body["unclassified_record_count"], 1)
        self.assertEqual(body["invalid_record_count"], 0)
        self.assertEqual(body["dataset_count"], 1)
        self.assertTrue(body["dataset_ids"][0].startswith("api-curated-test-"))
        self.assertEqual(body["datasets"][0]["unclassified_count"], 1)
        self.assertTrue(any("does not activate probability evidence" in warning for warning in body["warnings"]))

    def test_task16c_build_payload_registers_and_retains_context(self):
        accepted = self._observation_export_record("manual-craft-observation-register-accepted", "outcome-api-1")
        build = self.client.post(
            "/api/v1/observations/build-empirical-datasets",
            json={
                "accepted_export": {
                    "review_version": "dc-observation-review-v1",
                    "observations": [accepted],
                },
                "dataset_id_prefix": "api-register-build-test",
            },
        ).json()

        response = self.client.post(
            "/api/v1/observations/empirical-datasets/register",
            json={"dataset": build["datasets"][0]},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "REGISTERED")
        self.assertEqual(body["dataset_id"], build["dataset_ids"][0])
        self.assertEqual(body["dataset"]["league"], LEAGUE)
        self.assertEqual(body["dataset"]["action_id"], accepted["action_id"])
        self.assertEqual(body["dataset"]["source_outcome_set_id"], accepted["source_outcome_set_id"])

    def test_curated_observation_build_endpoint_rejects_malformed_observations(self):
        response = self.client.post(
            "/api/v1/observations/build-empirical-datasets",
            json={
                "accepted_export": {
                    "observations": [{"raw_record_id": "manual-craft-observation-build-malformed"}]
                }
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["source_record_count"], 1)
        self.assertEqual(body["imported_record_count"], 0)
        self.assertEqual(body["accepted_record_count"], 0)
        self.assertEqual(body["invalid_record_count"], 1)
        self.assertEqual(body["dataset_count"], 0)
        self.assertEqual(body["rejected_records"][0]["raw_record_id"], "manual-craft-observation-build-malformed")

    def test_curated_observation_build_endpoint_counts_non_dict_entries_as_invalid(self):
        accepted = self._observation_export_record("manual-craft-observation-build-valid", "outcome-api-1")
        response = self.client.post(
            "/api/v1/observations/build-empirical-datasets",
            json={
                "accepted_export": {
                    "observations": [accepted, "not an observation object"]
                }
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["source_record_count"], 2)
        self.assertEqual(body["imported_record_count"], 1)
        self.assertEqual(body["accepted_record_count"], 1)
        self.assertEqual(body["invalid_record_count"], 1)
        self.assertEqual(body["dataset_count"], 1)
        self.assertIsNone(body["rejected_records"][0]["raw_record_id"])
        self.assertIn("accepted_export:2", body["rejected_records"][0]["reason"])
        self.assertIn("str", body["rejected_records"][0]["reason"])

    def test_empirical_dataset_register_and_list_endpoint(self):
        self._install_registry_backed_deterministic_dependencies()
        initial = self.client.post("/api/v1/advisor/analyze", json=base_request()).json()
        payload = self._registered_empirical_dataset_payload(initial)

        response = self.client.post(
            "/api/v1/observations/empirical-datasets/register",
            json={"dataset": payload},
        )
        listed = self.client.get("/api/v1/observations/empirical-datasets")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "REGISTERED")
        self.assertEqual(response.json()["dataset_id"], payload["dataset_id"])
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json()["datasets"][0]["dataset_id"], payload["dataset_id"])
        self.assertEqual(listed.json()["datasets"][0]["league"], LEAGUE)
        self.assertEqual(listed.json()["persistence"]["storage_mode"], "IN_MEMORY")
        self.assertFalse(listed.json()["persistence"]["persistence_enabled"])

    def test_empirical_dataset_duplicate_registration_is_idempotent(self):
        self._install_registry_backed_deterministic_dependencies()
        payload = self._registered_empirical_dataset_payload(
            self.client.post("/api/v1/advisor/analyze", json=base_request()).json()
        )

        first = self.client.post("/api/v1/observations/empirical-datasets/register", json={"dataset": payload})
        second = self.client.post("/api/v1/observations/empirical-datasets/register", json={"dataset": payload})

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json()["status"], "ALREADY_REGISTERED")

    def test_empirical_dataset_conflicting_duplicate_registration_is_rejected(self):
        self._install_registry_backed_deterministic_dependencies()
        payload = self._registered_empirical_dataset_payload(
            self.client.post("/api/v1/advisor/analyze", json=base_request()).json()
        )
        conflict = copy.deepcopy(payload)
        conflict["observations"][0]["observed_count"] = 11

        self.client.post("/api/v1/observations/empirical-datasets/register", json={"dataset": payload})
        response = self.client.post("/api/v1/observations/empirical-datasets/register", json={"dataset": conflict})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"]["code"], "VALIDATION_ERROR")
        self.assertTrue(any("different content" in warning for warning in response.json()["detail"]["warnings"]))

    def test_registered_dataset_does_not_auto_activate_without_explicit_selection(self):
        self._install_registry_backed_deterministic_dependencies()
        initial = self.client.post("/api/v1/advisor/analyze", json=base_request()).json()
        payload = self._registered_empirical_dataset_payload(initial)
        self.client.post("/api/v1/observations/empirical-datasets/register", json={"dataset": payload})

        response = self.client.post("/api/v1/advisor/analyze", json=base_request())

        self.assertEqual(response.status_code, 200)
        annulment = self._action(response.json(), "dc:poe2:craft-action:orb-of-annulment")
        self.assertEqual(annulment["probability"]["completeness"], "UNKNOWN")
        self.assertEqual(annulment["probability"]["known_outcome_count"], 0)

    def test_explicit_registered_dataset_selection_reaches_empirical_readiness_path(self):
        self._install_registry_backed_deterministic_dependencies()
        initial = self.client.post("/api/v1/advisor/analyze", json=base_request()).json()
        payload = self._registered_empirical_dataset_payload(initial)
        self.client.post("/api/v1/observations/empirical-datasets/register", json={"dataset": payload})
        request = base_request()
        request["empirical_probability_dataset_version"] = payload["dataset_id"]

        response = self.client.post("/api/v1/advisor/analyze", json=request)

        self.assertEqual(response.status_code, 200)
        annulment = self._action(response.json(), "dc:poe2:craft-action:orb-of-annulment")
        self.assertEqual(annulment["probability"]["completeness"], "COMPLETE")
        self.assertEqual(annulment["probability"]["known_outcome_count"], annulment["outcome_count"])
        self.assertEqual(annulment["probability"]["outcome_probabilities"][0]["evidence"][0]["probability_type"], "EMPIRICAL_ESTIMATE")
        self.assertEqual(annulment["probability"]["outcome_probabilities"][0]["evidence"][0]["evidence_dataset_version"], payload["dataset_id"])

    def test_unknown_empirical_dataset_selection_surfaces_warning_not_fallback(self):
        self._install_registry_backed_deterministic_dependencies()
        request = base_request()
        request["empirical_probability_dataset_version"] = "not-registered"

        response = self.client.post("/api/v1/advisor/analyze", json=request)

        self.assertEqual(response.status_code, 200)
        annulment = self._action(response.json(), "dc:poe2:craft-action:orb-of-annulment")
        self.assertEqual(annulment["probability"]["completeness"], "UNKNOWN")
        self.assertTrue(any("not-registered" in warning for warning in annulment["warnings"]))

    def test_empirical_registry_persistence_reloads_through_api_dependency(self):
        from services.api.app.dependencies import advisor as advisor_dependencies

        previous = os.environ.get("DCS_EMPIRICAL_REGISTRY_PATH")
        with tempfile.TemporaryDirectory() as directory:
            os.environ["DCS_EMPIRICAL_REGISTRY_PATH"] = str(Path(directory) / "registry.json")
            try:
                self._clear_dependency_caches(advisor_dependencies)
                payload = self._registered_empirical_dataset_payload(
                    self.client.post("/api/v1/advisor/analyze", json=base_request()).json()
                )
                registered = self.client.post(
                    "/api/v1/observations/empirical-datasets/register",
                    json={"dataset": payload},
                )
                self._clear_dependency_caches(advisor_dependencies)
                listed = self.client.get("/api/v1/observations/empirical-datasets")
            finally:
                if previous is None:
                    os.environ.pop("DCS_EMPIRICAL_REGISTRY_PATH", None)
                else:
                    os.environ["DCS_EMPIRICAL_REGISTRY_PATH"] = previous
                self._clear_dependency_caches(advisor_dependencies)

        self.assertEqual(registered.status_code, 200)
        self.assertEqual(registered.json()["persistence"]["storage_mode"], "FILE")
        self.assertTrue(registered.json()["persistence"]["persistence_enabled"])
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json()["datasets"][0]["dataset_id"], payload["dataset_id"])
        self.assertEqual(listed.json()["persistence"]["loaded_dataset_count"], 1)

    def test_empirical_registry_corrupt_persisted_dataset_status_surfaces_warning(self):
        from services.api.app.dependencies import advisor as advisor_dependencies

        previous = os.environ.get("DCS_EMPIRICAL_REGISTRY_PATH")
        with tempfile.TemporaryDirectory() as directory:
            storage = Path(directory) / "registry.json"
            payload = self._registered_empirical_dataset_payload(
                self.client.post("/api/v1/advisor/analyze", json=base_request()).json()
            )
            storage.write_text(
                json.dumps(
                    {
                        "registry_version": "dc-empirical-dataset-registry-v1",
                        "storage_version": "dc-empirical-dataset-registry-storage-v1",
                        "datasets": [payload, {"dataset_id": "broken"}],
                    }
                ),
                encoding="utf-8",
            )
            os.environ["DCS_EMPIRICAL_REGISTRY_PATH"] = str(storage)
            try:
                self._clear_dependency_caches(advisor_dependencies)
                response = self.client.get("/api/v1/observations/empirical-datasets")
            finally:
                if previous is None:
                    os.environ.pop("DCS_EMPIRICAL_REGISTRY_PATH", None)
                else:
                    os.environ["DCS_EMPIRICAL_REGISTRY_PATH"] = previous
                self._clear_dependency_caches(advisor_dependencies)

        body = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["datasets"][0]["dataset_id"], payload["dataset_id"])
        self.assertEqual(body["persistence"]["skipped_dataset_count"], 1)
        self.assertTrue(any("broken" in warning for warning in body["warnings"]))

    def test_wrong_crafting_dataset_version_is_rejected(self):
        response = self.client.post(
            "/api/v1/observations/record",
            json={
                "before_clipboard_text": fixture("quiver_6_crafted_desecrated_advanced.txt"),
                "after_clipboard_text": fixture("quiver_6_crafted_desecrated_advanced.txt"),
                "action_id": "dc:poe2:craft-action:orb-of-annulment",
                "source_outcome_set_id": "analysis-test:dc:poe2:craft-action:orb-of-annulment",
                "item_class": "Quivers",
                "league": LEAGUE,
                "observed_at": AS_OF,
                "crafting_dataset_version": "fabricated-crafting-dataset",
                "modifier_dataset_version": GAME_DATASET_ID,
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("crafting_dataset_version", response.json()["detail"]["message"])

    def test_wrong_modifier_dataset_version_is_rejected(self):
        response = self.client.post(
            "/api/v1/observations/record",
            json={
                "before_clipboard_text": fixture("quiver_6_crafted_desecrated_advanced.txt"),
                "after_clipboard_text": fixture("quiver_6_crafted_desecrated_advanced.txt"),
                "action_id": "dc:poe2:craft-action:orb-of-annulment",
                "source_outcome_set_id": "analysis-test:dc:poe2:craft-action:orb-of-annulment",
                "item_class": "Quivers",
                "league": LEAGUE,
                "observed_at": AS_OF,
                "crafting_dataset_version": CRAFTING_DATASET_ID,
                "modifier_dataset_version": "fabricated-modifier-dataset",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("modifier_dataset_version", response.json()["detail"]["message"])

    def test_observation_item_class_mismatch_is_rejected(self):
        response = self.client.post(
            "/api/v1/observations/record",
            json={
                "before_clipboard_text": fixture("quiver_6_crafted_desecrated_advanced.txt"),
                "after_clipboard_text": fixture("quiver_6_crafted_desecrated_advanced.txt"),
                "action_id": "dc:poe2:craft-action:orb-of-annulment",
                "source_outcome_set_id": "analysis-test:dc:poe2:craft-action:orb-of-annulment",
                "item_class": "Rings",
                "league": LEAGUE,
                "observed_at": AS_OF,
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("item_class", response.json()["detail"]["message"])

    def test_incompatible_before_after_item_identity_is_rejected(self):
        response = self.client.post(
            "/api/v1/observations/record",
            json={
                "before_clipboard_text": fixture("quiver_6_crafted_desecrated_advanced.txt"),
                "after_clipboard_text": fixture("quiver_6_crafted_desecrated_advanced.txt").replace(
                    "Item Level: 82",
                    "Item Level: 81",
                ),
                "action_id": "dc:poe2:craft-action:orb-of-annulment",
                "source_outcome_set_id": "analysis-test:dc:poe2:craft-action:orb-of-annulment",
                "item_class": "Quivers",
                "league": LEAGUE,
                "observed_at": AS_OF,
                "manual_outcome_id": "fabricated-client-outcome-id",
                "manual_reason": "attempt to classify mismatched items",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("item_level", response.json()["detail"]["message"])

    def test_observation_manual_classification_is_labeled_manual(self):
        initial = self.client.post("/api/v1/advisor/analyze", json=base_request()).json()
        outcome_id = self._action(initial, "dc:poe2:craft-action:orb-of-annulment")["outcome_ids"][0]
        response = self.client.post(
            "/api/v1/observations/record",
            json={
                "before_clipboard_text": fixture("quiver_6_crafted_desecrated_advanced.txt"),
                "after_clipboard_text": fixture("quiver_6_crafted_desecrated_advanced.txt"),
                "action_id": "dc:poe2:craft-action:orb-of-annulment",
                "source_outcome_set_id": "analysis-test:dc:poe2:craft-action:orb-of-annulment",
                "item_class": "Quivers",
                "league": LEAGUE,
                "observed_at": AS_OF,
                "manual_outcome_id": outcome_id,
                "manual_reason": "User explicitly selected the outcome.",
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["classification"]["method"], "MANUAL")
        self.assertEqual(body["classification"]["outcome_id"], outcome_id)
        self.assertEqual(body["export_record"]["classification_method"], "MANUAL")

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

    def _clear_dependency_caches(self, advisor_dependencies) -> None:
        advisor_dependencies.get_advisor_orchestrator.cache_clear()
        advisor_dependencies.get_economy_repository.cache_clear()
        advisor_dependencies.get_probability_provider.cache_clear()
        advisor_dependencies.get_empirical_probability_registry.cache_clear()
        advisor_dependencies.get_cached_settings.cache_clear()

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

    def _install_synthetic_empirical_dependencies(self):
        from packages.shared.donniecraftshell_contracts.advisor_orchestration import CraftAdvisorOrchestrator
        from packages.shared.donniecraftshell_contracts.affix_capacity import AffixStateResolver, load_affix_capacity_dataset
        from packages.shared.donniecraftshell_contracts.crafting_actions import CraftActionEngine, load_crafting_dataset
        from packages.shared.donniecraftshell_contracts.domain import DataProvenance, SourceType, VerificationStatus
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
        from packages.shared.donniecraftshell_contracts.empirical_probability import (
            EmpiricalOutcomeCount,
            EmpiricalProbabilityDataset,
            EmpiricalProbabilityProvider,
        )
        from packages.shared.donniecraftshell_contracts.game_data_repository import GameDataRepository
        from packages.shared.donniecraftshell_contracts.parser import parse_clipboard_item
        from services.api.app.dependencies.advisor import get_advisor_orchestrator, get_economy_repository

        class SyntheticEmpiricalProbabilityProvider:
            def get_probability_model(self, item, outcome_set, context=None):
                retrieved_at = datetime.fromisoformat(AS_OF)
                dataset = EmpiricalProbabilityDataset(
                    dataset_id="synthetic-api-empirical-probability",
                    action_id=outcome_set.action_id,
                    source_outcome_set_id=f"{outcome_set.source_item_analysis_id}:{outcome_set.action_id}",
                    game="Path of Exile 2",
                    league=LEAGUE,
                    retrieved_at=retrieved_at,
                    outcome_counts=tuple(
                        EmpiricalOutcomeCount(state.outcome_id, 10)
                        for state in outcome_set.hypothetical_states
                    ),
                    unclassified_count=0,
                    sample_size=10 * len(outcome_set.hypothetical_states),
                    provenance=(
                        DataProvenance(
                            source_id="synthetic-api-empirical-probability",
                            source_type=SourceType.INTERNAL,
                            source_uri="local://tests/synthetic-api-empirical-probability",
                            retrieved_at=retrieved_at,
                            league=LEAGUE,
                            verification_status=VerificationStatus.NEEDS_VERIFICATION,
                            notes="Synthetic test-only empirical probability evidence.",
                        ),
                    ),
                    synthetic=True,
                    item_class="Quivers",
                    game_version="synthetic-test-version",
                    crafting_dataset_version=CRAFTING_DATASET_ID,
                    modifier_dataset_version=GAME_DATASET_ID,
                    methodology="synthetic API empirical probability evidence",
                    verification_status=VerificationStatus.NEEDS_VERIFICATION,
                    warnings=("Synthetic API fixture; not production probability evidence.",),
                )
                return EmpiricalProbabilityProvider((dataset,), allow_synthetic=True).get_probability_model(
                    item,
                    outcome_set,
                    context,
                )

        def deterministic_parser(raw_clipboard_text, game_context=None):
            result = parse_clipboard_item(raw_clipboard_text, game_context)
            if result.item is None:
                return result
            return replace(result, item=replace(result.item, analysis_id="synthetic-api-analysis"))

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
            probability_provider=SyntheticEmpiricalProbabilityProvider(),
            parser=deterministic_parser,
        )
        self.app.dependency_overrides[get_economy_repository] = lambda: economy
        self.app.dependency_overrides[get_advisor_orchestrator] = lambda: orchestrator

    def _install_registry_backed_deterministic_dependencies(self):
        from packages.shared.donniecraftshell_contracts.advisor_orchestration import CraftAdvisorOrchestrator
        from packages.shared.donniecraftshell_contracts.affix_capacity import AffixStateResolver, load_affix_capacity_dataset
        from packages.shared.donniecraftshell_contracts.crafting_actions import CraftActionEngine, load_crafting_dataset
        from packages.shared.donniecraftshell_contracts.economy_repository import EconomyRepository
        from packages.shared.donniecraftshell_contracts.empirical_probability import (
            EmpiricalProbabilityDatasetRegistry,
            EmpiricalProbabilityRegistryProvider,
        )
        from packages.shared.donniecraftshell_contracts.game_data_repository import GameDataRepository
        from packages.shared.donniecraftshell_contracts.parser import parse_clipboard_item
        from services.api.app.dependencies.advisor import (
            get_advisor_orchestrator,
            get_economy_repository,
            get_empirical_probability_registry,
        )

        def deterministic_parser(raw_clipboard_text, game_context=None):
            result = parse_clipboard_item(raw_clipboard_text, game_context)
            if result.item is None:
                return result
            return replace(result, item=replace(result.item, analysis_id="registry-api-analysis"))

        registry = EmpiricalProbabilityDatasetRegistry()
        economy = EconomyRepository(())
        orchestrator = CraftAdvisorOrchestrator(
            GameDataRepository.from_json_files((ROOT / "data" / "normalized" / GAME_DATASET_ID / "game_data.json",)),
            AffixStateResolver(load_affix_capacity_dataset(ROOT / "data" / "normalized" / "crafting" / AFFIX_CAPACITY_DATASET_ID / "capacity.json")),
            CraftActionEngine(load_crafting_dataset(ROOT / "data" / "normalized" / "crafting" / CRAFTING_DATASET_ID / "actions.json")),
            economy,
            probability_provider=EmpiricalProbabilityRegistryProvider(registry),
            parser=deterministic_parser,
        )
        self.app.dependency_overrides[get_empirical_probability_registry] = lambda: registry
        self.app.dependency_overrides[get_economy_repository] = lambda: economy
        self.app.dependency_overrides[get_advisor_orchestrator] = lambda: orchestrator

    def _action(self, body: dict, action_id: str) -> dict:
        return next(action for action in body["actions"] if action["action_id"] == action_id)

    def _registered_empirical_dataset_payload(self, analysis_body: dict) -> dict:
        annulment = self._action(analysis_body, "dc:poe2:craft-action:orb-of-annulment")
        return {
            "dataset_id": "api-registered-empirical-probability",
            "action_id": annulment["action_id"],
            "source_outcome_set_id": annulment["probability"]["source_outcome_set_id"],
            "game": "Path of Exile 2",
            "league": LEAGUE,
            "item_class": "Quivers",
            "game_version": None,
            "crafting_dataset_version": CRAFTING_DATASET_ID,
            "modifier_dataset_version": GAME_DATASET_ID,
            "retrieved_at": AS_OF,
            "source_uri": "local://tests/api-registered-empirical-probability",
            "source_type": "MANUAL_RESEARCH",
            "synthetic": False,
            "verification_status": "NEEDS_VERIFICATION",
            "methodology": "synthetic unit-test manual observations for registry plumbing",
            "notes": "Test-only non-synthetic-shaped payload; not real PoE2 probability evidence.",
            "warnings": ["Test fixture validates explicit registry selection only."],
            "unclassified_count": 0,
            "observations": [
                {
                    "outcome_id": outcome_id,
                    "observed_count": 10,
                    "raw_record_ids": [f"registry-test-record-{index}"],
                }
                for index, outcome_id in enumerate(annulment["outcome_ids"])
            ],
        }

    def _observation_export_record(self, raw_record_id: str, outcome_id: str) -> dict:
        return {
            "raw_record_id": raw_record_id,
            "action_id": "dc:poe2:craft-action:orb-of-annulment",
            "source_outcome_set_id": "backend-outcome-set:annulment:api-test",
            "item_class": "Quivers",
            "league": LEAGUE,
            "game": "Path of Exile 2",
            "game_version": "synthetic-test-version",
            "crafting_dataset_version": CRAFTING_DATASET_ID,
            "modifier_dataset_version": GAME_DATASET_ID,
            "observed_at": AS_OF,
            "source_id": "api-test-review",
            "source_type": "MANUAL_RESEARCH",
            "source_uri": "local://tests/api-observation-review",
            "synthetic": True,
            "outcome_id": outcome_id,
            "unclassified": False,
            "verification_status": "NEEDS_VERIFICATION",
            "notes": "synthetic API review test",
            "classification_method": "MANUAL",
            "classification_reason": "manual test classification",
            "classification_warnings": [],
            "before_item_fingerprint": "before-api",
            "after_item_fingerprint": "after-api",
            "recorder_version": "dc-observation-recorder-v1",
            "warnings": [],
        }


if __name__ == "__main__":
    unittest.main()
