import copy
import unittest
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

from packages.shared.donniecraftshell_contracts.affix_capacity import (
    AffixStateResolver,
    load_affix_capacity_dataset,
)
from packages.shared.donniecraftshell_contracts.craft_outcomes import CraftOutcomeEngine
from packages.shared.donniecraftshell_contracts.crafting_actions import CraftActionEngine, load_crafting_dataset
from packages.shared.donniecraftshell_contracts.game_data_repository import GameDataRepository
from packages.shared.donniecraftshell_contracts.domain import AffixState, AffixType
from packages.shared.donniecraftshell_contracts.parser import parse_clipboard_item
from packages.shared.donniecraftshell_contracts.probability import (
    CurrentResearchProbabilityProvider,
    OutcomeProbability,
    OutcomeProbabilityModel,
    ProbabilityCompleteness,
    ProbabilityContext,
    ProbabilityEvidence,
    ProbabilityInterval,
    ProbabilityType,
    can_calculate_expected_value,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "poe2" / "quivers"
CRAFTING_DATASET = ROOT / "data" / "normalized" / "crafting" / "crafting-actions-poe2-quiver-2026-08-12-research" / "actions.json"
AFFIX_CAPACITY_DATASET = ROOT / "data" / "normalized" / "crafting" / "affix-capacity-poe2-2026-08-12-research" / "capacity.json"
GAME_DATASET_VERSION = "poe2db-unknown-version-2026-08-12-task8c-fullx1"
GAME_DATASET = ROOT / "data" / "normalized" / GAME_DATASET_VERSION / "game_data.json"
CRAFTING_DATASET_VERSION = "crafting-actions-poe2-quiver-2026-08-12-research"


def parsed_fixture(name: str):
    result = parse_clipboard_item((FIXTURE_DIR / name).read_text(encoding="utf-8"))
    assert result.item is not None
    return result.item


def action_by_id(dataset, action_id: str):
    return next(action for action in dataset.actions if action.action_id == action_id)


def with_prefix_suffix_counts(item, prefix_count: int, suffix_count: int):
    prefixes = [modifier for modifier in item.explicit_modifiers if modifier.affix_type == AffixType.PREFIX]
    suffixes = [modifier for modifier in item.explicit_modifiers if modifier.affix_type == AffixType.SUFFIX]
    explicit = tuple(prefixes[:prefix_count] + suffixes[:suffix_count])
    return replace(
        item,
        explicit_modifiers=explicit,
        modifiers=item.implicit_modifiers + explicit + item.special_modifiers,
        affix_state=AffixState(
            known_prefixes=tuple(prefixes[:prefix_count]),
            known_suffixes=tuple(suffixes[:suffix_count]),
            observed_prefix_count=prefix_count,
            observed_suffix_count=suffix_count,
        ),
    )


class ProbabilityContractTests(unittest.TestCase):
    def setUp(self):
        self.crafting_dataset = load_crafting_dataset(CRAFTING_DATASET)
        self.craft_engine = CraftActionEngine(self.crafting_dataset)
        self.affix_resolver = AffixStateResolver(load_affix_capacity_dataset(AFFIX_CAPACITY_DATASET))
        self.outcome_engine = CraftOutcomeEngine()
        self.game_repo = GameDataRepository.from_json_files((GAME_DATASET,))
        self.provider = CurrentResearchProbabilityProvider()
        self.context = ProbabilityContext(
            crafting_dataset_version=CRAFTING_DATASET_VERSION,
            modifier_dataset_version=GAME_DATASET_VERSION,
            evidence_dataset_version="task9b-current-research",
        )

    def _outcomes(self, item, action_id: str):
        action = action_by_id(self.crafting_dataset, action_id)
        affix_state = self.affix_resolver.resolve(item)
        applicability = self.craft_engine.evaluate_action(action, item, affix_state)
        return self.outcome_engine.enumerate_outcomes(
            item,
            affix_state,
            action,
            applicability,
            self.game_repo,
            GAME_DATASET_VERSION,
        )

    def test_probability_below_zero_rejected(self):
        with self.assertRaises(ValueError):
            ProbabilityEvidence(
                evidence_id="synthetic-negative",
                probability_type=ProbabilityType.EXACT_MECHANICAL,
                action_id="dc:test:action",
                probability=Decimal("-0.1"),
            )

    def test_probability_above_one_rejected(self):
        with self.assertRaises(ValueError):
            ProbabilityEvidence(
                evidence_id="synthetic-too-high",
                probability_type=ProbabilityType.EXACT_MECHANICAL,
                action_id="dc:test:action",
                probability=Decimal("1.1"),
            )

    def test_unknown_probability_is_not_zero(self):
        evidence = ProbabilityEvidence(
            evidence_id="synthetic-unknown",
            probability_type=ProbabilityType.UNKNOWN,
            action_id="dc:test:action",
        )

        self.assertIsNone(evidence.probability)
        self.assertNotEqual(evidence.probability, Decimal("0"))

    def test_decimal_only_probability_values(self):
        with self.assertRaises(TypeError):
            ProbabilityEvidence(
                evidence_id="synthetic-float",
                probability_type=ProbabilityType.EXACT_MECHANICAL,
                action_id="dc:test:action",
                probability=0.5,  # type: ignore[arg-type]
            )

    def test_valid_uncertainty_interval(self):
        interval = ProbabilityInterval(Decimal("0.031"), Decimal("0.037"))

        self.assertEqual(interval.lower, Decimal("0.031"))
        self.assertEqual(interval.upper, Decimal("0.037"))

    def test_invalid_uncertainty_interval_rejected(self):
        with self.assertRaises(ValueError):
            ProbabilityInterval(Decimal("0.8"), Decimal("0.2"))

    def test_complete_model_requires_probability_mass_one(self):
        model = OutcomeProbabilityModel(
            action_id="dc:test:action",
            source_outcome_set_id="synthetic-complete",
            probability_completeness=ProbabilityCompleteness.COMPLETE,
            outcome_probabilities=(
                OutcomeProbability("outcome-a", Decimal("0.25")),
                OutcomeProbability("outcome-b", Decimal("0.75")),
            ),
        )

        self.assertEqual(model.total_known_probability_mass, Decimal("1.00"))
        self.assertTrue(can_calculate_expected_value(model))

    def test_complete_model_with_missing_probability_rejected(self):
        with self.assertRaises(ValueError):
            OutcomeProbabilityModel(
                action_id="dc:test:action",
                source_outcome_set_id="synthetic-missing",
                probability_completeness=ProbabilityCompleteness.COMPLETE,
                outcome_probabilities=(OutcomeProbability("outcome-a", None),),
            )

    def test_partial_model_permits_incomplete_mass(self):
        model = OutcomeProbabilityModel(
            action_id="dc:test:action",
            source_outcome_set_id="synthetic-partial",
            probability_completeness=ProbabilityCompleteness.PARTIAL,
            outcome_probabilities=(OutcomeProbability("outcome-a", Decimal("0.4")),),
        )

        self.assertEqual(model.total_known_probability_mass, Decimal("0.4"))
        self.assertFalse(can_calculate_expected_value(model))

    def test_unknown_model_does_not_invent_probabilities(self):
        model = OutcomeProbabilityModel(
            action_id="dc:test:action",
            source_outcome_set_id="synthetic-unknown",
            probability_completeness=ProbabilityCompleteness.UNKNOWN,
            outcome_probabilities=(
                OutcomeProbability("outcome-a", None),
                OutcomeProbability("outcome-b", None),
            ),
        )

        self.assertEqual(model.total_known_probability_mass, Decimal("0"))
        self.assertTrue(all(probability.probability is None for probability in model.outcome_probabilities))

    def test_no_equal_distribution_fallback_for_real_annulment(self):
        item = parsed_fixture("quiver_6_crafted_desecrated_advanced.txt")
        outcome_set = self._outcomes(item, "dc:poe2:craft-action:orb-of-annulment")

        model = self.provider.get_probability_model(item, outcome_set, self.context)

        self.assertEqual(model.probability_completeness, ProbabilityCompleteness.UNKNOWN)
        self.assertEqual(len(model.outcome_probabilities), 6)
        self.assertTrue(all(probability.probability is None for probability in model.outcome_probabilities))
        self.assertFalse(can_calculate_expected_value(model))

    def test_real_exalted_remains_unknown(self):
        item = parsed_fixture("quiver_1_rare_standard_advanced.txt")
        open_item = with_prefix_suffix_counts(item, 2, 2)
        outcome_set = self._outcomes(open_item, "dc:poe2:craft-action:exalted-orb")

        model = self.provider.get_probability_model(open_item, outcome_set, self.context)

        self.assertEqual(model.probability_completeness, ProbabilityCompleteness.UNKNOWN)
        self.assertTrue(all(probability.probability is None for probability in model.outcome_probabilities))

    def test_essence_deterministic_component_does_not_make_final_outcome_known(self):
        item = parsed_fixture("quiver_1_rare_standard_advanced.txt")
        outcome_set = self._outcomes(item, "dc:poe2:craft-action:essence-of-hysteria")

        model = self.provider.get_probability_model(item, outcome_set, self.context)

        self.assertEqual(model.probability_completeness, ProbabilityCompleteness.UNKNOWN)
        self.assertTrue(model.deterministic_operations)
        self.assertEqual(model.deterministic_operations[0].evidence.probability_type, ProbabilityType.DETERMINISTIC)
        self.assertEqual(model.deterministic_operations[0].evidence.probability, Decimal("1"))
        self.assertTrue(all(probability.probability is None for probability in model.outcome_probabilities))
        self.assertFalse(can_calculate_expected_value(model))

    def test_dataset_versions_are_retained(self):
        item = parsed_fixture("quiver_6_crafted_desecrated_advanced.txt")
        outcome_set = self._outcomes(item, "dc:poe2:craft-action:orb-of-annulment")

        model = self.provider.get_probability_model(item, outcome_set, self.context)

        self.assertIn(CRAFTING_DATASET_VERSION, model.dataset_versions)
        self.assertIn(GAME_DATASET_VERSION, model.dataset_versions)
        self.assertIn("task9b-current-research", model.dataset_versions)

    def test_parsed_item_and_outcome_set_remain_immutable(self):
        item = parsed_fixture("quiver_6_crafted_desecrated_advanced.txt")
        outcome_set = self._outcomes(item, "dc:poe2:craft-action:orb-of-annulment")
        before_item = copy.deepcopy(item)
        before_outcome_set = copy.deepcopy(outcome_set)

        self.provider.get_probability_model(item, outcome_set, self.context)

        self.assertEqual(item, before_item)
        self.assertEqual(outcome_set, before_outcome_set)


if __name__ == "__main__":
    unittest.main()
