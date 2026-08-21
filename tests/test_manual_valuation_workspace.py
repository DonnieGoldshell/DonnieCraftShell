from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from packages.shared.donniecraftshell_contracts.manual_valuation_workspace import (
    FileBackedManualValuationWorkspaceRepository,
    MANUAL_VALUATION_WORKSPACE_STORAGE_VERSION,
    MANUAL_VALUATION_WORKSPACE_VERSION,
    ManualValuationWorkspaceRepository,
    ManualValuationWorkspaceSaveStatus,
)


def record(
    evidence_id: str | None = None,
    subject_id: str = "current",
    subject_type: str = "CURRENT_ITEM",
    outcome_id: str | None = None,
    amount: str = "100",
    external_listing_id: str | None = "listing-1",
) -> dict:
    payload = {
        "subject_id": subject_id,
        "subject_type": subject_type,
        "league": "Runes of Aldur",
        "strategy": "STRICT",
        "amount": amount,
        "currency_asset_id": "dc:poe2:economy-asset:currency:exalted-orb",
        "external_listing_id": external_listing_id,
        "observed_at": "2026-08-13T10:00:00+00:00",
        "item_summary": "manual comparable",
        "notes": "synthetic test evidence",
    }
    if evidence_id is not None:
        payload["evidence_id"] = evidence_id
    if outcome_id is not None:
        payload["outcome_id"] = outcome_id
    return payload


class ManualValuationWorkspaceTests(unittest.TestCase):
    def test_current_item_evidence_survives_restart_under_current_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manual_valuation_workspace.json"
            first = FileBackedManualValuationWorkspaceRepository(path)
            result = first.save_record(record())
            self.assertEqual(result.status, ManualValuationWorkspaceSaveStatus.SAVED)

            second = FileBackedManualValuationWorkspaceRepository(path)

            self.assertEqual(len(second.list_records("current")), 1)
            self.assertEqual(second.list_records("outcome:outcome-1"), ())
            self.assertEqual(second.persistence_status().storage_mode, "FILE")

    def test_outcome_evidence_survives_restart_and_isolated_by_canonical_subject(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manual_valuation_workspace.json"
            first = FileBackedManualValuationWorkspaceRepository(path)
            result = first.save_record(
                record(
                    subject_id="outcome:outcome-2",
                    subject_type="HYPOTHETICAL_OUTCOME",
                    outcome_id="outcome-2",
                    external_listing_id="outcome-listing",
                )
            )
            self.assertEqual(result.status, ManualValuationWorkspaceSaveStatus.SAVED)

            second = FileBackedManualValuationWorkspaceRepository(path)

            self.assertEqual(len(second.list_records("outcome:outcome-2")), 1)
            self.assertEqual(second.list_records("outcome:outcome-1"), ())
            self.assertEqual(second.list_records("current"), ())

    def test_mismatched_subject_outcome_identity_is_rejected(self):
        repository = ManualValuationWorkspaceRepository()

        result = repository.save_record(
            record(
                subject_id="outcome:outcome-1",
                subject_type="HYPOTHETICAL_OUTCOME",
                outcome_id="outcome-2",
            )
        )

        self.assertEqual(result.status, ManualValuationWorkspaceSaveStatus.REJECTED)
        self.assertIn("subject_id must be outcome:outcome-2", result.warnings[0])

    def test_identical_save_idempotent_and_conflict_rejected(self):
        repository = ManualValuationWorkspaceRepository()
        saved = repository.save_record(record(evidence_id="manual-evidence-1"))
        identical = repository.save_record(record(evidence_id="manual-evidence-1"))
        conflict = repository.save_record(record(evidence_id="manual-evidence-1", amount="101"))

        self.assertEqual(saved.status, ManualValuationWorkspaceSaveStatus.SAVED)
        self.assertEqual(identical.status, ManualValuationWorkspaceSaveStatus.ALREADY_EXISTS)
        self.assertEqual(conflict.status, ManualValuationWorkspaceSaveStatus.REJECTED)
        self.assertEqual(repository.list_records()[0]["amount"], "100")

    def test_update_and_delete_are_subject_scoped_by_record_identity(self):
        repository = ManualValuationWorkspaceRepository()
        repository.save_record(record(evidence_id="current-evidence"))
        repository.save_record(
            record(
                evidence_id="outcome-evidence",
                subject_id="outcome:outcome-1",
                subject_type="HYPOTHETICAL_OUTCOME",
                outcome_id="outcome-1",
                external_listing_id="outcome-listing",
            )
        )

        updated = repository.update_record("current-evidence", record(evidence_id="current-evidence", amount="120"))
        deleted = repository.delete_record("current-evidence")

        self.assertEqual(updated.status, ManualValuationWorkspaceSaveStatus.UPDATED)
        self.assertEqual(deleted.status, ManualValuationWorkspaceSaveStatus.DELETED)
        self.assertEqual(repository.list_records("current"), ())
        self.assertEqual(len(repository.list_records("outcome:outcome-1")), 1)

    def test_persistence_failure_rolls_back_memory_and_preserves_previous_file(self):
        class FailingRepository(FileBackedManualValuationWorkspaceRepository):
            fail_next = False

            def _persist(self) -> None:
                if self.fail_next:
                    raise OSError("synthetic write failure")
                super()._persist()

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manual_valuation_workspace.json"
            repository = FailingRepository(path)
            first = repository.save_record(record(evidence_id="first"))
            self.assertEqual(first.status, ManualValuationWorkspaceSaveStatus.SAVED)
            before = path.read_text(encoding="utf-8")

            repository.fail_next = True
            failed = repository.save_record(record(evidence_id="second", external_listing_id="listing-2"))

            self.assertEqual(failed.status, ManualValuationWorkspaceSaveStatus.REJECTED)
            self.assertEqual(path.read_text(encoding="utf-8"), before)
            self.assertEqual([item["evidence_id"] for item in repository.list_records()], ["first"])

    def test_incompatible_storage_version_is_skipped_with_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manual_valuation_workspace.json"
            path.write_text(
                json.dumps(
                    {
                        "workspace_version": MANUAL_VALUATION_WORKSPACE_VERSION,
                        "storage_version": "future-version",
                        "records": [record()],
                    }
                ),
                encoding="utf-8",
            )

            repository = FileBackedManualValuationWorkspaceRepository(path)

            self.assertEqual(repository.list_records(), ())
            self.assertEqual(repository.persistence_status().skipped_evidence_count, 1)
            self.assertIn("storage_version", repository.persistence_status().warnings[0])

    def test_export_backup_uses_versioned_envelope(self):
        repository = ManualValuationWorkspaceRepository()
        repository.save_record(record())

        backup = repository.export_backup()

        self.assertEqual(backup["workspace_version"], MANUAL_VALUATION_WORKSPACE_VERSION)
        self.assertEqual(backup["storage_version"], MANUAL_VALUATION_WORKSPACE_STORAGE_VERSION)
        self.assertEqual(len(backup["records"]), 1)


if __name__ == "__main__":
    unittest.main()
