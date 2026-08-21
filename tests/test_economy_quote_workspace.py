import json
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from packages.shared.donniecraftshell_contracts.economy import (
    EXALTED_ASSET_ID,
    ORB_OF_ANNULMENT_ASSET_ID,
    PERFECT_EXALTED_ASSET_ID,
    FreshnessState,
)
from packages.shared.donniecraftshell_contracts.economy_quote_workspace import (
    ECONOMY_QUOTE_WORKSPACE_STORAGE_VERSION,
    ECONOMY_QUOTE_WORKSPACE_VERSION,
    FileBackedEconomyQuoteWorkspaceRepository,
    EconomyQuoteWorkspaceRepository,
    EconomyQuoteWorkspaceSaveStatus,
)
from packages.shared.donniecraftshell_contracts.economy_repository import EconomyRepository


LEAGUE = "Runes of Aldur"
OTHER_LEAGUE = "Different League"
AS_OF = datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc)
OBSERVED = "2026-08-21T10:30:00+00:00"
TMP_ROOT = Path(__file__).resolve().parents[1] / ".tmp-tests"


def quote_record(**overrides):
    return {
        "evidence_id": "local-annulment",
        "league": LEAGUE,
        "asset_id": ORB_OF_ANNULMENT_ASSET_ID,
        "amount": "7.5",
        "currency_asset_id": EXALTED_ASSET_ID,
        "observed_at": OBSERVED,
        "source_type": "MANUAL_RESEARCH",
        "source_reference": "operator-note-1",
        "notes": "Synthetic test operator quote.",
        **overrides,
    }


