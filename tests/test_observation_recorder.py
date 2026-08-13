import json
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from packages.shared.donniecraftshell_contracts.affix_capacity import (
    AffixStateResolver,
    load_affix_capacity_dataset,
)
from packages.shared.donniecraftshell_contracts.craft_outcomes import CraftOutcomeEngine
from packages.shared.donniecraftshell_contracts.crafting_actions import (
    CraftActionEngine,
    load_crafting_dataset,
)
from packages.shared.donniecraftshell_contracts.domain import AffixState
from packages.shared.donniecraftshell_contracts.empirical_observation_import import (
    aggregate_observations,
    load_empirical_observation_files,
)
from packages.shared.donniecraftshell_contracts.empirical_probability import EmpiricalProbabilityRepository
from packages.shared.donniecraftshell_contracts.observation_recorder import (
    CraftObservationRecorder,
    ObservationClassificationMethod,
    ObservationDraft,
)
from packages.shared.donniecraftshell_contracts.parser import parse_clipboard_item
from packages.shared.donniecraftshell_contracts.probability import ProbabilityCompleteness, ProbabilityContext
from tests.test_empirical_probability_pipeline import synthetic_outcome_set


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "poe2" / "quivers"
CRAFTING_DATASET = ROOT / "data" / "normalized" / "crafting" / "crafting-actions-poe2-quiver-2026-08-12-research" / "actions.json"
AFFIX_CAPACITY_DATASET = ROOT / "data" / "normalized" / "crafting" / "affix-capacity-poe2-2026-08-12-research" / "capacity.json"
OBSERVED_AT = datetime(2026, 8, 13, 10, 0, tzinfo=timezone.utc)


def parsed_quiver_6():
    result = parse_clipboard_item((FIXTURE_DIR / "quiver_6_crafted_desecrated_advanced.txt").read_text(encoding="utf-8"))
    assert result.item is not None
    return result.item


def action_by_id(dataset, action_id: str):
    return next(action for action in dataset.actions if action.action_id == action_id)


