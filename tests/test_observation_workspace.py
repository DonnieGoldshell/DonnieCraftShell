import copy
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from packages.shared.donniecraftshell_contracts.curated_observation_import import build_empirical_datasets_from_curated_export
from packages.shared.donniecraftshell_contracts.observation_review import ObservationReviewDecision, ObservationReviewStatus
from packages.shared.donniecraftshell_contracts.observation_workspace import (
    OBSERVATION_WORKSPACE_STORAGE_VERSION,
    OBSERVATION_WORKSPACE_VERSION,
    FileBackedObservationWorkspaceRepository,
    ObservationWorkspaceRepository,
    ObservationWorkspaceSaveStatus,
)
from tests.test_observation_recorder import OBSERVED_AT, ObservationRecorderTests


class ObservationWorkspaceTests(unittest.TestCase):
    def test_file_backed_workspace_reloads_raw_observation_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workspace.json"
            record = recorded_export_record()
            first = FileBackedObservationWorkspaceRepository(path)

            result = first.save_record(record)
            reloaded = FileBackedObservationWorkspaceRepository(path)

            self.assertEqual(result.status, ObservationWorkspaceSaveStatus.SAVED)
            self.assertEqual(reloaded.get_entry(record["raw_record_id"]).record, record)
            self.assertEqual(reloaded.persistence_status().loaded_record_count, 1)

    def test_identical_save_is_idempotent_without_duplication(self):
        workspace = ObservationWorkspaceRepository()
        record = recorded_export_record()

        first = workspace.save_record(record)
        second = workspace.save_record(copy.deepcopy(record))

        self.assertEqual(first.status, ObservationWorkspaceSaveStatus.SAVED)
        self.assertEqual(second.status, ObservationWorkspaceSaveStatus.ALREADY_EXISTS)
        self.assertEqual(len(workspace.list_entries()), 1)

    def test_conflicting_raw_record_id_is_rejected_and_original_preserved(self):
        workspace = ObservationWorkspaceRepository()
        record = recorded_export_record()
        conflict = copy.deepcopy(record)
        conflict["outcome_id"] = "different-outcome"

        workspace.save_record(record)
        result = workspace.save_record(conflict)

        self.assertEqual(result.status, ObservationWorkspaceSaveStatus.REJECTED)
        self.assertEqual(workspace.get_entry(record["raw_record_id"]).record, record)

    def test_review_decision_persists_separately_from_raw_record(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workspace.json"
            record = recorded_export_record()
            workspace = FileBackedObservationWorkspaceRepository(path)
            workspace.save_record(record)
            before = workspace.get_entry(record["raw_record_id"]).record
            workspace.save_decision(
                ObservationReviewDecision(
                    raw_record_id=record["raw_record_id"],
                    status=ObservationReviewStatus.ACCEPTED,
                    reviewed_at=datetime(2026, 8, 14, 12, 0, tzinfo=timezone.utc),
                    note="accepted for test",
                    reviewer_id="unit-test-reviewer",
                )
            )

            reloaded = FileBackedObservationWorkspaceRepository(path)
            entry = reloaded.get_entry(record["raw_record_id"])

            self.assertEqual(entry.record, before)
            self.assertEqual(entry.decision.status, ObservationReviewStatus.ACCEPTED)
            self.assertEqual(entry.decision.note, "accepted for test")

    def test_pending_and_rejected_records_are_excluded_from_accepted_export_and_dataset_build(self):
        workspace = ObservationWorkspaceRepository()
        accepted = recorded_export_record()
        pending = recorded_export_record("pending-record")
        rejected = recorded_export_record("rejected-record")
        workspace.save_record(accepted)
        workspace.save_record(pending)
        workspace.save_record(rejected)
        workspace.save_decision(ObservationReviewDecision(raw_record_id=accepted["raw_record_id"], status=ObservationReviewStatus.ACCEPTED))
        workspace.save_decision(ObservationReviewDecision(raw_record_id=rejected["raw_record_id"], status=ObservationReviewStatus.REJECTED))

        review = workspace.review_result()
        build = build_empirical_datasets_from_curated_export(review.accepted_export, built_at=OBSERVED_AT)

        self.assertEqual([record["raw_record_id"] for record in review.accepted_export["observations"]], [accepted["raw_record_id"]])
        self.assertEqual(build.accepted_record_count, 1)
        self.assertEqual(build.datasets[0].observations[0].raw_record_ids, (accepted["raw_record_id"],))

    def test_corrupt_persisted_records_and_decisions_are_skipped_with_warnings(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workspace.json"
            valid = recorded_export_record()
            path.write_text(
                json.dumps(
                    {
                        "workspace_version": OBSERVATION_WORKSPACE_VERSION,
                        "storage_version": OBSERVATION_WORKSPACE_STORAGE_VERSION,
                        "records": [valid, {"raw_record_id": ""}, "not an object"],
                        "decisions": [
                            {"raw_record_id": valid["raw_record_id"], "status": "ACCEPTED"},
                            {"raw_record_id": "absent", "status": "ACCEPTED"},
                            {"raw_record_id": valid["raw_record_id"], "status": "NOPE"},
                        ],
                    }
                ),
                encoding="utf-8",
            )

            workspace = FileBackedObservationWorkspaceRepository(path)

            self.assertIsNotNone(workspace.get_entry(valid["raw_record_id"]))
            self.assertEqual(workspace.get_entry(valid["raw_record_id"]).decision.status, ObservationReviewStatus.ACCEPTED)
            self.assertGreaterEqual(workspace.persistence_status().skipped_entry_count, 3)
            self.assertTrue(workspace.persistence_status().warnings)

    def test_wrong_workspace_version_skips_without_rewrite(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workspace.json"
            path.write_text(
                json.dumps(
                    {
                        "workspace_version": "future-workspace-version",
                        "storage_version": OBSERVATION_WORKSPACE_STORAGE_VERSION,
                        "records": [recorded_export_record()],
                        "decisions": [],
                    },
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            before = path.read_text(encoding="utf-8")

            workspace = FileBackedObservationWorkspaceRepository(path)

            self.assertEqual(workspace.list_entries(), ())
            self.assertEqual(workspace.persistence_status().skipped_entry_count, 1)
            self.assertTrue(any("workspace_version" in warning for warning in workspace.persistence_status().warnings))
            self.assertEqual(path.read_text(encoding="utf-8"), before)

    def test_missing_storage_version_skips_without_rewrite(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workspace.json"
            path.write_text(
                json.dumps(
                    {
                        "workspace_version": OBSERVATION_WORKSPACE_VERSION,
                        "records": [recorded_export_record()],
                        "decisions": [],
                    },
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            before = path.read_text(encoding="utf-8")

            workspace = FileBackedObservationWorkspaceRepository(path)

            self.assertEqual(workspace.list_entries(), ())
            self.assertEqual(workspace.persistence_status().skipped_entry_count, 1)
            self.assertTrue(any("storage_version" in warning for warning in workspace.persistence_status().warnings))
            self.assertEqual(path.read_text(encoding="utf-8"), before)


def recorded_export_record(raw_record_id: str | None = None) -> dict:
    fixture = ObservationRecorderTests()
    fixture.setUp()
    removed = fixture.outcome_set.hypothetical_states[0].deltas[0].removed_modifier.raw_text
    after = fixture._after_without(removed)
    recorded = fixture.recorder.record(
        fixture._draft(after),
        fixture.recorder.classify_automatically(fixture.before, after, fixture.outcome_set),
    )
    record = recorded.to_export_record()
    if raw_record_id is not None:
        record["raw_record_id"] = raw_record_id
    return record


if __name__ == "__main__":
    unittest.main()
