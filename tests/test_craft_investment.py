from __future__ import annotations

import unittest
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from packages.shared.donniecraftshell_contracts.craft_investment import (
    CraftInvestmentCalculator,
    CraftInvestmentEntry,
    CraftInvestmentEntryKind,
    CraftInvestmentLedger,
    CraftInvestmentWorkspaceRepository,
    CurrentMarketValuation,
    CurrentProfitPositionStatus,
    FileBackedCraftInvestmentWorkspaceRepository,
)
from packages.shared.donniecraftshell_contracts.domain import EconomicValue


EXALT = "dc:poe2:economy-asset:currency:exalted-orb"
DIVINE = "dc:poe2:economy-asset:currency:divine-orb"


def _entry(
    entry_id: str,
    kind: CraftInvestmentEntryKind,
    amount: str,
    normalized: str | None,
) -> CraftInvestmentEntry:
    return CraftInvestmentEntry(
        entry_id=entry_id,
        ledger_id="ledger-1",
        subject_id="current",
        kind=kind,
        description=entry_id,
        amount=Decimal(amount),
        currency_asset_id=DIVINE,
        normalized_value=EconomicValue(Decimal(normalized)) if normalized is not None else None,
        incurred_at=datetime(2026, 8, 28, tzinfo=timezone.utc),
    )


class CraftInvestmentTests(unittest.TestCase):
    def test_base_and_realized_spend_sum_deterministically(self) -> None:
        ledger = CraftInvestmentLedger(
            ledger_id="ledger-1",
            subject_id="current",
            entries=(
                _entry("base", CraftInvestmentEntryKind.BASE_ACQUISITION, "12", "120"),
                _entry("omen", CraftInvestmentEntryKind.CRAFTING_SPEND, "2", "20"),
                _entry("exalt", CraftInvestmentEntryKind.CRAFTING_SPEND, "1", "10"),
            ),
        )

        basis = CraftInvestmentCalculator().cost_basis(ledger)

        self.assertEqual(basis.status.value, "COMPLETE")
        self.assertEqual(basis.total_invested, EconomicValue(Decimal("150")))
        self.assertEqual(basis.base_acquisition_total, EconomicValue(Decimal("120")))
        self.assertEqual(basis.crafting_spend_total, EconomicValue(Decimal("30")))

    def test_missing_or_unconvertible_entries_make_cost_basis_incomplete_not_zero(self) -> None:
        ledger = CraftInvestmentLedger(
            ledger_id="ledger-1",
            subject_id="current",
            entries=(
                _entry("base", CraftInvestmentEntryKind.BASE_ACQUISITION, "12", "120"),
                _entry("unknown", CraftInvestmentEntryKind.CRAFTING_SPEND, "1", None),
            ),
        )

        basis = CraftInvestmentCalculator().cost_basis(ledger)

        self.assertEqual(basis.status.value, "INCOMPLETE")
        self.assertIsNone(basis.total_invested)
        self.assertEqual(basis.known_invested.amount, Decimal("120"))
        self.assertEqual(basis.incomplete_entry_ids, ("unknown",))

    def test_estimated_market_value_yields_point_profit_and_roi(self) -> None:
        basis = CraftInvestmentCalculator().cost_basis(
            CraftInvestmentLedger(
                ledger_id="ledger-1",
                subject_id="current",
                entries=(_entry("base", CraftInvestmentEntryKind.BASE_ACQUISITION, "10", "100"),),
            )
        )
        market = CurrentMarketValuation(
            status="ESTIMATED_MARKET_VALUE",
            estimated_value=EconomicValue(Decimal("150")),
            legacy_statistical_median=EconomicValue(Decimal("999")),
            confidence_level="LOW",
        )

        position = CraftInvestmentCalculator().current_profit_position(basis, market)

        self.assertEqual(position.status, CurrentProfitPositionStatus.CURRENT_PROFIT_ESTIMATE_AVAILABLE)
        self.assertEqual(position.unrealized_profit, EconomicValue(Decimal("50")))
        self.assertEqual(position.unrealized_roi, Decimal("0.5"))

    def test_supported_range_only_yields_range_without_point_profit(self) -> None:
        basis = CraftInvestmentCalculator().cost_basis(
            CraftInvestmentLedger(
                ledger_id="ledger-1",
                subject_id="current",
                entries=(_entry("base", CraftInvestmentEntryKind.BASE_ACQUISITION, "10", "100"),),
            )
        )
        market = CurrentMarketValuation(
            status="SUPPORTED_RANGE_ONLY",
            supported_low=EconomicValue(Decimal("45")),
            supported_high=EconomicValue(Decimal("450")),
            legacy_statistical_median=EconomicValue(Decimal("450")),
        )

        position = CraftInvestmentCalculator().current_profit_position(basis, market)

        self.assertEqual(position.status, CurrentProfitPositionStatus.SUPPORTED_PROFIT_RANGE_ONLY)
        self.assertIsNone(position.unrealized_profit)
        self.assertIsNone(position.unrealized_roi)
        self.assertEqual(position.supported_profit_low, EconomicValue(Decimal("-55")))
        self.assertEqual(position.supported_profit_high, EconomicValue(Decimal("350")))

    def test_insufficient_market_evidence_does_not_use_legacy_median(self) -> None:
        basis = CraftInvestmentCalculator().cost_basis(
            CraftInvestmentLedger(
                ledger_id="ledger-1",
                subject_id="current",
                entries=(_entry("base", CraftInvestmentEntryKind.BASE_ACQUISITION, "10", "100"),),
            )
        )
        market = CurrentMarketValuation(
            status="INSUFFICIENT_MARKET_EVIDENCE",
            legacy_statistical_median=EconomicValue(Decimal("450")),
        )

        position = CraftInvestmentCalculator().current_profit_position(basis, market)

        self.assertEqual(position.status, CurrentProfitPositionStatus.INSUFFICIENT_MARKET_EVIDENCE)
        self.assertIsNone(position.unrealized_profit)
        self.assertIn("Legacy/manual median was not used", " ".join(position.warnings))

    def test_negative_unrealized_profit_is_preserved(self) -> None:
        basis = CraftInvestmentCalculator().cost_basis(
            CraftInvestmentLedger(
                ledger_id="ledger-1",
                subject_id="current",
                entries=(_entry("base", CraftInvestmentEntryKind.BASE_ACQUISITION, "10", "100"),),
            )
        )

        position = CraftInvestmentCalculator().current_profit_position(
            basis,
            CurrentMarketValuation(status="ESTIMATED_MARKET_VALUE", estimated_value=EconomicValue(Decimal("80"))),
        )

        self.assertEqual(position.unrealized_profit, EconomicValue(Decimal("-20")))
        self.assertEqual(position.unrealized_roi, Decimal("-0.2"))

    def test_workspace_round_trip_preserves_identity_and_amounts(self) -> None:
        path = Path(".tmp-tests") / "craft_investment_workspace_round_trip.json"
        if path.exists():
            path.unlink()
        first = FileBackedCraftInvestmentWorkspaceRepository(path)
        result = first.save_record(
            {
                "entry_id": "entry-1",
                "ledger_id": "ledger-1",
                "subject_id": "current",
                "kind": "BASE_ACQUISITION",
                "description": "Base",
                "amount": "12",
                "currency_asset_id": DIVINE,
                "normalized_value": {"amount": "120", "unit": "EXALTED_ECONOMIC_UNIT"},
                "incurred_at": "2026-08-28T00:00:00+00:00",
            }
        )

        self.assertEqual(result.status.value, "SAVED")
        second = FileBackedCraftInvestmentWorkspaceRepository(path)
        records = second.list_records("ledger-1")

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["entry_id"], "entry-1")
        self.assertEqual(records[0]["amount"], "12")
        self.assertEqual(records[0]["normalized_value"]["amount"], "120")

    def test_in_memory_workspace_rejects_conflicting_duplicate_entry_id(self) -> None:
        workspace = CraftInvestmentWorkspaceRepository()
        record = {
            "entry_id": "entry-1",
            "ledger_id": "ledger-1",
            "subject_id": "current",
            "kind": "CRAFTING_SPEND",
            "description": "Spent",
            "amount": "1",
            "currency_asset_id": EXALT,
            "normalized_value": {"amount": "1", "unit": "EXALTED_ECONOMIC_UNIT"},
        }
        self.assertEqual(workspace.save_record(record).status.value, "SAVED")

        changed = {**record, "amount": "2"}
        result = workspace.save_record(changed)

        self.assertEqual(result.status.value, "REJECTED")


