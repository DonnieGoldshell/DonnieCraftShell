"""Durable local workspace for operator-supplied economy quotes.

The workspace stores explicit local quote evidence for exact economy assets in
exact leagues. It does not scrape, infer missing prices, cross-use quotes across
leagues, or mutate committed normalized economy fixtures.
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

from .domain import DataProvenance, SourceType, VerificationStatus
from .economy import (
    DEFAULT_FRESHNESS_POLICY,
    EXALTED_ASSET_ID,
    EconomyCategory,
    EconomyQuote,
    EconomySnapshot,
    FreshnessPolicy,
    FreshnessState,
    classify_freshness,
    normalized_exalted_value,
)
from .economy_repository import EconomyRepository


ECONOMY_QUOTE_WORKSPACE_VERSION = "dc-economy-quote-workspace-v1"
ECONOMY_QUOTE_WORKSPACE_STORAGE_VERSION = "dc-economy-quote-workspace-storage-v1"
LOCAL_ECONOMY_QUOTE_PROVIDER = "LOCAL_OPERATOR_ECONOMY_QUOTE"


class EconomyQuoteWorkspaceSaveStatus(str, Enum):
    SAVED = "SAVED"
    UPDATED = "UPDATED"
    ALREADY_EXISTS = "ALREADY_EXISTS"
    DELETED = "DELETED"
    CLEARED = "CLEARED"
    NOT_FOUND = "NOT_FOUND"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class EconomyQuoteWorkspacePersistenceStatus:
    storage_version: str
    storage_mode: str
    persistence_enabled: bool
    loaded_quote_count: int
    skipped_quote_count: int = 0
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class EconomyQuoteWorkspaceResult:
    status: EconomyQuoteWorkspaceSaveStatus
    evidence_id: str | None = None
    record: dict[str, Any] | None = None
    records: tuple[dict[str, Any], ...] = ()
    warnings: tuple[str, ...] = ()


class EconomyQuoteWorkspaceRepository:
    def __init__(self, records: tuple[dict[str, Any], ...] = ()) -> None:
        self._records: dict[str, dict[str, Any]] = {}
        self._fingerprints: dict[str, str] = {}
        for record in records:
            result = self.save_record(record)
            if result.status == EconomyQuoteWorkspaceSaveStatus.REJECTED:
                raise ValueError("; ".join(result.warnings))

    def save_record(self, record: dict[str, Any]) -> EconomyQuoteWorkspaceResult:
        try:
            copied = _normalized_record(record)
        except Exception as exc:
            return EconomyQuoteWorkspaceResult(
                status=EconomyQuoteWorkspaceSaveStatus.REJECTED,
                warnings=(f"Economy quote evidence was rejected: {exc}",),
            )
        evidence_id = copied["evidence_id"]
        fingerprint = _record_fingerprint(copied)
        existing = self._records.get(evidence_id)
        if existing is not None:
            if self._fingerprints[evidence_id] == fingerprint:
                return EconomyQuoteWorkspaceResult(
                    status=EconomyQuoteWorkspaceSaveStatus.ALREADY_EXISTS,
                    evidence_id=evidence_id,
                    record=deepcopy(existing),
                    warnings=("Identical economy quote evidence was already stored.",),
                )
            return EconomyQuoteWorkspaceResult(
                status=EconomyQuoteWorkspaceSaveStatus.REJECTED,
                evidence_id=evidence_id,
                warnings=(f"Conflicting economy quote evidence for evidence_id {evidence_id} was rejected.",),
            )
        self._records[evidence_id] = copied
        self._fingerprints[evidence_id] = fingerprint
        return EconomyQuoteWorkspaceResult(
            status=EconomyQuoteWorkspaceSaveStatus.SAVED,
            evidence_id=evidence_id,
            record=deepcopy(copied),
            warnings=("Stored local economy quote evidence applies only after Advisor analysis is re-run.",),
        )

    def update_record(self, evidence_id: str, record: dict[str, Any]) -> EconomyQuoteWorkspaceResult:
        try:
            copied = _normalized_record({**record, "evidence_id": evidence_id})
        except Exception as exc:
            return EconomyQuoteWorkspaceResult(
                status=EconomyQuoteWorkspaceSaveStatus.REJECTED,
                evidence_id=evidence_id,
                warnings=(f"Economy quote evidence update was rejected: {exc}",),
            )
        existing = self._records.get(evidence_id)
        if existing is None:
            return EconomyQuoteWorkspaceResult(
                status=EconomyQuoteWorkspaceSaveStatus.NOT_FOUND,
                evidence_id=evidence_id,
                warnings=(f"Economy quote evidence {evidence_id} was not found.",),
            )
        partition_change = _identity_partition_difference(existing, copied)
        if partition_change:
            return EconomyQuoteWorkspaceResult(
                status=EconomyQuoteWorkspaceSaveStatus.REJECTED,
                evidence_id=evidence_id,
                warnings=(
                    "Economy quote evidence update was rejected because evidence_id "
                    f"{evidence_id} is already bound to a different {partition_change}.",
                ),
            )
        copied["created_at"] = existing.get("created_at", copied["created_at"])
        copied["updated_at"] = _now_iso()
        self._records[evidence_id] = copied
        self._fingerprints[evidence_id] = _record_fingerprint(copied)
        return EconomyQuoteWorkspaceResult(
            status=EconomyQuoteWorkspaceSaveStatus.UPDATED,
            evidence_id=evidence_id,
            record=deepcopy(copied),
            warnings=("Updated local economy quote evidence applies only after Advisor analysis is re-run.",),
        )

    def delete_record(self, evidence_id: str) -> EconomyQuoteWorkspaceResult:
        existing = self._records.pop(evidence_id, None)
        self._fingerprints.pop(evidence_id, None)
        if existing is None:
            return EconomyQuoteWorkspaceResult(
                status=EconomyQuoteWorkspaceSaveStatus.NOT_FOUND,
                evidence_id=evidence_id,
                warnings=(f"Economy quote evidence {evidence_id} was not found.",),
            )
        return EconomyQuoteWorkspaceResult(
            status=EconomyQuoteWorkspaceSaveStatus.DELETED,
            evidence_id=evidence_id,
            record=deepcopy(existing),
            warnings=("Deleted persisted local economy quote evidence only.",),
        )

    def clear_quotes(self, league: str | None = None, asset_id: str | None = None) -> EconomyQuoteWorkspaceResult:
        if asset_id is not None and league is None:
            return EconomyQuoteWorkspaceResult(
                status=EconomyQuoteWorkspaceSaveStatus.REJECTED,
                warnings=("league is required when clearing quotes for a specific asset_id.",),
            )
        deleted = tuple(
            evidence_id
            for evidence_id, record in self._records.items()
            if (league is None or record.get("league") == league)
            and (asset_id is None or record.get("asset_id") == asset_id)
        )
        deleted_records = tuple(deepcopy(self._records[evidence_id]) for evidence_id in deleted)
        for evidence_id in deleted:
            self._records.pop(evidence_id, None)
            self._fingerprints.pop(evidence_id, None)
        return EconomyQuoteWorkspaceResult(
            status=EconomyQuoteWorkspaceSaveStatus.CLEARED,
            records=deleted_records,
            warnings=(f"Cleared {len(deleted)} local economy quote evidence records.",),
        )

    def list_records(self, league: str | None = None, asset_id: str | None = None) -> tuple[dict[str, Any], ...]:
        return tuple(
            deepcopy(record)
            for record in sorted(self._records.values(), key=lambda item: item["evidence_id"])
            if (league is None or record.get("league") == league)
            and (asset_id is None or record.get("asset_id") == asset_id)
        )

    def economy_repository(
        self,
        base_repository: EconomyRepository,
        league: str,
        as_of: datetime,
        freshness_policy: FreshnessPolicy = DEFAULT_FRESHNESS_POLICY,
    ) -> EconomyRepository:
        snapshot = self.snapshot_for_league(league, as_of, freshness_policy)
        snapshots = base_repository.snapshots()
        if snapshot is not None:
            snapshots = (*snapshots, snapshot)
        return EconomyRepository(snapshots)

    def snapshot_for_league(
        self,
        league: str,
        as_of: datetime,
        freshness_policy: FreshnessPolicy = DEFAULT_FRESHNESS_POLICY,
    ) -> EconomySnapshot | None:
        records = [record for record in self.list_records(league) if _parse_iso(record["observed_at"]) <= as_of]
        latest_by_asset: dict[str, dict[str, Any]] = {}
        for record in records:
            asset_id = record["asset_id"]
            current = latest_by_asset.get(asset_id)
            if current is None or _parse_iso(record["observed_at"]) > _parse_iso(current["observed_at"]):
                latest_by_asset[asset_id] = record
        if not latest_by_asset:
            return None
        observed_times = tuple(_parse_iso(record["observed_at"]) for record in latest_by_asset.values())
        newest = max(observed_times)
        snapshot_id = _snapshot_id(league, newest)
        quotes = tuple(
            _quote_from_record(record, snapshot_id, as_of, freshness_policy)
            for record in sorted(latest_by_asset.values(), key=lambda item: item["asset_id"])
        )
        return EconomySnapshot(
            snapshot_id=snapshot_id,
            provider=LOCAL_ECONOMY_QUOTE_PROVIDER,
            game="Path of Exile 2",
            league=league,
            retrieved_at=newest,
            observed_at=newest,
            freshness=_least_quote_freshness(quotes),
            quotes=quotes,
            exchange_rates=(),
            provenance=tuple(provenance for quote in quotes for provenance in quote.provenance),
            warnings=("Local operator-supplied economy quotes are exact league/asset evidence only; no scraping or inference was performed.",),
        )

    def export_backup(self) -> dict[str, Any]:
        return _workspace_envelope(self._records)

    def persistence_status(self) -> EconomyQuoteWorkspacePersistenceStatus:
        return EconomyQuoteWorkspacePersistenceStatus(
            storage_version=ECONOMY_QUOTE_WORKSPACE_STORAGE_VERSION,
            storage_mode="IN_MEMORY",
            persistence_enabled=False,
            loaded_quote_count=len(self._records),
            warnings=("Local economy quote workspace persistence is disabled; evidence exists only for this process.",),
        )


class FileBackedEconomyQuoteWorkspaceRepository(EconomyQuoteWorkspaceRepository):
    def __init__(self, storage_path: str | Path) -> None:
        self._storage_path = Path(storage_path)
        self._load_warnings: list[str] = []
        self._skipped_quote_count = 0
        self._loading = True
        records = self._load()
        super().__init__(records)
        self._loading = False

    def save_record(self, record: dict[str, Any]) -> EconomyQuoteWorkspaceResult:
        before = self._snapshot_state()
        result = super().save_record(record)
        if result.status == EconomyQuoteWorkspaceSaveStatus.SAVED and not self._loading:
            persisted = self._persist_or_rollback(before, result.evidence_id, "save")
            if persisted is not None:
                return persisted
        return result

    def update_record(self, evidence_id: str, record: dict[str, Any]) -> EconomyQuoteWorkspaceResult:
        before = self._snapshot_state()
        result = super().update_record(evidence_id, record)
        if result.status == EconomyQuoteWorkspaceSaveStatus.UPDATED and not self._loading:
            persisted = self._persist_or_rollback(before, evidence_id, "update")
            if persisted is not None:
                return persisted
        return result

    def delete_record(self, evidence_id: str) -> EconomyQuoteWorkspaceResult:
        before = self._snapshot_state()
        result = super().delete_record(evidence_id)
        if result.status == EconomyQuoteWorkspaceSaveStatus.DELETED and not self._loading:
            persisted = self._persist_or_rollback(before, evidence_id, "delete")
            if persisted is not None:
                return persisted
        return result

    def clear_quotes(self, league: str | None = None, asset_id: str | None = None) -> EconomyQuoteWorkspaceResult:
        before = self._snapshot_state()
        result = super().clear_quotes(league, asset_id)
        if result.status == EconomyQuoteWorkspaceSaveStatus.CLEARED and not self._loading:
            persisted = self._persist_or_rollback(before, None, "clear")
            if persisted is not None:
                return persisted
        return result

    def persistence_status(self) -> EconomyQuoteWorkspacePersistenceStatus:
        return EconomyQuoteWorkspacePersistenceStatus(
            storage_version=ECONOMY_QUOTE_WORKSPACE_STORAGE_VERSION,
            storage_mode="FILE",
            persistence_enabled=True,
            loaded_quote_count=len(self._records),
            skipped_quote_count=self._skipped_quote_count,
            warnings=tuple(self._load_warnings),
        )

    def _load(self) -> tuple[dict[str, Any], ...]:
        if not self._storage_path.exists():
            return ()
        try:
            payload = json.loads(self._storage_path.read_text(encoding="utf-8"))
        except Exception as exc:
            self._skip(f"Economy quote workspace storage could not be read and was skipped: {exc}")
            return ()
        if not isinstance(payload, dict):
            self._skip("Economy quote workspace storage root must be an object; persisted quotes were skipped.")
            return ()
        if payload.get("workspace_version") != ECONOMY_QUOTE_WORKSPACE_VERSION:
            self._skip("Economy quote workspace_version is missing or incompatible; persisted quotes were skipped.")
            return ()
        if payload.get("storage_version") != ECONOMY_QUOTE_WORKSPACE_STORAGE_VERSION:
            self._skip("Economy quote workspace storage_version is missing or incompatible; persisted quotes were skipped.")
            return ()
        records = payload.get("records", ())
        if not isinstance(records, list):
            self._skip("Economy quote workspace records must be a list; persisted quotes were skipped.")
            return ()
        loaded: list[dict[str, Any]] = []
        seen: set[str] = set()
        for index, record in enumerate(records, start=1):
            if not isinstance(record, dict):
                self._skip(f"Persisted economy quote #{index} is not an object and was skipped.")
                continue
            try:
                copied = _normalized_record(record)
                evidence_id = copied["evidence_id"]
            except Exception as exc:
                self._skip(f"Persisted economy quote #{index} was skipped: {exc}")
                continue
            if evidence_id in seen:
                self._skip(f"Duplicate persisted economy quote {evidence_id} was skipped.")
                continue
            seen.add(evidence_id)
            loaded.append(copied)
        return tuple(loaded)

    def _persist(self) -> None:
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        encoded = json.dumps(_workspace_envelope(self._records), indent=2, sort_keys=True)
        temporary_path = self._storage_path.with_name(f"{self._storage_path.name}.tmp")
        temporary_path.write_text(encoded, encoding="utf-8")
        temporary_path.replace(self._storage_path)

    def _persist_or_rollback(
        self,
        before: tuple[dict[str, dict[str, Any]], dict[str, str]],
        evidence_id: str | None,
        operation: str,
    ) -> EconomyQuoteWorkspaceResult | None:
        try:
            self._persist()
            return None
        except Exception as exc:
            self._restore_state(before)
            return EconomyQuoteWorkspaceResult(
                status=EconomyQuoteWorkspaceSaveStatus.REJECTED,
                evidence_id=evidence_id,
                warnings=(f"Economy quote workspace persistence failed; {operation} was not saved: {exc}",),
            )

    def _skip(self, warning: str) -> None:
        self._skipped_quote_count += 1
        self._load_warnings.append(warning)

    def _snapshot_state(self) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
        return deepcopy(self._records), dict(self._fingerprints)

    def _restore_state(self, snapshot: tuple[dict[str, dict[str, Any]], dict[str, str]]) -> None:
        self._records, self._fingerprints = snapshot


def _normalized_record(record: dict[str, Any]) -> dict[str, Any]:
    copied = _json_payload_copy(record)
    if not copied.get("league"):
        raise ValueError("league is required")
    if not copied.get("asset_id"):
        raise ValueError("asset_id is required")
    if ":" not in str(copied["asset_id"]):
        raise ValueError("asset_id must be namespaced")
    currency_asset_id = str(copied.get("currency_asset_id") or EXALTED_ASSET_ID)
    if currency_asset_id != EXALTED_ASSET_ID:
        raise ValueError("Task 22A local economy quotes must be recorded in Exalted economic units")
    amount = Decimal(str(copied.get("amount", "")))
    if amount <= Decimal("0"):
        raise ValueError("quote amount must be positive")
    copied["amount"] = str(amount)
    copied["currency_asset_id"] = currency_asset_id
    copied["observed_at"] = _iso_or_none(copied.get("observed_at")) or _now_iso()
    copied["source_type"] = str(copied.get("source_type") or "MANUAL_RESEARCH")
    copied["source_reference"] = _empty_to_none(copied.get("source_reference"))
    copied["notes"] = _empty_to_none(copied.get("notes"))
    now = _now_iso()
    copied.setdefault("created_at", now)
    copied.setdefault("updated_at", copied["created_at"])
    copied["evidence_id"] = str(copied.get("evidence_id") or _derive_evidence_id(copied))
    return copied


def _identity_partition_difference(existing: dict[str, Any], replacement: dict[str, Any]) -> str | None:
    immutable_fields = ("league", "asset_id", "currency_asset_id")
    changed = tuple(field for field in immutable_fields if existing.get(field) != replacement.get(field))
    if not changed:
        return None
    return "/".join(changed)


def _derive_evidence_id(record: dict[str, Any]) -> str:
    digest = hashlib.sha256(
        "|".join(
            (
                str(record.get("league")),
                str(record.get("asset_id")),
                str(record.get("currency_asset_id")),
                str(record.get("observed_at")),
                str(record.get("source_reference") or ""),
            )
        ).encode("utf-8")
    ).hexdigest()[:24]
    return f"economy-quote-evidence:{digest}"


def _record_fingerprint(record: dict[str, Any]) -> str:
    content = {
        key: value
        for key, value in record.items()
        if key not in {"created_at", "updated_at"}
    }
    return hashlib.sha256(json.dumps(content, sort_keys=True).encode("utf-8")).hexdigest()


def _workspace_envelope(records: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "workspace_version": ECONOMY_QUOTE_WORKSPACE_VERSION,
        "storage_version": ECONOMY_QUOTE_WORKSPACE_STORAGE_VERSION,
        "records": [deepcopy(records[evidence_id]) for evidence_id in sorted(records)],
    }


def _quote_from_record(
    record: dict[str, Any],
    snapshot_id: str,
    as_of: datetime,
    freshness_policy: FreshnessPolicy,
) -> EconomyQuote:
    observed_at = _parse_iso(record["observed_at"])
    source_type = SourceType(record.get("source_type") or SourceType.MANUAL_RESEARCH.value)
    return EconomyQuote(
        asset_id=record["asset_id"],
        league=record["league"],
        normalized_value=normalized_exalted_value(record["amount"]),
        source_native_value=Decimal(record["amount"]),
        native_reference_asset_id=record["currency_asset_id"],
        source=LOCAL_ECONOMY_QUOTE_PROVIDER,
        snapshot_id=snapshot_id,
        category=_category_for_asset(record["asset_id"]),
        observed_at=observed_at,
        retrieved_at=observed_at,
        freshness=classify_freshness(observed_at, as_of, freshness_policy),
        provenance=(
            DataProvenance(
                source_id=record["evidence_id"],
                source_type=source_type,
                source_uri=record.get("source_reference") if _looks_like_uri(record.get("source_reference")) else None,
                retrieved_at=observed_at,
                league=record["league"],
                verification_status=VerificationStatus.CURATED,
                notes=record.get("notes") or "Local operator-supplied economy quote evidence.",
            ),
        ),
    )


def _category_for_asset(asset_id: str) -> EconomyCategory:
    if ":currency:" in asset_id:
        return EconomyCategory.CURRENCY
    if ":ritual:" in asset_id:
        return EconomyCategory.RITUAL
    if ":essence:" in asset_id:
        return EconomyCategory.ESSENCES
    return EconomyCategory.UNKNOWN


def _snapshot_id(league: str, observed_at: datetime) -> str:
    digest = hashlib.sha256(f"{league}|{observed_at.isoformat()}|local-economy-quotes".encode("utf-8")).hexdigest()[:24]
    return f"economy-snapshot:local-quotes:{digest}"


def _least_quote_freshness(quotes: tuple[EconomyQuote, ...]) -> FreshnessState:
    order = {
        FreshnessState.FRESH: 0,
        FreshnessState.AGING: 1,
        FreshnessState.STALE: 2,
        FreshnessState.UNAVAILABLE: 3,
    }
    return max((quote.freshness for quote in quotes), key=lambda state: order[state], default=FreshnessState.UNAVAILABLE)


def _parse_iso(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _iso_or_none(value: Any) -> str | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return (value if value.tzinfo else value.replace(tzinfo=timezone.utc)).isoformat()
    if not isinstance(value, str):
        raise ValueError("observed_at must be an ISO datetime string")
    return _parse_iso(value).isoformat()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_payload_copy(payload: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(payload, sort_keys=True, default=str))


def _empty_to_none(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


def _looks_like_uri(value: str | None) -> bool:
    return bool(value and (value.startswith("http://") or value.startswith("https://")))
