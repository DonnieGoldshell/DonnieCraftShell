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
from packages.shared.donniecraftshell_contracts.guided_observation_capture import (
    GuidedCaptureSessionContext,
    GuidedTrialPreviewStatus,
    confirmed_guided_classification,
    preview_guided_trial,
)
from packages.shared.donniecraftshell_contracts.observation_recorder import (
    CraftObservationRecorder,
    ObservationDraft,
)
from packages.shared.donniecraftshell_contracts.observation_workspace import (
    ObservationWorkspaceRepository,
    ObservationWorkspaceSaveStatus,
)
from packages.shared.donniecraftshell_contracts.parser import parse_clipboard_item
from packages.shared.donniecraftshell_contracts.probability import ProbabilityCompleteness, ProbabilityContext
from tests.test_empirical_probability_pipeline import synthetic_outcome_set


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "poe2" / "quivers"
CRAFTING_DATASET_ID = "crafting-actions-poe2-quiver-2026-08-12-research"
GAME_DATASET_ID = "poe2db-unknown-version-2026-08-12-task8c-fullx1"
CRAFTING_DATASET = ROOT / "data" / "normalized" / "crafting" / CRAFTING_DATASET_ID / "actions.json"
AFFIX_CAPACITY_DATASET = ROOT / "data" / "normalized" / "crafting" / "affix-capacity-poe2-2026-08-12-research" / "capacity.json"
OBSERVED_AT = datetime(2026, 9, 14, 8, 0, tzinfo=timezone.utc)


def parsed_quiver_6():
    result = parse_clipboard_item((FIXTURE_DIR / "quiver_6_crafted_desecrated_advanced.txt").read_text(encoding="utf-8"))
    assert result.item is not None
    return result.item


