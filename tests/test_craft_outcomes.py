import copy
import unittest
from dataclasses import replace
from pathlib import Path

from packages.shared.donniecraftshell_contracts.affix_capacity import (
    AffixStateResolver,
    load_affix_capacity_dataset,
)
from packages.shared.donniecraftshell_contracts.craft_outcomes import (
    CraftOutcomeEngine,
    CraftOutcomeOperation,
    OutcomeProbabilityStatus,
    OutcomeSelectionRule,
    OutcomeSpaceCompleteness,
)
from packages.shared.donniecraftshell_contracts.crafting_actions import (
    CraftActionEngine,
    CraftApplicabilityStatus,
    load_crafting_dataset,
)
from packages.shared.donniecraftshell_contracts.domain import (
    AffixState,
    AffixType,
    ItemModifier,
)
from packages.shared.donniecraftshell_contracts.game_data_repository import GameDataRepository
from packages.shared.donniecraftshell_contracts.parser import parse_clipboard_item


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "poe2" / "quivers"
CRAFTING_DATASET = ROOT / "data" / "normalized" / "crafting" / "crafting-actions-poe2-quiver-2026-08-12-research" / "actions.json"
AFFIX_CAPACITY_DATASET = ROOT / "data" / "normalized" / "crafting" / "affix-capacity-poe2-2026-08-12-research" / "capacity.json"
GAME_DATASET = ROOT / "data" / "normalized" / "poe2db-unknown-version-2026-08-11-task5c-quiver" / "game_data.json"
GAME_DATASET_VERSION = "poe2db-unknown-version-2026-08-11-task5c-quiver"


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