class ObservationRecorderTests(unittest.TestCase):
    def setUp(self):
        self.recorder = CraftObservationRecorder()
        self.before = parsed_quiver_6()
        crafting_dataset = load_crafting_dataset(CRAFTING_DATASET)
        action = action_by_id(crafting_dataset, "dc:poe2:craft-action:orb-of-annulment")
        affix = AffixStateResolver(load_affix_capacity_dataset(AFFIX_CAPACITY_DATASET)).resolve(self.before)
        applicability = CraftActionEngine(crafting_dataset).evaluate_action(action, self.before, affix)
        self.outcome_set = CraftOutcomeEngine().enumerate_outcomes(self.before, affix, action, applicability)

    def test_supported_deterministic_before_after_maps_to_existing_outcome_id(self):
        removed_modifier = self.outcome_set.hypothetical_states[0].deltas[0].removed_modifier
        after = self._after_without(removed_modifier.raw_text)

        classification = self.recorder.classify_automatically(self.before, after, self.outcome_set)

        self.assertEqual(classification.method, ObservationClassificationMethod.AUTOMATIC)
        self.assertEqual(classification.outcome_id, self.outcome_set.hypothetical_states[0].outcome_id)

    def test_non_matching_result_becomes_unclassified_not_guessed(self):
        after = replace(self.before, explicit_modifiers=self.before.explicit_modifiers, modifiers=self.before.modifiers)

        classification = self.recorder.classify_automatically(self.before, after, self.outcome_set)

        self.assertEqual(classification.method, ObservationClassificationMethod.UNCLASSIFIED)
        self.assertIsNone(classification.outcome_id)

    def test_manual_classification_is_explicitly_labeled_manual(self):
        outcome_id = self.outcome_set.hypothetical_states[1].outcome_id

        classification = self.recorder.classify_manually(
            outcome_id,
            tuple(state.outcome_id for state in self.outcome_set.hypothetical_states),
            "User selected outcome after reviewing before/after items.",
        )

        self.assertEqual(classification.method, ObservationClassificationMethod.MANUAL)
        self.assertEqual(classification.outcome_id, outcome_id)

    def test_raw_record_ids_are_unique_for_distinct_crafts_and_stable_for_reload(self):
        first_removed = self.outcome_set.hypothetical_states[0].deltas[0].removed_modifier.raw_text
        second_removed = self.outcome_set.hypothetical_states[1].deltas[0].removed_modifier.raw_text
        first = self.recorder.record(
            self._draft(self._after_without(first_removed)),
            self.recorder.classify_automatically(self.before, self._after_without(first_removed), self.outcome_set),
        )
        reloaded = self.recorder.record(
            self._draft(self._after_without(first_removed)),
            self.recorder.classify_automatically(self.before, self._after_without(first_removed), self.outcome_set),
        )
        second = self.recorder.record(
            self._draft(self._after_without(second_removed)),
            self.recorder.classify_automatically(self.before, self._after_without(second_removed), self.outcome_set),
        )

        self.assertEqual(first.raw_record_id, reloaded.raw_record_id)
        self.assertNotEqual(first.raw_record_id, second.raw_record_id)

    def test_exported_json_loads_through_importer_and_duplicate_protection(self):
        removed = self.outcome_set.hypothetical_states[0].deltas[0].removed_modifier.raw_text
        after = self._after_without(removed)
        recorded = self.recorder.record(
            self._draft(after),
            self.recorder.classify_automatically(self.before, after, self.outcome_set),
        )
        payload = self.recorder.export((recorded, recorded), exported_at=OBSERVED_AT).to_dict()

        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "recorded-observations.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            result = aggregate_observations(load_empirical_observation_files((path,)), retrieved_at=OBSERVED_AT)

        self.assertEqual(result.accepted_record_count, 1)
        self.assertEqual(result.duplicate_record_count, 1)
        self.assertEqual(result.datasets[0].observations[0].raw_record_ids, (recorded.raw_record_id,))

    def test_real_advisor_probabilities_remain_unknown_when_observations_are_only_recorded(self):
        model = EmpiricalProbabilityRepository(()).to_provider().get_probability_model(
            self.before,
            synthetic_outcome_set(),
            ProbabilityContext(evidence_dataset_version="missing"),
        )

        self.assertEqual(model.probability_completeness, ProbabilityCompleteness.UNKNOWN)
        self.assertTrue(all(entry.probability is None for entry in model.outcome_probabilities))

    def _draft(self, after):
        return ObservationDraft(
            action_id=self.outcome_set.action_id,
            source_outcome_set_id=f"{self.outcome_set.source_item_analysis_id}:{self.outcome_set.action_id}",
            item_class="Quivers",
            league="Runes of Aldur",
            before_item=self.before,
            after_item=after,
            observed_at=OBSERVED_AT,
            source_id="test-manual-recorder",
            game_version="synthetic-test-version",
            crafting_dataset_version="crafting-actions-poe2-quiver-2026-08-12-research",
            modifier_dataset_version="poe2db-unknown-version-2026-08-12-task8c-fullx1",
            synthetic=True,
        )

    def _after_without(self, raw_text: str):
        explicit = tuple(modifier for modifier in self.before.explicit_modifiers if modifier.raw_text != raw_text)
        return replace(
            self.before,
            explicit_modifiers=explicit,
            modifiers=self.before.implicit_modifiers + explicit + self.before.special_modifiers,
            affix_state=AffixState(
                known_prefixes=tuple(modifier for modifier in explicit if modifier.affix_type.value == "PREFIX"),
                known_suffixes=tuple(modifier for modifier in explicit if modifier.affix_type.value == "SUFFIX"),
                observed_prefix_count=sum(1 for modifier in explicit if modifier.affix_type.value == "PREFIX"),
                observed_suffix_count=sum(1 for modifier in explicit if modifier.affix_type.value == "SUFFIX"),
            ),
        )


if __name__ == "__main__":
    unittest.main()