class GuidedObservationCaptureTests(unittest.TestCase):
    def setUp(self):
        self.before = parsed_quiver_6()
        crafting_dataset = load_crafting_dataset(CRAFTING_DATASET)
        self.action = next(action for action in crafting_dataset.actions if action.action_id == "dc:poe2:craft-action:orb-of-annulment")
        affix = AffixStateResolver(load_affix_capacity_dataset(AFFIX_CAPACITY_DATASET)).resolve(self.before)
        applicability = CraftActionEngine(crafting_dataset).evaluate_action(self.action, self.before, affix)
        self.outcome_set = CraftOutcomeEngine().enumerate_outcomes(self.before, affix, self.action, applicability)
        self.session = GuidedCaptureSessionContext(
            action_id=self.action.action_id,
            item_class="Quivers",
            league="Runes of Aldur",
            game="Path of Exile 2",
            game_version="0.3.0-test",
            crafting_dataset_version=CRAFTING_DATASET_ID,
            modifier_dataset_version=GAME_DATASET_ID,
            source_id="manual-annulment-lab-2026-09-14",
            source_uri="local://tests/guided-annulment-session",
            notes="Synthetic clipboard fixture exercising real-trial capture contracts.",
        )

    def test_valid_one_modifier_removal_proposes_outcome_without_accepting_it(self):
        removed = self.outcome_set.hypothetical_states[0].deltas[0].removed_modifier
        after = self._after_without(removed.raw_text)

        preview = preview_guided_trial(self.session, self.before, after, self.outcome_set, OBSERVED_AT)

        self.assertEqual(preview.status, GuidedTrialPreviewStatus.PROPOSED_OUTCOME)
        self.assertEqual(preview.proposed_outcome_id, self.outcome_set.hypothetical_states[0].outcome_id)
        self.assertTrue(preview.requires_operator_confirmation)
        self.assertEqual(len(preview.diff.removed_modifiers), 1)
        self.assertEqual(preview.diff.removed_modifiers[0].raw_text, removed.raw_text)
        self.assertEqual(preview.diff.added_modifiers, ())

    def test_preview_and_trial_identity_are_deterministic_for_same_session_and_items(self):
        removed = self.outcome_set.hypothetical_states[1].deltas[0].removed_modifier.raw_text
        after = self._after_without(removed)

        first = preview_guided_trial(self.session, self.before, after, self.outcome_set, OBSERVED_AT)
        second = preview_guided_trial(self.session, self.before, after, self.outcome_set, OBSERVED_AT)

        self.assertEqual(first.session_id, second.session_id)
        self.assertEqual(first.trial_id, second.trial_id)
        self.assertEqual(first.before_raw_sha256, second.before_raw_sha256)
        self.assertEqual(first.after_raw_sha256, second.after_raw_sha256)

    def test_explicit_confirmation_is_required_before_record_is_classified(self):
        removed = self.outcome_set.hypothetical_states[0].deltas[0].removed_modifier.raw_text
        preview = preview_guided_trial(self.session, self.before, self._after_without(removed), self.outcome_set, OBSERVED_AT)

        with self.assertRaises(ValueError):
            confirmed_guided_classification(
                preview,
                operator_confirmed=False,
                confirmed_outcome_id=preview.proposed_outcome_id,
            )

    def test_confirmed_trial_flows_to_workspace_and_importer_without_duplicate_inflation(self):
        removed = self.outcome_set.hypothetical_states[0].deltas[0].removed_modifier.raw_text
        after = self._after_without(removed)
        preview = preview_guided_trial(self.session, self.before, after, self.outcome_set, OBSERVED_AT)
        classification = confirmed_guided_classification(
            preview,
            operator_confirmed=True,
            confirmed_outcome_id=preview.proposed_outcome_id,
            reason="operator confirmed single removed modifier",
        )
        recorder = CraftObservationRecorder()
        recorded = recorder.record(
            ObservationDraft(
                action_id=self.session.action_id,
                source_outcome_set_id=preview.source_outcome_set_id,
                item_class="Quivers",
                league=self.session.league,
                before_item=self.before,
                after_item=after,
                observed_at=OBSERVED_AT,
                source_id=self.session.source_id,
                game=self.session.game,
                game_version=self.session.game_version,
                crafting_dataset_version=self.session.crafting_dataset_version,
                modifier_dataset_version=self.session.modifier_dataset_version,
                source_uri=self.session.source_uri,
                synthetic=False,
            ),
            classification,
        )
        workspace = ObservationWorkspaceRepository()
        first_save = workspace.save_record(recorded.to_export_record())
        second_save = workspace.save_record(recorded.to_export_record())
        workspace.save_decision(workspace.list_entries()[0].decision)

        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "guided-export.json"
            path.write_text(json.dumps({"observations": [entry.record for entry in workspace.list_entries()] * 2}), encoding="utf-8")
            result = aggregate_observations(load_empirical_observation_files((path,)), retrieved_at=OBSERVED_AT)

        self.assertEqual(first_save.status, ObservationWorkspaceSaveStatus.SAVED)
        self.assertEqual(second_save.status, ObservationWorkspaceSaveStatus.ALREADY_EXISTS)
        self.assertEqual(result.accepted_record_count, 1)
        self.assertEqual(result.duplicate_record_count, 1)
        self.assertEqual(result.datasets[0].game_version, "0.3.0-test")
        self.assertEqual(result.datasets[0].observations[0].raw_record_ids, (recorded.raw_record_id,))

    def test_ambiguous_multi_change_diff_fails_closed_as_unclassified(self):
        removed_a = self.outcome_set.hypothetical_states[0].deltas[0].removed_modifier.raw_text
        removed_b = self.outcome_set.hypothetical_states[1].deltas[0].removed_modifier.raw_text
        after = self._after_without(removed_a, removed_b)

        preview = preview_guided_trial(self.session, self.before, after, self.outcome_set, OBSERVED_AT)

        self.assertEqual(preview.status, GuidedTrialPreviewStatus.UNCLASSIFIED)
        self.assertIsNone(preview.proposed_outcome_id)
        self.assertEqual(len(preview.diff.removed_modifiers), 2)

    def test_probability_remains_unknown_because_capture_workspace_exists(self):
        model = EmpiricalProbabilityRepository(()).to_provider().get_probability_model(
            self.before,
            synthetic_outcome_set(),
            ProbabilityContext(evidence_dataset_version="missing"),
        )

        self.assertEqual(model.probability_completeness, ProbabilityCompleteness.UNKNOWN)

    def _after_without(self, *raw_texts: str):
        removed = set(raw_texts)
        explicit = tuple(modifier for modifier in self.before.explicit_modifiers if modifier.raw_text not in removed)
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