class CraftOutcomeEngineTests(unittest.TestCase):
    def setUp(self):
        self.crafting_dataset = load_crafting_dataset(CRAFTING_DATASET)
        self.craft_engine = CraftActionEngine(self.crafting_dataset)
        self.affix_resolver = AffixStateResolver(load_affix_capacity_dataset(AFFIX_CAPACITY_DATASET))
        self.outcome_engine = CraftOutcomeEngine()
        self.game_repo = GameDataRepository.from_json_files((GAME_DATASET,))

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

    def test_outcome_set_does_not_mutate_parsed_item(self):
        item = parsed_fixture("quiver_6_crafted_desecrated_advanced.txt")
        before = copy.deepcopy(item)

        self._outcomes(item, "dc:poe2:craft-action:orb-of-annulment")

        self.assertEqual(item, before)

    def test_not_applicable_action_produces_no_executable_outcomes(self):
        item = parsed_fixture("quiver_6_crafted_desecrated_advanced.txt")

        outcome_set = self._outcomes(item, "dc:poe2:craft-action:exalted-orb")

        self.assertEqual(outcome_set.applicability_status, CraftApplicabilityStatus.NOT_APPLICABLE)
        self.assertEqual(outcome_set.outcome_space_completeness, OutcomeSpaceCompleteness.NOT_APPLICABLE)
        self.assertEqual(outcome_set.probability_completeness, OutcomeProbabilityStatus.NOT_APPLICABLE)
        self.assertEqual(outcome_set.hypothetical_states, ())

    def test_annulment_enumerates_only_eligible_explicit_modifiers(self):
        item = parsed_fixture("quiver_6_crafted_desecrated_advanced.txt")

        outcome_set = self._outcomes(item, "dc:poe2:craft-action:orb-of-annulment")

        self.assertEqual(outcome_set.outcome_space_completeness, OutcomeSpaceCompleteness.COMPLETE)
        self.assertEqual(len(outcome_set.hypothetical_states), 6)
        removed = [state.deltas[0].removed_modifier for state in outcome_set.hypothetical_states]
        self.assertTrue(all(modifier in item.explicit_modifiers for modifier in removed))
        self.assertTrue(all(modifier not in item.implicit_modifiers for modifier in removed))
        self.assertEqual(outcome_set.probability_completeness, OutcomeProbabilityStatus.UNKNOWN)

    def test_prefix_and_suffix_annul_restrict_eligible_modifier_set(self):
        item = parsed_fixture("quiver_6_crafted_desecrated_advanced.txt")

        prefix = self._outcomes(item, "dc:poe2:craft-action:orb-of-annulment-with-omen-of-sinistral-annulment")
        suffix = self._outcomes(item, "dc:poe2:craft-action:orb-of-annulment-with-omen-of-dextral-annulment")

        self.assertEqual(len(prefix.hypothetical_states), 3)
        self.assertEqual(prefix.outcome_definition.selection_rule, OutcomeSelectionRule.PREFIX_ONLY)
        self.assertTrue(all(state.deltas[0].removed_modifier.affix_type == AffixType.PREFIX for state in prefix.hypothetical_states))
        self.assertEqual(len(suffix.hypothetical_states), 3)
        self.assertEqual(suffix.outcome_definition.selection_rule, OutcomeSelectionRule.SUFFIX_ONLY)
        self.assertTrue(all(state.deltas[0].removed_modifier.affix_type == AffixType.SUFFIX for state in suffix.hypothetical_states))

    def test_greater_annulment_is_partial_and_unknown_probability(self):
        item = parsed_fixture("quiver_6_crafted_desecrated_advanced.txt")

        outcome_set = self._outcomes(item, "dc:poe2:craft-action:orb-of-annulment-with-omen-of-greater-annulment")

        self.assertEqual(outcome_set.outcome_space_completeness, OutcomeSpaceCompleteness.PARTIAL)
        self.assertEqual(outcome_set.probability_completeness, OutcomeProbabilityStatus.UNKNOWN)
        self.assertTrue(any("pairwise" in warning for warning in outcome_set.warnings))

    def test_exalted_candidate_pool_respects_open_affix_side(self):
        item = with_prefix_suffix_counts(parsed_fixture("quiver_1_rare_standard_advanced.txt"), 3, 2)

        dextral = self._outcomes(item, "dc:poe2:craft-action:exalted-orb-with-omen-of-dextral-exaltation")
        sinistral = self._outcomes(item, "dc:poe2:craft-action:exalted-orb-with-omen-of-sinistral-exaltation")

        self.assertEqual(dextral.applicability_status, CraftApplicabilityStatus.APPLICABLE)
        self.assertEqual(dextral.outcome_space_completeness, OutcomeSpaceCompleteness.PARTIAL)
        self.assertGreater(len(dextral.hypothetical_states), 0)
        self.assertEqual(sinistral.applicability_status, CraftApplicabilityStatus.NOT_APPLICABLE)
        self.assertEqual(sinistral.hypothetical_states, ())

    def test_prefix_open_synthetic_quiver_produces_partial_prefix_pool(self):
        item = with_prefix_suffix_counts(parsed_fixture("quiver_1_rare_standard_advanced.txt"), 2, 3)

        outcome_set = self._outcomes(item, "dc:poe2:craft-action:exalted-orb-with-omen-of-sinistral-exaltation")

        self.assertEqual(outcome_set.applicability_status, CraftApplicabilityStatus.APPLICABLE)
        self.assertEqual(outcome_set.outcome_space_completeness, OutcomeSpaceCompleteness.PARTIAL)
        self.assertGreater(len(outcome_set.hypothetical_states), 0)
        self.assertEqual(outcome_set.probability_completeness, OutcomeProbabilityStatus.UNKNOWN)

    def test_item_level_requirements_filter_impossible_candidates(self):
        item = with_prefix_suffix_counts(parsed_fixture("quiver_1_rare_standard_advanced.txt"), 2, 3)
        low_level = replace(item, item_level=1)

        normal = self._outcomes(item, "dc:poe2:craft-action:exalted-orb-with-omen-of-sinistral-exaltation")
        low = self._outcomes(low_level, "dc:poe2:craft-action:exalted-orb-with-omen-of-sinistral-exaltation")

        self.assertGreater(len(normal.hypothetical_states), len(low.hypothetical_states))

    def test_modifier_group_conflicts_filter_impossible_candidates_when_present(self):
        item = with_prefix_suffix_counts(parsed_fixture("quiver_1_rare_standard_advanced.txt"), 3, 2)
        conflict_modifier = ItemModifier(
            raw_text="+13% increased Attack Speed",
            affix_type=AffixType.SUFFIX,
            family="IncreasedAttackSpeed",
        )
        with_conflict = replace(item, explicit_modifiers=item.explicit_modifiers + (conflict_modifier,))

        without_conflict = self._outcomes(item, "dc:poe2:craft-action:exalted-orb-with-omen-of-dextral-exaltation")
        with_conflict_outcomes = self._outcomes(with_conflict, "dc:poe2:craft-action:exalted-orb-with-omen-of-dextral-exaltation")

        self.assertGreater(len(without_conflict.hypothetical_states), len(with_conflict_outcomes.hypothetical_states))

    def test_unknown_probability_does_not_become_equal_distribution(self):
        item = parsed_fixture("quiver_6_crafted_desecrated_advanced.txt")

        outcome_set = self._outcomes(item, "dc:poe2:craft-action:orb-of-annulment")

        self.assertEqual(outcome_set.probability_completeness, OutcomeProbabilityStatus.UNKNOWN)
        self.assertFalse(any(hasattr(state, "probability") for state in outcome_set.hypothetical_states))

    def test_hypothetical_item_states_have_deterministic_identity(self):
        item = parsed_fixture("quiver_6_crafted_desecrated_advanced.txt")

        first = self._outcomes(item, "dc:poe2:craft-action:orb-of-annulment")
        second = self._outcomes(item, "dc:poe2:craft-action:orb-of-annulment")

        self.assertEqual(
            tuple(state.outcome_id for state in first.hypothetical_states),
            tuple(state.outcome_id for state in second.hypothetical_states),
        )

    def test_essence_guaranteed_component_is_separate_from_random_removal(self):
        item = parsed_fixture("quiver_1_rare_standard_advanced.txt")

        outcome_set = self._outcomes(item, "dc:poe2:craft-action:essence-of-hysteria")

        self.assertEqual(outcome_set.outcome_space_completeness, OutcomeSpaceCompleteness.PARTIAL)
        self.assertEqual(outcome_set.probability_completeness, OutcomeProbabilityStatus.UNKNOWN)
        self.assertEqual(
            outcome_set.outcome_definition.guaranteed_modifier_family_id,
            "dc:poe2:modifier-family:damagewithweapontypeskill",
        )
        self.assertTrue(all(len(state.deltas) == 2 for state in outcome_set.hypothetical_states))
        self.assertEqual(outcome_set.hypothetical_states[0].deltas[0].operation, CraftOutcomeOperation.REMOVE_MODIFIER)
        self.assertEqual(outcome_set.hypothetical_states[0].deltas[1].operation, CraftOutcomeOperation.GUARANTEE_MODIFIER)

    def test_dataset_versions_and_provenance_retained(self):
        item = with_prefix_suffix_counts(parsed_fixture("quiver_1_rare_standard_advanced.txt"), 3, 2)

        outcome_set = self._outcomes(item, "dc:poe2:craft-action:exalted-orb-with-omen-of-dextral-exaltation")

        self.assertEqual(outcome_set.dataset_versions, (GAME_DATASET_VERSION,))
        self.assertTrue(outcome_set.provenance)


if __name__ == "__main__":
    unittest.main()
