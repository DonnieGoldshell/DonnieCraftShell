import copy
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
    EmpiricalProbabilityProvider,
    EmpiricalProbabilityRepository,
    EmpiricalProbabilityReadinessPolicy,
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


if __name__ == "__main__":
    unittest.main()