class EconomyQuoteWorkspaceTests(unittest.TestCase):
    def test_save_list_update_delete_and_clear_quotes(self):
        workspace = EconomyQuoteWorkspaceRepository()

        saved = workspace.save_record(quote_record())
        self.assertEqual(saved.status, EconomyQuoteWorkspaceSaveStatus.SAVED)
        self.assertEqual(len(workspace.list_records(LEAGUE, ORB_OF_ANNULMENT_ASSET_ID)), 1)

        updated = workspace.update_record("local-annulment", quote_record(amount="8.25"))
        self.assertEqual(updated.status, EconomyQuoteWorkspaceSaveStatus.UPDATED)
        self.assertEqual(workspace.list_records()[0]["amount"], "8.25")

        deleted = workspace.delete_record("local-annulment")
        self.assertEqual(deleted.status, EconomyQuoteWorkspaceSaveStatus.DELETED)
        self.assertEqual(workspace.list_records(), ())

        workspace.save_record(quote_record(evidence_id="a"))
        workspace.save_record(quote_record(evidence_id="b", asset_id=PERFECT_EXALTED_ASSET_ID))
        cleared = workspace.clear_quotes(LEAGUE)
        self.assertEqual(cleared.status, EconomyQuoteWorkspaceSaveStatus.CLEARED)
        self.assertEqual(len(cleared.records), 2)

    def test_conflicting_evidence_id_does_not_silently_overwrite(self):
        workspace = EconomyQuoteWorkspaceRepository()
        self.assertEqual(workspace.save_record(quote_record()).status, EconomyQuoteWorkspaceSaveStatus.SAVED)

        conflict = workspace.save_record(quote_record(amount="9"))

        self.assertEqual(conflict.status, EconomyQuoteWorkspaceSaveStatus.REJECTED)
        self.assertEqual(workspace.list_records()[0]["amount"], "7.5")

    def test_file_persistence_survives_reload_and_rejects_corrupt_storage(self):
        TMP_ROOT.mkdir(exist_ok=True)
        path = TMP_ROOT / "economy_quotes_persistence_test.json"
        path.unlink(missing_ok=True)
        try:
            workspace = FileBackedEconomyQuoteWorkspaceRepository(path)
            saved = workspace.save_record(quote_record())
            self.assertEqual(saved.status, EconomyQuoteWorkspaceSaveStatus.SAVED)

            reloaded = FileBackedEconomyQuoteWorkspaceRepository(path)

            self.assertEqual(len(reloaded.list_records()), 1)
            self.assertEqual(reloaded.persistence_status().loaded_quote_count, 1)

            with open(path, "w", encoding="utf-8") as handle:
                json.dump({"workspace_version": "wrong", "storage_version": ECONOMY_QUOTE_WORKSPACE_STORAGE_VERSION, "records": []}, handle)
            corrupt = FileBackedEconomyQuoteWorkspaceRepository(path)
            self.assertEqual(corrupt.list_records(), ())
            self.assertGreater(corrupt.persistence_status().skipped_quote_count, 0)
        finally:
            path.unlink(missing_ok=True)
            path.with_name(f"{path.name}.tmp").unlink(missing_ok=True)

    def test_persistence_failure_rolls_back_memory(self):
        class FailingRepository(FileBackedEconomyQuoteWorkspaceRepository):
            def _persist(self) -> None:
                raise OSError("disk unavailable")

        TMP_ROOT.mkdir(exist_ok=True)
        path = TMP_ROOT / "economy_quotes_rollback_test.json"
        path.unlink(missing_ok=True)
        try:
            workspace = FailingRepository(path)

            result = workspace.save_record(quote_record())

            self.assertEqual(result.status, EconomyQuoteWorkspaceSaveStatus.REJECTED)
            self.assertEqual(workspace.list_records(), ())
        finally:
            path.unlink(missing_ok=True)
            path.with_name(f"{path.name}.tmp").unlink(missing_ok=True)

    def test_league_isolation_and_exact_asset_semantics(self):
        workspace = EconomyQuoteWorkspaceRepository()
        workspace.save_record(quote_record())
        workspace.save_record(
            quote_record(
                evidence_id="other-league-annulment",
                league=OTHER_LEAGUE,
                amount="99",
            )
        )
        base = EconomyRepository(())

        repository = workspace.economy_repository(base, LEAGUE, AS_OF)

        self.assertEqual(
            repository.get_current_quote(LEAGUE, ORB_OF_ANNULMENT_ASSET_ID, AS_OF).normalized_value.amount,
            Decimal("7.5"),
        )
        self.assertIsNone(repository.get_current_quote(OTHER_LEAGUE, ORB_OF_ANNULMENT_ASSET_ID, AS_OF))
        self.assertIsNone(repository.get_current_quote(LEAGUE, PERFECT_EXALTED_ASSET_ID, AS_OF))

    def test_stale_quote_retains_explicit_freshness(self):
        workspace = EconomyQuoteWorkspaceRepository()
        workspace.save_record(quote_record(observed_at=(AS_OF - timedelta(hours=8)).isoformat()))

        quote = workspace.economy_repository(EconomyRepository(()), LEAGUE, AS_OF).get_current_quote(
            LEAGUE,
            ORB_OF_ANNULMENT_ASSET_ID,
            AS_OF,
        )

        self.assertEqual(quote.freshness, FreshnessState.STALE)

    def test_invalid_quote_rejected(self):
        workspace = EconomyQuoteWorkspaceRepository()

        negative = workspace.save_record(quote_record(amount="-1"))
        unsupported_currency = workspace.save_record(quote_record(evidence_id="div", currency_asset_id="dc:poe2:economy-asset:currency:divine-orb"))

        self.assertEqual(negative.status, EconomyQuoteWorkspaceSaveStatus.REJECTED)
        self.assertEqual(unsupported_currency.status, EconomyQuoteWorkspaceSaveStatus.REJECTED)

    def test_export_backup_has_versioned_envelope(self):
        workspace = EconomyQuoteWorkspaceRepository()
        workspace.save_record(quote_record())

        backup = workspace.export_backup()

        self.assertEqual(backup["workspace_version"], ECONOMY_QUOTE_WORKSPACE_VERSION)
        self.assertEqual(backup["storage_version"], ECONOMY_QUOTE_WORKSPACE_STORAGE_VERSION)
        self.assertEqual(len(backup["records"]), 1)


if __name__ == "__main__":
    unittest.main()
