import copy
import json
import tempfile
import unittest
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

from packages.shared.donniecraftshell_contracts.craft_outcomes import (
    CraftOutcomeSet,
    HypotheticalItemState,
    OutcomeProbabilityStatus,
    OutcomeSpaceCompleteness,
)
from packages.shared.donniecraftshell_contracts.crafting_actions import CraftApplicabilityStatus
from packages.shared.donniecraftshell_contracts.empirical_probability import (
    EMPIRICAL_PROBABILITY_METHODOLOGY_VERSION,
    EmpiricalOutcomeCount,
    EmpiricalDatasetRegistrationStatus,
    EmpiricalProbabilityDatasetRegistry,
    EmpiricalProbabilityProvider,
    EmpiricalProbabilityRepository,
    EmpiricalProbabilityReadinessPolicy,
    FileBackedEmpiricalProbabilityDatasetRegistry,
    load_raw_empirical_probability_dataset,
    normalize_empirical_probability_dataset,
)
from packages.shared.donniecraftshell_contracts.parser import parse_clipboard_item
from packages.shared.donniecraftshell_contracts.probability import (
    ProbabilityCompleteness,
    ProbabilityContext,
    ProbabilityType,
    can_calculate_expected_value,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "poe2" / "quivers"
SYNTHETIC_FIXTURE = ROOT / "data" / "raw" / "probability" / "synthetic_empirical_annulment_outcomes.json"


def parsed_quiver_6():
    result = parse_clipboard_item((FIXTURE_DIR / "quiver_6_crafted_desecrated_advanced.txt").read_text(encoding="utf-8"))
    assert result.item is not None
    return result.item


def synthetic_outcome_set(outcome_ids=("synthetic-outcome-a", "synthetic-outcome-b")):
    action_id = "dc:test:craft-action:synthetic-annulment"
    return CraftOutcomeSet(
        action_id=action_id,
        source_item_analysis_id="synthetic-quiver-analysis",
        applicability_status=CraftApplicabilityStatus.APPLICABLE,
        outcome_definition=None,
        hypothetical_states=tuple(
            HypotheticalItemState(
                outcome_id=outcome_id,
                source_item_analysis_id="synthetic-quiver-analysis",
                action_id=action_id,
                deltas=(),
            )
            for outcome_id in outcome_ids
        ),
        outcome_space_completeness=OutcomeSpaceCompleteness.COMPLETE,
        probability_completeness=OutcomeProbabilityStatus.UNKNOWN,
        dataset_versions=("synthetic-modifier-dataset",),
        warnings=("Synthetic test-only outcome set.",),
    )


class EmpiricalProbabilityPipelineTests(unittest.TestCase):
    def test_raw_fixture_parses_and_normalizes(self):
        raw = load_raw_empirical_probability_dataset(SYNTHETIC_FIXTURE)
        dataset = normalize_empirical_probability_dataset(raw)

        self.assertTrue(dataset.synthetic)
        self.assertEqual(dataset.dataset_id, "synthetic-empirical-probability-2026-08-13-test-only")
        self.assertEqual(dataset.sample_size, 100)
        self.assertEqual(dataset.outcome_counts[0].observed_count, 25)
        self.assertEqual(dataset.outcome_counts[1].observed_count, 75)
        self.assertEqual(dataset.provenance[0].source_uri, "local://tests/synthetic-empirical-annulment-outcomes")

    def test_complete_synthetic_dataset_produces_empirical_estimates(self):
        dataset = normalize_empirical_probability_dataset(load_raw_empirical_probability_dataset(SYNTHETIC_FIXTURE))
        provider = EmpiricalProbabilityProvider((dataset,), allow_synthetic=True)
        item = parsed_quiver_6()

        model = provider.get_probability_model(
            item,
            synthetic_outcome_set(),
            ProbabilityContext(
                crafting_dataset_version="synthetic-crafting-dataset",
                modifier_dataset_version="synthetic-modifier-dataset",
                evidence_dataset_version=dataset.dataset_id,
                game_version="synthetic-test-version",
                league="Synthetic Test League",
            ),
        )

        probabilities = {entry.outcome_id: entry.probability for entry in model.outcome_probabilities}
        self.assertEqual(model.probability_completeness, ProbabilityCompleteness.COMPLETE)
        self.assertEqual(probabilities["synthetic-outcome-a"], Decimal("0.25"))
        self.assertEqual(probabilities["synthetic-outcome-b"], Decimal("0.75"))
        self.assertEqual(model.total_known_probability_mass, Decimal("1.00"))
        self.assertTrue(can_calculate_expected_value(model))
        self.assertTrue(all(entry.evidence[0].probability_type == ProbabilityType.EMPIRICAL_ESTIMATE for entry in model.outcome_probabilities))
        self.assertTrue(all(entry.evidence[0].sample_size == 100 for entry in model.outcome_probabilities))
        self.assertTrue(all(entry.evidence[0].uncertainty_interval is not None for entry in model.outcome_probabilities))
        self.assertIn(dataset.dataset_id, model.dataset_versions)

    def test_dataset_requires_explicit_selection_before_use(self):
        dataset = normalize_empirical_probability_dataset(load_raw_empirical_probability_dataset(SYNTHETIC_FIXTURE))
        provider = EmpiricalProbabilityProvider((dataset,), allow_synthetic=True)

        model = provider.get_probability_model(
            parsed_quiver_6(),
            synthetic_outcome_set(),
            ProbabilityContext(
                crafting_dataset_version="synthetic-crafting-dataset",
                modifier_dataset_version="synthetic-modifier-dataset",
                game_version="synthetic-test-version",
                league="Synthetic Test League",
            ),
        )

        self.assertEqual(model.probability_completeness, ProbabilityCompleteness.UNKNOWN)
        self.assertTrue(all(entry.probability is None for entry in model.outcome_probabilities))

    def test_unknown_explicit_dataset_selection_warns_without_fallback(self):
        dataset = normalize_empirical_probability_dataset(load_raw_empirical_probability_dataset(SYNTHETIC_FIXTURE))

        model = EmpiricalProbabilityProvider((dataset,), allow_synthetic=True).get_probability_model(
            parsed_quiver_6(),
            synthetic_outcome_set(),
            ProbabilityContext(evidence_dataset_version="missing-empirical-dataset"),
        )

        self.assertEqual(model.probability_completeness, ProbabilityCompleteness.UNKNOWN)
        self.assertTrue(any("missing-empirical-dataset" in warning for warning in model.warnings))

    def test_empirical_probability_uses_counts_not_equal_distribution(self):
        dataset = normalize_empirical_probability_dataset(load_raw_empirical_probability_dataset(SYNTHETIC_FIXTURE))
        model = EmpiricalProbabilityProvider((dataset,), allow_synthetic=True).get_probability_model(
            parsed_quiver_6(),
            synthetic_outcome_set(),
            ProbabilityContext(evidence_dataset_version=dataset.dataset_id),
        )

        self.assertNotEqual(model.outcome_probabilities[0].probability, Decimal("0.5"))
        self.assertNotEqual(model.outcome_probabilities[1].probability, Decimal("0.5"))

    def test_unclassified_observations_block_complete_model(self):
        dataset = normalize_empirical_probability_dataset(load_raw_empirical_probability_dataset(SYNTHETIC_FIXTURE))
        partial = replace(dataset, unclassified_count=10, sample_size=110)

        model = EmpiricalProbabilityProvider((partial,), allow_synthetic=True).get_probability_model(
            parsed_quiver_6(),
            synthetic_outcome_set(),
            ProbabilityContext(evidence_dataset_version=partial.dataset_id),
        )

        self.assertEqual(model.probability_completeness, ProbabilityCompleteness.PARTIAL)
        self.assertEqual(model.total_known_probability_mass, Decimal("0.9090909090909090909090909091"))
        self.assertFalse(can_calculate_expected_value(model))
        self.assertTrue(any("unclassified" in warning for warning in model.warnings))

    def test_missing_outcome_count_remains_unknown_not_zero(self):
        dataset = normalize_empirical_probability_dataset(load_raw_empirical_probability_dataset(SYNTHETIC_FIXTURE))

        model = EmpiricalProbabilityProvider((dataset,), allow_synthetic=True).get_probability_model(
            parsed_quiver_6(),
            synthetic_outcome_set(("synthetic-outcome-a", "synthetic-outcome-b", "synthetic-outcome-c")),
            ProbabilityContext(evidence_dataset_version=dataset.dataset_id),
        )

        missing = next(entry for entry in model.outcome_probabilities if entry.outcome_id == "synthetic-outcome-c")
        self.assertEqual(model.probability_completeness, ProbabilityCompleteness.PARTIAL)
        self.assertIsNone(missing.probability)
        self.assertNotEqual(missing.probability, Decimal("0"))
        self.assertFalse(can_calculate_expected_value(model))

    def test_low_sample_size_is_partial_even_when_mass_sums_to_one(self):
        raw = load_raw_empirical_probability_dataset(SYNTHETIC_FIXTURE)
        dataset = normalize_empirical_probability_dataset(raw)
        small = replace(
            dataset,
            outcome_counts=(
                EmpiricalOutcomeCount("synthetic-outcome-a", 1),
                EmpiricalOutcomeCount("synthetic-outcome-b", 1),
            ),
            sample_size=2,
        )

        model = EmpiricalProbabilityProvider(
            (small,),
            EmpiricalProbabilityReadinessPolicy(minimum_sample_size_for_complete=30),
            allow_synthetic=True,
        ).get_probability_model(parsed_quiver_6(), synthetic_outcome_set(), ProbabilityContext(evidence_dataset_version=small.dataset_id))

        self.assertEqual(model.total_known_probability_mass, Decimal("1.0"))
        self.assertEqual(model.probability_completeness, ProbabilityCompleteness.PARTIAL)
        self.assertFalse(can_calculate_expected_value(model))

    def test_context_incompatible_evidence_falls_back_to_unknown(self):
        dataset = normalize_empirical_probability_dataset(load_raw_empirical_probability_dataset(SYNTHETIC_FIXTURE))

        model = EmpiricalProbabilityProvider((dataset,), allow_synthetic=True).get_probability_model(
            parsed_quiver_6(),
            synthetic_outcome_set(),
            ProbabilityContext(
                evidence_dataset_version=dataset.dataset_id,
                crafting_dataset_version="different-crafting-dataset",
                league="Different League",
            ),
        )

        self.assertEqual(model.probability_completeness, ProbabilityCompleteness.UNKNOWN)
        self.assertTrue(all(entry.probability is None for entry in model.outcome_probabilities))
        self.assertTrue(any("does not match" in warning for warning in model.warnings))

    def test_synthetic_dataset_requires_explicit_enablement(self):
        dataset = normalize_empirical_probability_dataset(load_raw_empirical_probability_dataset(SYNTHETIC_FIXTURE))

        model = EmpiricalProbabilityProvider((dataset,)).get_probability_model(
            parsed_quiver_6(),
            synthetic_outcome_set(),
            ProbabilityContext(evidence_dataset_version=dataset.dataset_id),
        )

        self.assertEqual(model.probability_completeness, ProbabilityCompleteness.UNKNOWN)
        self.assertTrue(all(entry.probability is None for entry in model.outcome_probabilities))
        self.assertTrue(any("Synthetic empirical probability datasets require explicit" in warning for warning in model.warnings))

    def test_repository_skips_synthetic_dataset_by_default(self):
        repository = EmpiricalProbabilityRepository.from_json_files((SYNTHETIC_FIXTURE,))

        self.assertEqual(repository.datasets, ())
        self.assertEqual(repository.skipped_dataset_ids, ("synthetic-empirical-probability-2026-08-13-test-only",))
        self.assertTrue(repository.warnings)

    def test_registry_registers_task15a_payload_and_lists_summary(self):
        registry = EmpiricalProbabilityDatasetRegistry()
        payload = json.loads(SYNTHETIC_FIXTURE.read_text(encoding="utf-8"))

        result = registry.register_raw_payload(payload)

        self.assertEqual(result.status, EmpiricalDatasetRegistrationStatus.REGISTERED)
        self.assertEqual(result.dataset_id, payload["dataset_id"])
        self.assertEqual(registry.get_dataset(payload["dataset_id"]).dataset_id, payload["dataset_id"])
        summaries = registry.list_summaries()
        self.assertEqual(len(summaries), 1)
        self.assertEqual(summaries[0].dataset_id, payload["dataset_id"])
        self.assertEqual(summaries[0].sample_size, 100)
        self.assertTrue(summaries[0].synthetic)

    def test_registry_duplicate_identical_payload_is_idempotent(self):
        registry = EmpiricalProbabilityDatasetRegistry()
        payload = json.loads(SYNTHETIC_FIXTURE.read_text(encoding="utf-8"))

        first = registry.register_raw_payload(payload)
        second = registry.register_raw_payload(payload)

        self.assertEqual(first.status, EmpiricalDatasetRegistrationStatus.REGISTERED)
        self.assertEqual(second.status, EmpiricalDatasetRegistrationStatus.ALREADY_REGISTERED)
        self.assertEqual(len(registry.list_summaries()), 1)

    def test_registry_rejects_same_dataset_id_with_conflicting_content(self):
        registry = EmpiricalProbabilityDatasetRegistry()
        payload = json.loads(SYNTHETIC_FIXTURE.read_text(encoding="utf-8"))
        conflict = copy.deepcopy(payload)
        conflict["observations"][0]["observed_count"] = 26

        registry.register_raw_payload(payload)
        result = registry.register_raw_payload(conflict)

        self.assertEqual(result.status, EmpiricalDatasetRegistrationStatus.REJECTED)
        self.assertTrue(any("different content" in warning for warning in result.warnings))
        self.assertEqual(registry.get_dataset(payload["dataset_id"]).sample_size, 100)

    def test_registry_rejects_malformed_payload_conservatively(self):
        result = EmpiricalProbabilityDatasetRegistry().register_raw_payload({"dataset_id": "broken"})

        self.assertEqual(result.status, EmpiricalDatasetRegistrationStatus.REJECTED)
        self.assertTrue(result.warnings)

    def test_file_backed_registry_reloads_registered_dataset(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "registry.json"
            payload = non_synthetic_payload("persisted-dataset")
            first = FileBackedEmpiricalProbabilityDatasetRegistry(path)

            result = first.register_raw_payload(payload)
            reloaded = FileBackedEmpiricalProbabilityDatasetRegistry(path)

            self.assertEqual(result.status, EmpiricalDatasetRegistrationStatus.REGISTERED)
            self.assertEqual(reloaded.get_dataset("persisted-dataset").dataset_id, "persisted-dataset")
            self.assertEqual(reloaded.get_dataset("persisted-dataset").league, "Synthetic Test League")
            self.assertEqual(reloaded.persistence_status().loaded_dataset_count, 1)
            self.assertTrue(reloaded.persistence_status().persistence_enabled)

    def test_file_backed_registry_duplicate_is_idempotent_after_reload(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "registry.json"
            payload = non_synthetic_payload("idempotent-dataset")
            FileBackedEmpiricalProbabilityDatasetRegistry(path).register_raw_payload(payload)
            reloaded = FileBackedEmpiricalProbabilityDatasetRegistry(path)

            result = reloaded.register_raw_payload(payload)

            self.assertEqual(result.status, EmpiricalDatasetRegistrationStatus.ALREADY_REGISTERED)
            self.assertEqual(len(reloaded.list_summaries()), 1)

    def test_file_backed_registry_rejects_conflict_after_reload(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "registry.json"
            payload = non_synthetic_payload("conflict-dataset")
            conflict = copy.deepcopy(payload)
            conflict["observations"][0]["observed_count"] = 26
            FileBackedEmpiricalProbabilityDatasetRegistry(path).register_raw_payload(payload)
            reloaded = FileBackedEmpiricalProbabilityDatasetRegistry(path)

            result = reloaded.register_raw_payload(conflict)

            self.assertEqual(result.status, EmpiricalDatasetRegistrationStatus.REJECTED)
            self.assertTrue(any("different content" in warning for warning in result.warnings))
            self.assertEqual(reloaded.get_dataset("conflict-dataset").sample_size, 100)

    def test_corrupt_persisted_entries_are_skipped_with_warnings(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "registry.json"
            valid = non_synthetic_payload("valid-after-corrupt")
            path.write_text(
                json.dumps(
                    {
                        "registry_version": "dc-empirical-dataset-registry-v1",
                        "storage_version": "dc-empirical-dataset-registry-storage-v1",
                        "datasets": [valid, {"dataset_id": "broken"}, "not an object"],
                    }
                ),
                encoding="utf-8",
            )

            registry = FileBackedEmpiricalProbabilityDatasetRegistry(path)

            self.assertIsNotNone(registry.get_dataset("valid-after-corrupt"))
            self.assertEqual(registry.persistence_status().skipped_dataset_count, 2)
            self.assertTrue(any("broken" in warning or "not an object" in warning for warning in registry.persistence_status().warnings))

    def test_rejected_registration_does_not_alter_persistence_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "registry.json"
            registry = FileBackedEmpiricalProbabilityDatasetRegistry(path)
            payload = non_synthetic_payload("stable-file")
            registry.register_raw_payload(payload)
            before = path.read_text(encoding="utf-8")
            conflict = copy.deepcopy(payload)
            conflict["observations"][0]["observed_count"] = 26

            result = registry.register_raw_payload(conflict)

            self.assertEqual(result.status, EmpiricalDatasetRegistrationStatus.REJECTED)
            self.assertEqual(path.read_text(encoding="utf-8"), before)

    def test_persistence_write_is_deterministic_and_preserves_previous_datasets(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "registry.json"
            registry = FileBackedEmpiricalProbabilityDatasetRegistry(path)
            registry.register_raw_payload(non_synthetic_payload("dataset-b"))
            registry.register_raw_payload(non_synthetic_payload("dataset-a"))
            first = path.read_text(encoding="utf-8")
            reloaded = FileBackedEmpiricalProbabilityDatasetRegistry(path)
            second = path.read_text(encoding="utf-8")

            self.assertEqual(first, second)
            self.assertEqual([summary.dataset_id for summary in reloaded.list_summaries()], ["dataset-a", "dataset-b"])

    def test_persisted_dataset_reload_does_not_auto_activate_probability(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "registry.json"
            payload = non_synthetic_payload("inert-persisted-dataset")
            FileBackedEmpiricalProbabilityDatasetRegistry(path).register_raw_payload(payload)
            provider = FileBackedEmpiricalProbabilityDatasetRegistry(path).to_provider()

            model = provider.get_probability_model(
                parsed_quiver_6(),
                synthetic_outcome_set(),
                ProbabilityContext(
                    crafting_dataset_version="synthetic-crafting-dataset",
                    modifier_dataset_version="synthetic-modifier-dataset",
                    league="Synthetic Test League",
                ),
            )

            self.assertEqual(model.probability_completeness, ProbabilityCompleteness.UNKNOWN)
            self.assertTrue(all(entry.probability is None for entry in model.outcome_probabilities))

    def test_explicit_selection_after_reload_reaches_empirical_path(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "registry.json"
            payload = non_synthetic_payload("selected-after-reload")
            FileBackedEmpiricalProbabilityDatasetRegistry(path).register_raw_payload(payload)
            provider = FileBackedEmpiricalProbabilityDatasetRegistry(path).to_provider()

            model = provider.get_probability_model(
                parsed_quiver_6(),
                synthetic_outcome_set(),
                ProbabilityContext(
                    evidence_dataset_version="selected-after-reload",
                    crafting_dataset_version="synthetic-crafting-dataset",
                    modifier_dataset_version="synthetic-modifier-dataset",
                    game_version="synthetic-test-version",
                    league="Synthetic Test League",
                ),
            )

            self.assertEqual(model.probability_completeness, ProbabilityCompleteness.COMPLETE)
            self.assertEqual(model.total_known_probability_mass, Decimal("1.00"))

    def test_persisted_synthetic_dataset_still_requires_synthetic_enablement(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "registry.json"
            payload = json.loads(SYNTHETIC_FIXTURE.read_text(encoding="utf-8"))
            FileBackedEmpiricalProbabilityDatasetRegistry(path).register_raw_payload(payload)

            model = FileBackedEmpiricalProbabilityDatasetRegistry(path).to_provider().get_probability_model(
                parsed_quiver_6(),
                synthetic_outcome_set(),
                ProbabilityContext(evidence_dataset_version=payload["dataset_id"]),
            )

            self.assertEqual(model.probability_completeness, ProbabilityCompleteness.UNKNOWN)
            self.assertTrue(any("Synthetic empirical probability datasets require explicit" in warning for warning in model.warnings))

    def test_no_dataset_leaves_real_actions_unknown(self):
        model = EmpiricalProbabilityProvider(()).get_probability_model(
            parsed_quiver_6(),
            synthetic_outcome_set(),
            ProbabilityContext(evidence_dataset_version="missing-evidence-dataset"),
        )

        self.assertEqual(model.probability_completeness, ProbabilityCompleteness.UNKNOWN)
        self.assertTrue(all(entry.probability is None for entry in model.outcome_probabilities))

    def test_provider_does_not_mutate_item_or_outcome_set(self):
        dataset = normalize_empirical_probability_dataset(load_raw_empirical_probability_dataset(SYNTHETIC_FIXTURE))
        item = parsed_quiver_6()
        outcome_set = synthetic_outcome_set()
        before_item = copy.deepcopy(item)
        before_outcome_set = copy.deepcopy(outcome_set)

        EmpiricalProbabilityProvider((dataset,), allow_synthetic=True).get_probability_model(
            item,
            outcome_set,
            ProbabilityContext(evidence_dataset_version=dataset.dataset_id),
        )

        self.assertEqual(item, before_item)
        self.assertEqual(outcome_set, before_outcome_set)

def non_synthetic_payload(dataset_id: str) -> dict:
    payload = json.loads(SYNTHETIC_FIXTURE.read_text(encoding="utf-8"))
    payload["dataset_id"] = dataset_id
    payload["synthetic"] = False
    payload["source_type"] = "MANUAL_RESEARCH"
    payload["source_uri"] = f"local://tests/{dataset_id}"
    payload["warnings"] = ["Test-only non-synthetic-shaped persistence fixture."]
    payload["notes"] = "Test-only payload; not real PoE2 probability evidence."
    return payload


if __name__ == "__main__":
    unittest.main()
