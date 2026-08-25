import json
import os
import tempfile
import unittest
from pathlib import Path

from packages.shared.donniecraftshell_contracts.affix_capacity import AffixStateResolver, load_affix_capacity_dataset
from packages.shared.donniecraftshell_contracts.analytical_probability_registry import (
    ANALYTICAL_MECHANIC_REGISTRY_VERSION,
    AnalyticalMechanicRegistry,
    analytical_mechanic_registry_from_dict,
)
from packages.shared.donniecraftshell_contracts.advisor_orchestration import AdvisorAnalysisRequest, CraftAdvisorOrchestrator, MissingRequirementKind
from packages.shared.donniecraftshell_contracts.craft_outcomes import CraftOutcomeEngine
from packages.shared.donniecraftshell_contracts.crafting_actions import CraftActionEngine, load_crafting_dataset
from packages.shared.donniecraftshell_contracts.economy_repository import EconomyRepository
from packages.shared.donniecraftshell_contracts.game_data_repository import GameDataRepository
from packages.shared.donniecraftshell_contracts.parser import parse_clipboard_item
from packages.shared.donniecraftshell_contracts.probability import (
    AnalyticalProbabilityProvider,
    ProbabilityCompleteness,
    ProbabilityContext,
    can_calculate_expected_value,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "poe2" / "quivers"
GAME_DATASET_ID = "poe2db-unknown-version-2026-08-12-task8c-fullx1"
CRAFTING_DATASET_ID = "crafting-actions-poe2-quiver-2026-08-12-research"
AFFIX_CAPACITY_DATASET_ID = "affix-capacity-poe2-2026-08-12-research"
GAME_DATASET = ROOT / "data" / "normalized" / GAME_DATASET_ID / "game_data.json"
CRAFTING_DATASET = ROOT / "data" / "normalized" / "crafting" / CRAFTING_DATASET_ID / "actions.json"
AFFIX_CAPACITY_DATASET = ROOT / "data" / "normalized" / "crafting" / AFFIX_CAPACITY_DATASET_ID / "capacity.json"
EMPTY_PRODUCTION_REGISTRY = (
    ROOT
    / "data"
    / "normalized"
    / "probability"
    / "verified-analytical-mechanics-empty-2026-08-25"
    / "registry.json"
)


class AnalyticalProbabilityRegistryTests(unittest.TestCase):
    def setUp(self):
        self.item = parse_clipboard_item((FIXTURE_DIR / "quiver_6_crafted_desecrated_advanced.txt").read_text(encoding="utf-8")).item
        self.assertIsNotNone(self.item)
        self.crafting_dataset = load_crafting_dataset(CRAFTING_DATASET)
        self.craft_engine = CraftActionEngine(self.crafting_dataset)
        self.affix_state = AffixStateResolver(load_affix_capacity_dataset(AFFIX_CAPACITY_DATASET)).resolve(self.item)
        action = next(action for action in self.crafting_dataset.actions if action.action_id == "dc:poe2:craft-action:orb-of-annulment")
        applicability = self.craft_engine.evaluate_action(action, self.item, self.affix_state)
        self.outcome_set = CraftOutcomeEngine().enumerate_outcomes(
            self.item,
            self.affix_state,
            action,
            applicability,
            GameDataRepository.from_json_files((GAME_DATASET,)),
            GAME_DATASET_ID,
        )
        self.context = ProbabilityContext(
            crafting_dataset_version=CRAFTING_DATASET_ID,
            modifier_dataset_version=GAME_DATASET_ID,
            evidence_dataset_version="synthetic-analytical-registry-test",
        )

    def test_empty_production_registry_preserves_unknown_behavior(self):
        registry = AnalyticalMechanicRegistry.from_json_files((EMPTY_PRODUCTION_REGISTRY,))
        model = AnalyticalProbabilityProvider(registry.rules, load_warnings=registry.warnings).get_probability_model(
            self.item,
            self.outcome_set,
            self.context,
        )

        self.assertEqual(registry.dataset_id, "verified-analytical-mechanics-empty-2026-08-25")
        self.assertEqual(registry.rules, ())
        self.assertEqual(model.probability_completeness, ProbabilityCompleteness.UNKNOWN)
        self.assertTrue(all(item.probability is None for item in model.outcome_probabilities))
        self.assertFalse(can_calculate_expected_value(model))

    def test_valid_synthetic_verified_record_loads_and_maps_to_rule(self):
        registry = analytical_mechanic_registry_from_dict(self._registry_payload((self._valid_rule(),)))
        model = AnalyticalProbabilityProvider(registry.rules).get_probability_model(self.item, self.outcome_set, self.context)

        self.assertEqual(registry.skipped_rule_ids, ())
        self.assertEqual(len(registry.rules), 1)
        self.assertEqual(model.probability_completeness, ProbabilityCompleteness.COMPLETE)
        self.assertTrue(all(item.probability is not None for item in model.outcome_probabilities))
        self.assertTrue(all(item.evidence[0].evidence_dataset_version == "synthetic-verified-mechanic-registry" for item in model.outcome_probabilities))

    def test_non_verified_record_is_skipped_and_cannot_clear_blocker(self):
        rule = self._valid_rule()
        rule["verification_status"] = "NEEDS_VERIFICATION"
        registry = analytical_mechanic_registry_from_dict(self._registry_payload((rule,)))
        model = AnalyticalProbabilityProvider(registry.rules, load_warnings=registry.warnings).get_probability_model(
            self.item,
            self.outcome_set,
            self.context,
        )

        self.assertEqual(registry.rules, ())
        self.assertEqual(registry.skipped_rule_ids, ("synthetic-verified-uniform-annulment",))
        self.assertTrue(any("must be VERIFIED" in warning for warning in registry.warnings))
        self.assertEqual(model.probability_completeness, ProbabilityCompleteness.UNKNOWN)

        result = self._orchestrator(AnalyticalProbabilityProvider(registry.rules, load_warnings=registry.warnings)).analyze(
            self._request()
        )
        self.assertTrue(
            any(
                requirement.kind == MissingRequirementKind.PROBABILITY_EVIDENCE_REQUIRED
                and requirement.affected_action_id == self.outcome_set.action_id
                for requirement in result.missing_requirements
            )
        )

    def test_non_verified_provenance_is_skipped(self):
        rule = self._valid_rule()
        rule["provenance"][0]["verification_status"] = "CURATED"
        registry = analytical_mechanic_registry_from_dict(self._registry_payload((rule,)))

        self.assertEqual(registry.rules, ())
        self.assertEqual(registry.skipped_rule_ids, ("synthetic-verified-uniform-annulment",))
        self.assertTrue(any("provenance must be VERIFIED" in warning for warning in registry.warnings))

    def test_duplicate_action_scope_fails_closed(self):
        first = self._valid_rule("duplicate-a")
        second = self._valid_rule("duplicate-b")
        registry = analytical_mechanic_registry_from_dict(self._registry_payload((first, second)))

        self.assertEqual(registry.rules, ())
        self.assertEqual(set(registry.skipped_rule_ids), {"duplicate-a", "duplicate-b"})
        self.assertTrue(any("Duplicate analytical mechanic action scopes" in warning for warning in registry.warnings))

    def test_duplicate_rule_id_fails_closed(self):
        first = self._valid_rule("duplicate-rule-id")
        second = self._valid_rule("duplicate-rule-id")
        second["action_id"] = "dc:test:other-action"
        registry = analytical_mechanic_registry_from_dict(self._registry_payload((first, second)))

        self.assertEqual(registry.rules, ())
        self.assertEqual(registry.skipped_rule_ids, ("duplicate-rule-id", "duplicate-rule-id"))
        self.assertTrue(any("Duplicate analytical mechanic rule IDs" in warning for warning in registry.warnings))

    def test_intra_file_action_conflict_cannot_be_masked_by_second_file(self):
        with tempfile.TemporaryDirectory() as directory:
            first_path = Path(directory) / "conflicting_registry.json"
            second_path = Path(directory) / "valid_looking_registry.json"
            first_path.write_text(
                json.dumps(
                    self._registry_payload(
                        (
                            self._valid_rule("same-file-conflict-a"),
                            self._valid_rule("same-file-conflict-b"),
                        )
                    )
                ),
                encoding="utf-8",
            )
            second_path.write_text(
                json.dumps(self._registry_payload((self._valid_rule("second-file-valid-looking"),))),
                encoding="utf-8",
            )

            registry = AnalyticalMechanicRegistry.from_json_files((first_path, second_path))

        self.assertEqual(registry.rules, ())
        self.assertEqual(
            set(registry.skipped_rule_ids),
            {"same-file-conflict-a", "same-file-conflict-b", "second-file-valid-looking"},
        )
        self.assertTrue(any("Duplicate analytical mechanic action scopes" in warning for warning in registry.warnings))

    def test_cross_file_duplicate_rule_ids_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            first_path = Path(directory) / "first_registry.json"
            second_path = Path(directory) / "second_registry.json"
            first_path.write_text(
                json.dumps(self._registry_payload((self._valid_rule("shared-rule-id", action_id="dc:test:first-action"),))),
                encoding="utf-8",
            )
            second_path.write_text(
                json.dumps(self._registry_payload((self._valid_rule("shared-rule-id", action_id="dc:test:second-action"),))),
                encoding="utf-8",
            )

            registry = AnalyticalMechanicRegistry.from_json_files((first_path, second_path))

        self.assertEqual(registry.rules, ())
        self.assertEqual(registry.skipped_rule_ids, ("shared-rule-id", "shared-rule-id"))
        self.assertTrue(any("Duplicate analytical mechanic rule IDs" in warning for warning in registry.warnings))

    def test_cross_file_duplicate_action_scopes_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            first_path = Path(directory) / "first_registry.json"
            second_path = Path(directory) / "second_registry.json"
            first_path.write_text(
                json.dumps(self._registry_payload((self._valid_rule("first-action-scope-rule"),))),
                encoding="utf-8",
            )
            second_path.write_text(
                json.dumps(self._registry_payload((self._valid_rule("second-action-scope-rule"),))),
                encoding="utf-8",
            )

            registry = AnalyticalMechanicRegistry.from_json_files((first_path, second_path))

        self.assertEqual(registry.rules, ())
        self.assertEqual(set(registry.skipped_rule_ids), {"first-action-scope-rule", "second-action-scope-rule"})
        self.assertTrue(any("Duplicate analytical mechanic action scopes" in warning for warning in registry.warnings))

    def test_malformed_registry_surfaces_warning_without_rules(self):
        registry = analytical_mechanic_registry_from_dict({"dataset_id": "broken", "registry_version": "future"})

        self.assertEqual(registry.rules, ())
        self.assertTrue(any("registry_version" in warning for warning in registry.warnings))

    def test_dependency_assembly_uses_registry_before_empirical_fallback(self):
        from services.api.app.dependencies import advisor as advisor_dependencies

        previous_registry_paths = os.environ.get("DCS_ANALYTICAL_MECHANIC_REGISTRY_PATHS")
        previous_empirical_registry = os.environ.get("DCS_EMPIRICAL_REGISTRY_PATH")
        with tempfile.TemporaryDirectory() as directory:
            registry_path = Path(directory) / "analytical_registry.json"
            registry_path.write_text(json.dumps(self._registry_payload((self._valid_rule(),))), encoding="utf-8")
            os.environ["DCS_ANALYTICAL_MECHANIC_REGISTRY_PATHS"] = str(registry_path)
            os.environ["DCS_EMPIRICAL_REGISTRY_PATH"] = "disabled"
            self._clear_dependency_caches(advisor_dependencies)

            provider = advisor_dependencies.get_probability_provider()
            model = provider.get_probability_model(self.item, self.outcome_set, self.context)

        self._restore_env("DCS_ANALYTICAL_MECHANIC_REGISTRY_PATHS", previous_registry_paths)
        self._restore_env("DCS_EMPIRICAL_REGISTRY_PATH", previous_empirical_registry)
        self._clear_dependency_caches(advisor_dependencies)

        self.assertEqual(model.probability_completeness, ProbabilityCompleteness.COMPLETE)
        self.assertTrue(all(item.evidence[0].evidence_id.startswith("probability:analytical:") for item in model.outcome_probabilities))

    def _orchestrator(self, probability_provider):
        return CraftAdvisorOrchestrator(
            GameDataRepository.from_json_files((GAME_DATASET,)),
            AffixStateResolver(load_affix_capacity_dataset(AFFIX_CAPACITY_DATASET)),
            self.craft_engine,
            EconomyRepository(()),
            probability_provider=probability_provider,
            parser=lambda raw, context=None: parse_clipboard_item(
                (FIXTURE_DIR / "quiver_6_crafted_desecrated_advanced.txt").read_text(encoding="utf-8"),
                context,
            ),
        )

    def _request(self):
        return AdvisorAnalysisRequest(
            raw_clipboard_text="ignored by deterministic parser",
            game_context=None,
            league="Runes of Aldur",
            game_data_dataset_version=GAME_DATASET_ID,
            crafting_dataset_version=CRAFTING_DATASET_ID,
            affix_capacity_dataset_version=AFFIX_CAPACITY_DATASET_ID,
        )

    def _valid_rule(
        self,
        rule_id: str = "synthetic-verified-uniform-annulment",
        action_id: str | None = None,
    ) -> dict:
        return {
            "rule_id": rule_id,
            "action_id": action_id or self.outcome_set.action_id,
            "rule_type": "UNIFORM_ENUMERATED_OUTCOMES",
            "methodology": "Synthetic test-only VERIFIED mechanic: uniform over enumerated outcomes.",
            "verification_status": "VERIFIED",
            "required_selection_rule": "ANY_ELIGIBLE_EXPLICIT_MODIFIER",
            "required_outcome_space_completeness": "COMPLETE",
            "expected_source_outcome_set_id": f"{self.outcome_set.source_item_analysis_id}:{self.outcome_set.action_id}",
            "expected_outcome_ids": [state.outcome_id for state in self.outcome_set.hypothetical_states],
            "crafting_dataset_version": CRAFTING_DATASET_ID,
            "modifier_dataset_version": GAME_DATASET_ID,
            "evidence_dataset_version": "synthetic-verified-mechanic-registry",
            "provenance": [
                {
                    "source_id": "synthetic-verified-mechanic-source",
                    "source_type": "INTERNAL",
                    "source_uri": "local://tests/synthetic-verified-mechanic-source",
                    "retrieved_at": "2026-08-25T00:00:00+00:00",
                    "verification_status": "VERIFIED",
                    "notes": "Synthetic test-only provenance; not real PoE2 probability evidence.",
                }
            ],
            "warnings": ["Synthetic test-only analytical mechanic evidence."],
        }

    def _registry_payload(self, rules: tuple[dict, ...]) -> dict:
        return {
            "dataset_id": "synthetic-verified-mechanic-registry",
            "registry_version": ANALYTICAL_MECHANIC_REGISTRY_VERSION,
            "rules": list(rules),
        }

    def _clear_dependency_caches(self, advisor_dependencies) -> None:
        advisor_dependencies.get_cached_settings.cache_clear()
        advisor_dependencies.get_probability_provider.cache_clear()
        advisor_dependencies.get_empirical_probability_registry.cache_clear()
        advisor_dependencies.get_analytical_mechanic_registry.cache_clear()
        advisor_dependencies.get_advisor_orchestrator.cache_clear()

    def _restore_env(self, name: str, value: str | None) -> None:
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value


if __name__ == "__main__":
    unittest.main()
