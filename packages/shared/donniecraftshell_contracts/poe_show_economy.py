"""poe.show/poe.ninja offline economy adapter and normalizer."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any

from .domain import Confidence, ConfidenceLevel, DataProvenance, SourceType, VerificationStatus
from .economy import (
    DIVINE_ASSET_ID,
    EXALTED_ASSET_ID,
    EXALTED_ECONOMIC_UNIT,
    EconomyCategory,
    FreshnessState,
    EconomyQuote,
    EconomySnapshot,
    ExchangeRate,
    classify_freshness,
    convert_native_to_exalted,
    generate_snapshot_id,
    normalized_exalted_value,
)
from .economy_assets import asset_id_for_poe_show


POE_SHOW_SOURCE_ID = "poe.show"


def load_raw_poe_show_currency_snapshot(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"), parse_float=Decimal, parse_int=Decimal)


def load_raw_poe_show_economy_snapshot(path: Path) -> dict[str, Any]:
    return load_raw_poe_show_currency_snapshot(path)


def normalize_poe_show_currency_snapshot(
    path: Path,
    as_of: datetime | None = None,
) -> EconomySnapshot:
    return normalize_poe_show_economy_snapshot(path, as_of)


def normalize_poe_show_economy_snapshot(
    path: Path,
    as_of: datetime | None = None,
) -> EconomySnapshot:
    raw = load_raw_poe_show_currency_snapshot(path)
    league = raw.get("league")
    if not league:
        raise ValueError("poe.show economy snapshot requires league")
    retrieved_at = _parse_datetime(raw["retrieved_at"])
    current_as_of = as_of or retrieved_at
    freshness = classify_freshness(retrieved_at, current_as_of)
    response = raw["response"]
    core = response["core"]
    category = _category(raw.get("category"))
    primary_source_id = core["primary"]
    primary_asset_id = asset_id_for_poe_show(primary_source_id)
    if primary_asset_id is None:
        raise ValueError(f"unsupported poe.show primary currency: {primary_source_id}")

    snapshot_id = raw.get("snapshot_id") or generate_snapshot_id()
    provenance = (_provenance(raw),)
    warnings: list[str] = []
    primary_to_exalted_rate = _primary_to_exalted_rate(
        primary_asset_id=primary_asset_id,
        source_rates=core.get("rates", {}),
        source=raw["source"],
        league=league,
        snapshot_id=snapshot_id,
        retrieved_at=retrieved_at,
        provenance=provenance,
    )
    exchange_rates = [primary_to_exalted_rate]
    quotes: list[EconomyQuote] = []
    seen_assets: set[str] = set()

    for line in response.get("lines", []):
        source_asset_id = line["id"]
        asset_id = asset_id_for_poe_show(source_asset_id)
        if asset_id is None:
            warnings.append(f"Unmapped poe.show asset skipped: {source_asset_id}")
            continue
        primary_value = _decimal(line.get("primaryValue"), f"{source_asset_id}.primaryValue")
        if primary_value <= Decimal("0"):
            raise ValueError("source price must be positive")
        if asset_id == EXALTED_ASSET_ID:
            normalized_value = normalized_exalted_value(Decimal("1"))
        elif asset_id == primary_asset_id:
            normalized_value = normalized_exalted_value(primary_to_exalted_rate.rate)
        else:
            normalized_value = convert_native_to_exalted(primary_value, primary_to_exalted_rate)
        quote = EconomyQuote(
            asset_id=asset_id,
            league=league,
            normalized_value=normalized_value,
            source_native_value=primary_value,
            native_reference_asset_id=primary_asset_id,
            source=raw["source"],
            snapshot_id=snapshot_id,
            category=category,
            observed_at=None,
            retrieved_at=retrieved_at,
            volume=_decimal_or_none(line.get("volumePrimaryValue")),
            confidence=Confidence(
                level=ConfidenceLevel.MEDIUM,
                reasons=("Community economy source; confidence formula not implemented in Task 6B.",),
            ),
            freshness=freshness,
            provenance=provenance,
        )
        quotes.append(quote)
        seen_assets.add(asset_id)

    if category == EconomyCategory.CURRENCY and EXALTED_ASSET_ID not in seen_assets:
        quotes.append(
            EconomyQuote(
                asset_id=EXALTED_ASSET_ID,
                league=league,
                normalized_value=normalized_exalted_value(Decimal("1")),
                source_native_value=None,
                native_reference_asset_id=EXALTED_ASSET_ID,
                source=raw["source"],
                snapshot_id=snapshot_id,
                category=category,
                retrieved_at=retrieved_at,
                confidence=Confidence(level=ConfidenceLevel.MEDIUM),
                freshness=freshness,
                provenance=provenance,
            )
        )

    return EconomySnapshot(
        snapshot_id=snapshot_id,
        provider=raw["source"],
        game=raw.get("game", "Path of Exile 2"),
        league=league,
        observed_at=None,
        retrieved_at=retrieved_at,
        freshness=freshness,
        quotes=tuple(quotes),
        exchange_rates=tuple(exchange_rates),
        provenance=provenance,
        warnings=tuple(warnings),
    )


def write_normalized_economy_snapshot(snapshot: EconomySnapshot, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_jsonable(snapshot), indent=2), encoding="utf-8")


def load_normalized_economy_snapshot(path: Path) -> EconomySnapshot:
    data = json.loads(path.read_text(encoding="utf-8"), parse_float=Decimal, parse_int=Decimal)
    provenance = tuple(_provenance_from_json(item) for item in data.get("provenance", []))
    quotes = tuple(
        EconomyQuote(
            asset_id=item["asset_id"],
            league=item["league"],
            normalized_value=normalized_exalted_value(item["normalized_value"]["amount"])
            if item.get("normalized_value")
            else None,
            source_native_value=_decimal_or_none(item.get("source_native_value")),
            native_reference_asset_id=item.get("native_reference_asset_id"),
            source=item["source"],
            snapshot_id=item["snapshot_id"],
            category=EconomyCategory[item.get("category", "UNKNOWN")]
            if item.get("category") in EconomyCategory.__members__
            else item.get("category", EconomyCategory.UNKNOWN),
            observed_at=_parse_datetime(item.get("observed_at")),
            retrieved_at=_parse_datetime(item.get("retrieved_at")),
            volume=_decimal_or_none(item.get("volume")),
            confidence=_confidence_from_json(item.get("confidence")),
            freshness=FreshnessState[item.get("freshness", "UNAVAILABLE")],
            provenance=tuple(_provenance_from_json(prov) for prov in item.get("provenance", [])),
        )
        for item in data.get("quotes", [])
    )
    rates = tuple(
        ExchangeRate(
            base_asset_id=item["base_asset_id"],
            quote_asset_id=item["quote_asset_id"],
            rate=_decimal(item["rate"], "exchange rate"),
            source=item["source"],
            league=item["league"],
            snapshot_id=item["snapshot_id"],
            observed_at=_parse_datetime(item.get("observed_at")),
            retrieved_at=_parse_datetime(item.get("retrieved_at")),
            confidence=_confidence_from_json(item.get("confidence")),
            provenance=tuple(_provenance_from_json(prov) for prov in item.get("provenance", [])),
        )
        for item in data.get("exchange_rates", [])
    )
    return EconomySnapshot(
        snapshot_id=data["snapshot_id"],
        provider=data["provider"],
        game=data["game"],
        league=data["league"],
        observed_at=_parse_datetime(data.get("observed_at")),
        retrieved_at=_parse_datetime(data["retrieved_at"]),
        freshness=FreshnessState[data["freshness"]],
        quotes=quotes,
        exchange_rates=rates,
        provenance=provenance,
        warnings=tuple(data.get("warnings", [])),
    )


def _primary_to_exalted_rate(
    primary_asset_id: str,
    source_rates: dict[str, Any],
    source: str,
    league: str,
    snapshot_id: str,
    retrieved_at: datetime,
    provenance: tuple[DataProvenance, ...],
) -> ExchangeRate:
    if primary_asset_id == EXALTED_ASSET_ID:
        rate = Decimal("1")
    elif primary_asset_id == DIVINE_ASSET_ID:
        if "exalted" not in source_rates:
            raise ValueError("missing Exalted cross-rate for Divine primary currency")
        rate = _decimal(source_rates["exalted"], "Divine -> Exalted rate")
    else:
        raise ValueError("normalization requires explicit primary -> Exalted support")
    return ExchangeRate(
        base_asset_id=primary_asset_id,
        quote_asset_id=EXALTED_ASSET_ID,
        rate=rate,
        source=source,
        league=league,
        snapshot_id=snapshot_id,
        retrieved_at=retrieved_at,
        confidence=Confidence(
            level=ConfidenceLevel.MEDIUM,
            reasons=("Explicit poe.show core.rates cross-rate.",),
        ),
        provenance=provenance,
    )


def _provenance(raw: dict[str, Any]) -> DataProvenance:
    return DataProvenance(
        source_id=raw.get("source", POE_SHOW_SOURCE_ID),
        source_type=SourceType.COMMUNITY,
        source_uri=raw.get("source_uri"),
        retrieved_at=_parse_datetime(raw.get("retrieved_at")),
        league=raw.get("league"),
        verification_status=VerificationStatus.PROVISIONAL,
        confidence=Confidence(
            level=ConfidenceLevel.MEDIUM,
            reasons=("Public community economy API; no SLA.",),
        ),
        notes=f"Offline captured poe.show {raw.get('category', 'economy')} response.",
    )


def _category(value: str | None) -> EconomyCategory | str:
    if value == "Currency":
        return EconomyCategory.CURRENCY
    if value == "Ritual":
        return EconomyCategory.RITUAL
    if value == "Essences":
        return EconomyCategory.ESSENCES
    return value or EconomyCategory.UNKNOWN


def _provenance_from_json(data: dict[str, Any]) -> DataProvenance:
    return DataProvenance(
        source_id=data["source_id"],
        source_type=SourceType[data["source_type"]],
        source_uri=data.get("source_uri"),
        retrieved_at=_parse_datetime(data.get("retrieved_at")),
        game_version=data.get("game_version"),
        league=data.get("league"),
        verification_status=VerificationStatus[data.get("verification_status", "NEEDS_VERIFICATION")],
        confidence=_confidence_from_json(data.get("confidence")),
        notes=data.get("notes"),
    )


def _confidence_from_json(data: dict[str, Any] | None) -> Confidence | None:
    if data is None:
        return None
    return Confidence(
        score=_decimal_or_none(data.get("score")),
        level=ConfidenceLevel[data["level"]] if data.get("level") else None,
        reasons=tuple(data.get("reasons", [])),
        sample_size=data.get("sample_size"),
    )


def _parse_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _decimal(value: Any, field_name: str) -> Decimal:
    if isinstance(value, float):
        raise TypeError(f"{field_name} must not use binary floating point")
    decimal = Decimal(str(value))
    if decimal <= Decimal("0") and "rate" in field_name.lower():
        raise ValueError(f"{field_name} must be positive")
    return decimal


def _decimal_or_none(value: Any) -> Decimal | None:
    return Decimal(str(value)) if value is not None else None


def _jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.name
    if hasattr(value, "__dataclass_fields__"):
        return {key: _jsonable(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    return value