class CraftInvestmentApiTests(unittest.TestCase):
    def setUp(self) -> None:
        from fastapi.testclient import TestClient
        from services.api.app.main import app

        self.client = TestClient(app)

    def test_preview_api_range_only_does_not_emit_point_profit(self) -> None:
        response = self.client.post(
            "/api/v1/advisor/craft-investment/preview",
            json={
                "ledger_id": "ledger-1",
                "subject_id": "current",
                "entries": [
                    {
                        "entry_id": "base",
                        "kind": "BASE_ACQUISITION",
                        "description": "Base",
                        "amount": "100",
                        "currency_asset_id": EXALT,
                        "normalized_value": {"amount": "100", "unit": "EXALTED_ECONOMIC_UNIT"},
                    }
                ],
                "market_valuation": {
                    "status": "SUPPORTED_RANGE_ONLY",
                    "supported_low": {"amount": "45", "unit": "EXALTED_ECONOMIC_UNIT"},
                    "supported_high": {"amount": "450", "unit": "EXALTED_ECONOMIC_UNIT"},
                    "legacy_statistical_median": {"amount": "450", "unit": "EXALTED_ECONOMIC_UNIT"},
                },
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        position = payload["current_profit_position"]
        self.assertEqual(position["status"], "SUPPORTED_PROFIT_RANGE_ONLY")
        self.assertIsNone(position["unrealized_profit"])
        self.assertEqual(position["supported_profit_low"]["amount"], "-55")
        self.assertEqual(position["supported_profit_high"]["amount"], "350")

    def test_openapi_exposes_craft_investment_contracts(self) -> None:
        openapi = self.client.get("/openapi.json").json()

        self.assertIn("/api/v1/advisor/craft-investment/preview", openapi["paths"])
        self.assertIn("/api/v1/advisor/craft-investment/workspace/entries", openapi["paths"])
        schemas = openapi["components"]["schemas"]
        self.assertIn("CraftInvestmentPreviewRequestDto", schemas)
        self.assertIn("CurrentProfitPositionDto", schemas)


if __name__ == "__main__":
    unittest.main()
