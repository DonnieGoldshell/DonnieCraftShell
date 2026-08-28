"""Craft investment ledger and current profit-position contracts.

This module tracks realized operator-entered spend only. It does not infer
historical spend from item modifiers, current action candidates, or market
valuation diagnostics.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any

from .domain import DataProvenance, EconomicValue, SourceType, VerificationStatus
from .economy import EXALTED_ECONOMIC_UNIT


CRAFT_INVESTMENT_LEDGER_VERSION = "dc-craft-investment-ledger-v1"
CRAFT_INVESTMENT_WORKSPACE_VERSION = "dc-craft-investment-workspace-v1"
CRAFT_INVESTMENT_WORKSPACE_STORAGE_VERSION = "dc-craft-investment-workspace-storage-v1"


class CraftInvestmentEntryKind(str, Enum):
    BASE_ACQUISITION = "BASE_ACQUISITION"
    CRAFTING_SPEND = "CRAFTING_SPEND"


class CraftInvestmentCostBasisStatus(str, Enum):
    COMPLETE = "COMPLETE"
    INCOMPLETE = "INCOMPLETE"


class CurrentProfitPositionStatus(str, Enum):
    INCOMPLETE_COST_BASIS = "INCOMPLETE_COST_BASIS"
    INSUFFICIENT_MARKET_EVIDENCE = "INSUFFICIENT_MARKET_EVIDENCE"
    SUPPORTED_PROFIT_RANGE_ONLY = "SUPPORTED_PROFIT_RANGE_ONLY"
    CURRENT_PROFIT_ESTIMATE_AVAILABLE = "CURRENT_PROFIT_ESTIMATE_AVAILABLE"


class CraftInvestmentWorkspaceSaveStatus(str, Enum):
    SAVED = "SAVED"
    UPDATED = "UPDATED"
    ALREADY_EXISTS = "ALREADY_EXISTS"
    DELETED = "DELETED"
    CLEARED = "CLEARED"
    NOT_FOUND = "NOT_FOUND"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class CraftInvestmentEntry:
    entry_id: str
    ledger_id: str
    subject_id: str
    kind: CraftInvestmentEntryKind
    description: str
    amount: Decimal
    currency_asset_id: str
    normalized_value: EconomicValue | None = None
    economy_snapshot_id: str | None = None
    action_id: str | None = None
    incurred_at: datetime | None = None
    source_reference: str | None = None
    notes: str | None = None
    provenance: tuple[DataProvenance, ...] = ()
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.entry_id:
            raise ValueError("entry_id is required")
        if not self.ledger_id:
            raise ValueError("ledger_id is required")
        if not self.subject_id:
            raise ValueError("subject_id is required")
        amount = Decimal(self.amount)
        if amount < 0:
            raise ValueError("investment entry amount cannot be negative")
        object.__setattr__(self, "amount", amount)
        object.__setattr__(self, "kind", CraftInvestmentEntryKind(self.kind))
        if self.normalized_value is not None and self.normalized_value.unit != EXALTED_ECONOMIC_UNIT:
            raise ValueError("normalized investment value must use EXALTED_ECONOMIC_UNIT")


@dataclass(frozen=True)
class CraftInvestmentLedger:
    ledger_id: str
    subject_id: str
    entries: tuple[CraftInvestmentEntry, ...] = ()
    ledger_version: str = CRAFT_INVESTMENT_LEDGER_VERSION
    provenance: tuple[DataProvenance, ...] = ()
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.ledger_id:
            raise ValueError("ledger_id is required")
        if not self.subject_id:
            raise ValueError("subject_id is required")
        for entry in self.entries:
            if entry.ledger_id != self.ledger_id:
                raise ValueError("ledger entries must match ledger_id")
            if entry.subject_id != self.subject_id:
                raise ValueError("ledger entries must match subject_id")

    @property
    def base_entries(self) -> tuple[CraftInvestmentEntry, ...]:
        return tuple(entry for entry in self.entries if entry.kind == CraftInvestmentEntryKind.BASE_ACQUISITION)

    @property
    def crafting_spend_entries(self) -> tuple[CraftInvestmentEntry, ...]:
        return tuple(entry for entry in self.entries if entry.kind == CraftInvestmentEntryKind.CRAFTING_SPEND)


@dataclass(frozen=True)
class CraftInvestmentCostBasis:
    ledger_id: str
    status: CraftInvestmentCostBasisStatus
    total_invested: EconomicValue | None
    known_invested: EconomicValue
    base_acquisition_total: EconomicValue
    crafting_spend_total: EconomicValue
    included_entry_ids: tuple[str, ...]
    incomplete_entry_ids: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class CurrentMarketValuation:
    status: str
    estimated_value: EconomicValue | None = None
    supported_low: EconomicValue | None = None
    supported_high: EconomicValue | None = None
    legacy_statistical_median: EconomicValue | None = None
    confidence_level: str | None = None
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class CurrentProfitPosition:
    status: CurrentProfitPositionStatus
    ledger_id: str
    market_valuation_status: str
    total_invested: EconomicValue | None = None
    known_invested: EconomicValue | None = None
    market_estimated_value: EconomicValue | None = None
    supported_market_low: EconomicValue | None = None
    supported_market_high: EconomicValue | None = None
    unrealized_profit: EconomicValue | None = None
    unrealized_roi: Decimal | None = None
    supported_profit_low: EconomicValue | None = None
    supported_profit_high: EconomicValue | None = None
    confidence_level: str | None = None
    label: str = "unrealized/listing-evidence-based"
    warnings: tuple[str, ...] = ()


class CraftInvestmentCalculator:
    def cost_basis(self, ledger: CraftInvestmentLedger) -> CraftInvestmentCostBasis:
        base_total = Decimal("0")
        craft_total = Decimal("0")
        included: list[str] = []
        incomplete: list[str] = []
        warnings: list[str] = list(ledger.warnings)
        for entry in sorted(ledger.entries, key=lambda item: (item.incurred_at or datetime.min.replace(tzinfo=timezone.utc), item.entry_id)):
            if entry.normalized_value is None:
                incomplete.append(entry.entry_id)
                warnings.append(f"Investment entry {entry.entry_id} has no normalized value and was not treated as zero.")
                continue
            included.append(entry.entry_id)
            if entry.kind == CraftInvestmentEntryKind.BASE_ACQUISITION:
                base_total += entry.normalized_value.amount
            else:
                craft_total += entry.normalized_value.amount
        known = EconomicValue(base_total + craft_total, EXALTED_ECONOMIC_UNIT)
        complete = not incomplete
        return CraftInvestmentCostBasis(
            ledger_id=ledger.ledger_id,
            status=CraftInvestmentCostBasisStatus.COMPLETE if complete else CraftInvestmentCostBasisStatus.INCOMPLETE,
            total_invested=known if complete else None,
            known_invested=known,
            base_acquisition_total=EconomicValue(base_total, EXALTED_ECONOMIC_UNIT),
            crafting_spend_total=EconomicValue(craft_total, EXALTED_ECONOMIC_UNIT),
            included_entry_ids=tuple(included),
            incomplete_entry_ids=tuple(incomplete),
            warnings=tuple(warnings),
        )

    def current_profit_position(
        self,
        cost_basis: CraftInvestmentCostBasis,
        market_valuation: CurrentMarketValuation,
    ) -> CurrentProfitPosition:
        warnings = list((*cost_basis.warnings, *market_valuation.warnings))
        if cost_basis.status != CraftInvestmentCostBasisStatus.COMPLETE or cost_basis.total_invested is None:
            return CurrentProfitPosition(
                status=CurrentProfitPositionStatus.INCOMPLETE_COST_BASIS,
                ledger_id=cost_basis.ledger_id,
                market_valuation_status=market_valuation.status,
                known_invested=cost_basis.known_invested,
                confidence_level=market_valuation.confidence_level,
                warnings=tuple(warnings),
            )

        total = cost_basis.total_invested
        if market_valuation.status == "ESTIMATED_MARKET_VALUE" and market_valuation.estimated_value is not None:
            _require_normalized(market_valuation.estimated_value, "estimated market value")
            profit = EconomicValue(market_valuation.estimated_value.amount - total.amount, EXALTED_ECONOMIC_UNIT)
            roi = None if total.amount == 0 else profit.amount / total.amount
            return CurrentProfitPosition(
                status=CurrentProfitPositionStatus.CURRENT_PROFIT_ESTIMATE_AVAILABLE,
                ledger_id=cost_basis.ledger_id,
                market_valuation_status=market_valuation.status,
                total_invested=total,
                known_invested=cost_basis.known_invested,
                market_estimated_value=market_valuation.estimated_value,
                unrealized_profit=profit,
                unrealized_roi=roi,
                confidence_level=market_valuation.confidence_level,
                warnings=tuple(warnings),
            )

        if market_valuation.status == "SUPPORTED_RANGE_ONLY":
            if market_valuation.supported_low is not None and market_valuation.supported_high is not None:
                _require_normalized(market_valuation.supported_low, "supported market low")
                _require_normalized(market_valuation.supported_high, "supported market high")
                return CurrentProfitPosition(
                    status=CurrentProfitPositionStatus.SUPPORTED_PROFIT_RANGE_ONLY,
                    ledger_id=cost_basis.ledger_id,
                    market_valuation_status=market_valuation.status,
                    total_invested=total,
                    known_invested=cost_basis.known_invested,
                    supported_market_low=market_valuation.supported_low,
                    supported_market_high=market_valuation.supported_high,
                    supported_profit_low=EconomicValue(market_valuation.supported_low.amount - total.amount, EXALTED_ECONOMIC_UNIT),
                    supported_profit_high=EconomicValue(market_valuation.supported_high.amount - total.amount, EXALTED_ECONOMIC_UNIT),
                    confidence_level=market_valuation.confidence_level,
                    warnings=tuple((*warnings, "Supported range is not a point profit estimate.")),
                )
        return CurrentProfitPosition(
            status=CurrentProfitPositionStatus.INSUFFICIENT_MARKET_EVIDENCE,
            ledger_id=cost_basis.ledger_id,
            market_valuation_status=market_valuation.status,
            total_invested=total,
            known_invested=cost_basis.known_invested,
            confidence_level=market_valuation.confidence_level,
            warnings=tuple((*warnings, "Legacy/manual median was not used as a market value.")),
        )


@dataclass(frozen=True)
class CraftInvestmentWorkspacePersistenceStatus:
    storage_version: str
    storage_mode: str
    persistence_enabled: bool
    loaded_entry_count: int
    skipped_entry_count: int = 0
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class CraftInvestmentWorkspaceResult:
    status: CraftInvestmentWorkspaceSaveStatus
    entry_id: str | None = None
    record: dict[str, Any] | None = None
    records: tuple[dict[str, Any], ...] = ()
    warnings: tuple[str, ...] = ()


class CraftInvestmentWorkspaceRepository:
    def __init__(self, records: tuple[dict[str, Any], ...] = ()) -> None:
        self._records: dict[str, dict[str, Any]] = {}
        self._fingerprints: dict[str, str] = {}
        for record in records:
            result = self.save_record(record)
            if result.status == CraftInvestmentWorkspaceSaveStatus.REJECTED:
                raise ValueError("; ".join(result.warnings))

    def save_record(self, record: dict[str, Any]) -> CraftInvestmentWorkspaceResult:
        try:
            copied = _normalized_record(record)
        except Exception as exc:
            return CraftInvestmentWorkspaceResult(CraftInvestmentWorkspaceSaveStatus.REJECTED, warnings=(f"Craft investment entry was rejected: {exc}",))
        entry_id = copied["entry_id"]
        fingerprint = _record_fingerprint(copied)
        existing = self._records.get(entry_id)
        if existing is not None:
            if self._fingerprints[entry_id] == fingerprint:
                return CraftInvestmentWorkspaceResult(CraftInvestmentWorkspaceSaveStatus.ALREADY_EXISTS, entry_id, deepcopy(existing), warnings=("Identical craft investment entry was already stored.",))
            return CraftInvestmentWorkspaceResult(CraftInvestmentWorkspaceSaveStatus.REJECTED, entry_id, warnings=(f"Conflicting craft investment entry {entry_id} was rejected.",))
        self._records[entry_id] = copied
        self._fingerprints[entry_id] = fingerprint
        return CraftInvestmentWorkspaceResult(CraftInvestmentWorkspaceSaveStatus.SAVED, entry_id, deepcopy(copied), warnings=("Stored craft investment entry applies only after current economics is refreshed.",))

    def update_record(self, entry_id: str, record: dict[str, Any]) -> CraftInvestmentWorkspaceResult:
        try:
            copied = _normalized_record({**record, "entry_id": entry_id})
        except Exception as exc:
            return CraftInvestmentWorkspaceResult(CraftInvestmentWorkspaceSaveStatus.REJECTED, entry_id, warnings=(f"Craft investment entry update was rejected: {exc}",))
        existing = self._records.get(entry_id)
        if existing is None:
            return CraftInvestmentWorkspaceResult(CraftInvestmentWorkspaceSaveStatus.NOT_FOUND, entry_id, warnings=(f"Craft investment entry {entry_id} was not found.",))
        for key in ("ledger_id", "subject_id"):
            if existing.get(key) != copied.get(key):
                return CraftInvestmentWorkspaceResult(CraftInvestmentWorkspaceSaveStatus.REJECTED, entry_id, warnings=(f"Craft investment entry {entry_id} is already bound to a different {key}.",))
        copied["created_at"] = existing.get("created_at", copied["created_at"])
        copied["updated_at"] = _now_iso()
        self._records[entry_id] = copied
        self._fingerprints[entry_id] = _record_fingerprint(copied)
        return CraftInvestmentWorkspaceResult(CraftInvestmentWorkspaceSaveStatus.UPDATED, entry_id, deepcopy(copied), warnings=("Updated craft investment entry applies only after current economics is refreshed.",))

    def delete_record(self, entry_id: str) -> CraftInvestmentWorkspaceResult:
        existing = self._records.pop(entry_id, None)
        self._fingerprints.pop(entry_id, None)
        if existing is None:
            return CraftInvestmentWorkspaceResult(CraftInvestmentWorkspaceSaveStatus.NOT_FOUND, entry_id, warnings=(f"Craft investment entry {entry_id} was not found.",))
        return CraftInvestmentWorkspaceResult(CraftInvestmentWorkspaceSaveStatus.DELETED, entry_id, deepcopy(existing))

    def clear_ledger(self, ledger_id: str) -> CraftInvestmentWorkspaceResult:
        deleted = tuple(entry_id for entry_id, record in self._records.items() if record.get("ledger_id") == ledger_id)
        deleted_records = tuple(deepcopy(self._records[entry_id]) for entry_id in deleted)
        for entry_id in deleted:
            self._records.pop(entry_id, None)
            self._fingerprints.pop(entry_id, None)
        return CraftInvestmentWorkspaceResult(CraftInvestmentWorkspaceSaveStatus.CLEARED, records=deleted_records, warnings=(f"Cleared {len(deleted)} craft investment entries.",))

    def list_records(self, ledger_id: str | None = None, subject_id: str | None = None) -> tuple[dict[str, Any], ...]:
        return tuple(
            deepcopy(record)
            for record in sorted(self._records.values(), key=lambda item: (item["ledger_id"], item["incurred_at"], item["entry_id"]))
            if (ledger_id is None or record.get("ledger_id") == ledger_id)
            and (subject_id is None or record.get("subject_id") == subject_id)
        )

    def ledger(self, ledger_id: str, subject_id: str = "current") -> CraftInvestmentLedger:
        entries = tuple(_entry_from_record(record) for record in self.list_records(ledger_id=ledger_id, subject_id=subject_id))
        return CraftInvestmentLedger(ledger_id=ledger_id, subject_id=subject_id, entries=entries)

    def export_backup(self) -> dict[str, Any]:
        return _workspace_envelope(self._records)

    def persistence_status(self) -> CraftInvestmentWorkspacePersistenceStatus:
        return CraftInvestmentWorkspacePersistenceStatus(
            storage_version=CRAFT_INVESTMENT_WORKSPACE_STORAGE_VERSION,
            storage_mode="IN_MEMORY",
            persistence_enabled=False,
            loaded_entry_count=len(self._records),
            warnings=("Craft investment workspace persistence is disabled; entries exist only for this process.",),
        )


class FileBackedCraftInvestmentWorkspaceRepository(CraftInvestmentWorkspaceRepository):
    def __init__(self, storage_path: str | Path) -> None:
        self._storage_path = Path(storage_path)
        self._load_warnings: list[str] = []
        self._skipped_entry_count = 0
        self._loading = True
        records = self._load()
        super().__init__(records)
        self._loading = False

    def save_record(self, record: dict[str, Any]) -> CraftInvestmentWorkspaceResult:
        before = self._snapshot_state()
        result = super().save_record(record)
        if result.status == CraftInvestmentWorkspaceSaveStatus.SAVED and not self._loading:
            persisted = self._persist_or_rollback(before, result.entry_id, "save")
            if persisted is not None:
                return persisted
        return result

    def update_record(self, entry_id: str, record: dict[str, Any]) -> CraftInvestmentWorkspaceResult:
        before = self._snapshot_state()
        result = super().update_record(entry_id, record)
        if result.status == CraftInvestmentWorkspaceSaveStatus.UPDATED and not self._loading:
            persisted = self._persist_or_rollback(before, entry_id, "update")
            if persisted is not None:
                return persisted
        return result

    def delete_record(self, entry_id: str) -> CraftInvestmentWorkspaceResult:
        before = self._snapshot_state()
        result = super().delete_record(entry_id)
        if result.status == CraftInvestmentWorkspaceSaveStatus.DELETED:
            persisted = self._persist_or_rollback(before, entry_id, "delete")
            if persisted is not None:
                return persisted
        return result

    def clear_ledger(self, ledger_id: str) -> CraftInvestmentWorkspaceResult:
        before = self._snapshot_state()
        result = super().clear_ledger(ledger_id)
        persisted = self._persist_or_rollback(before, None, "clear")
        return persisted or result

    def persistence_status(self) -> CraftInvestmentWorkspacePersistenceStatus:
        return CraftInvestmentWorkspacePersistenceStatus(
            storage_version=CRAFT_INVESTMENT_WORKSPACE_STORAGE_VERSION,
            storage_mode="FILE",
            persistence_enabled=True,
            loaded_entry_count=len(self._records),
            skipped_entry_count=self._skipped_entry_count,
            warnings=tuple(self._load_warnings),
        )

    def _load(self) -> tuple[dict[str, Any], ...]:
        if not self._storage_path.exists():
            return ()
        try:
            payload = json.loads(self._storage_path.read_text(encoding="utf-8"))
        except Exception as exc:
            self._load_warnings.append(f"Craft investment workspace could not be loaded: {exc}")
            return ()
        if payload.get("storage_version") != CRAFT_INVESTMENT_WORKSPACE_STORAGE_VERSION:
            self._load_warnings.append("Craft investment workspace storage version is unsupported.")
            return ()
        valid: list[dict[str, Any]] = []
        for record in payload.get("entries", []):
            try:
                valid.append(_normalized_record(record))
            except Exception:
                self._skipped_entry_count += 1
        return tuple(valid)

    def _snapshot_state(self) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
        return deepcopy(self._records), deepcopy(self._fingerprints)

    def _restore_state(self, state: tuple[dict[str, dict[str, Any]], dict[str, str]]) -> None:
        self._records, self._fingerprints = deepcopy(state[0]), deepcopy(state[1])

    def _persist_or_rollback(self, before, entry_id: str | None, operation: str) -> CraftInvestmentWorkspaceResult | None:
        try:
            self._persist()
        except Exception as exc:
            self._restore_state(before)
            return CraftInvestmentWorkspaceResult(
                CraftInvestmentWorkspaceSaveStatus.REJECTED,
                entry_id,
                warnings=(f"Craft investment workspace {operation} could not be persisted: {exc}",),
            )
        return None

    def _persist(self) -> None:
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._storage_path.write_text(json.dumps(self.export_backup(), indent=2, sort_keys=True), encoding="utf-8")


def _normalized_record(record: dict[str, Any]) -> dict[str, Any]:
    copied = deepcopy(record)
    now = _now_iso()
    copied.setdefault("entry_id", _entry_id(copied))
    copied.setdefault("ledger_id", "current")
    copied.setdefault("subject_id", "current")
    copied.setdefault("description", "")
    copied["kind"] = CraftInvestmentEntryKind(copied["kind"]).value
    copied["amount"] = str(Decimal(str(copied["amount"])))
    if Decimal(copied["amount"]) < 0:
        raise ValueError("amount cannot be negative")
    if not copied.get("currency_asset_id"):
        raise ValueError("currency_asset_id is required")
    copied["incurred_at"] = _normalize_datetime(copied.get("incurred_at") or now)
    copied.setdefault("created_at", now)
    copied.setdefault("updated_at", copied["created_at"])
    copied["created_at"] = _normalize_datetime(copied["created_at"])
    copied["updated_at"] = _normalize_datetime(copied["updated_at"])
    if copied.get("normalized_value") is not None:
        copied["normalized_value"] = _economic_value_to_record(_economic_value_from_record(copied["normalized_value"]))
    return copied


def _entry_from_record(record: dict[str, Any]) -> CraftInvestmentEntry:
    return CraftInvestmentEntry(
        entry_id=record["entry_id"],
        ledger_id=record["ledger_id"],
        subject_id=record["subject_id"],
        kind=CraftInvestmentEntryKind(record["kind"]),
        description=record.get("description", ""),
        amount=Decimal(record["amount"]),
        currency_asset_id=record["currency_asset_id"],
        normalized_value=_economic_value_from_record(record["normalized_value"]) if record.get("normalized_value") else None,
        economy_snapshot_id=record.get("economy_snapshot_id"),
        action_id=record.get("action_id"),
        incurred_at=_parse_datetime(record.get("incurred_at")),
        source_reference=record.get("source_reference"),
        notes=record.get("notes"),
        provenance=(
            DataProvenance(
                source_id="craft-investment-workspace",
                source_type=SourceType.OTHER,
                retrieved_at=_parse_datetime(record.get("updated_at")),
                verification_status=VerificationStatus.CURATED,
                notes=record.get("notes"),
            ),
        ),
        warnings=tuple(record.get("warnings", ())),
    )


def _economic_value_from_record(value: dict[str, Any]) -> EconomicValue:
    return EconomicValue(Decimal(str(value["amount"])), value.get("unit", EXALTED_ECONOMIC_UNIT))


def _economic_value_to_record(value: EconomicValue) -> dict[str, str]:
    return {"amount": str(value.amount), "unit": value.unit}


def _workspace_envelope(records: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "storage_version": CRAFT_INVESTMENT_WORKSPACE_STORAGE_VERSION,
        "workspace_version": CRAFT_INVESTMENT_WORKSPACE_VERSION,
        "entries": sorted(deepcopy(tuple(records.values())), key=lambda item: item["entry_id"]),
    }


def _record_fingerprint(record: dict[str, Any]) -> str:
    comparable = {key: value for key, value in record.items() if key not in {"created_at", "updated_at"}}
    return hashlib.sha256(json.dumps(comparable, sort_keys=True).encode("utf-8")).hexdigest()


def _entry_id(record: dict[str, Any]) -> str:
    source = "|".join(
        str(record.get(key, ""))
        for key in ("ledger_id", "subject_id", "kind", "description", "amount", "currency_asset_id", "incurred_at")
    )
    return f"craft-investment:{hashlib.sha256(source.encode('utf-8')).hexdigest()[:24]}"


def _require_normalized(value: EconomicValue, label: str) -> None:
    if value.unit != EXALTED_ECONOMIC_UNIT:
        raise ValueError(f"{label} must use {EXALTED_ECONOMIC_UNIT}")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_datetime(value: str | datetime) -> str:
    parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


def _parse_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed
