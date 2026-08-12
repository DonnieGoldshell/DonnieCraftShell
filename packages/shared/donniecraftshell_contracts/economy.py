"""Framework-independent economy domain contracts and normalization helpers."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum

from .domain import Confidence, DataProvenance, EconomicValue


EXALTED_ASSET_ID = "dc:poe2:economy-asset:currency:exalted-orb"
DIVINE_ASSET_ID = "dc:poe2:economy-asset:currency:divine-orb"
PERFECT_EXALTED_ASSET_ID = "dc:poe2:economy-asset:currency:perfect-exalted-orb"
GREATER_EXALTED_ASSET_ID = "dc:poe2:economy-asset:currency:greater-exalted-orb"
ORB_OF_ANNULMENT_ASSET_ID = "dc:poe2:economy-asset:currency:orb-of-annulment"
OMEN_OF_SINISTRAL_EXALTATION_ASSET_ID = "dc:poe2:economy-asset:ritual:omen-of-sinistral-exaltation"
OMEN_OF_DEXTRAL_EXALTATION_ASSET_ID = "dc:poe2:economy-asset:ritual:omen-of-dextral-exaltation"
OMEN_OF_GREATER_EXALTATION_ASSET_ID = "dc:poe2:economy-asset:ritual:omen-of-greater-exaltation"
OMEN_OF_SINISTRAL_ANNULMENT_ASSET_ID = "dc:poe2:economy-asset:ritual:omen-of-sinistral-annulment"
OMEN_OF_DEXTRAL_ANNULMENT_ASSET_ID = "dc:poe2:economy-asset:ritual:omen-of-dextral-annulment"
OMEN_OF_GREATER_ANNULMENT_ASSET_ID = "dc:poe2:economy-asset:ritual:omen-of-greater-annulment"
OMEN_OF_PUTREFACTION_ASSET_ID = "dc:poe2:economy-asset:ritual:omen-of-putrefaction"
OMEN_OF_CATALYSING_EXALTATION_ASSET_ID = "dc:poe2:economy-asset:ritual:omen-of-catalysing-exaltation"
OMEN_OF_CHAOTIC_MONSTERS_ASSET_ID = "dc:poe2:economy-asset:ritual:omen-of-chaotic-monsters"
OMEN_OF_LIGHT_ASSET_ID = "dc:poe2:economy-asset:ritual:omen-of-light"
PERFECT_ESSENCE_OF_BATTLE_ASSET_ID = "dc:poe2:economy-asset:essence:perfect-essence-of-battle"
PERFECT_ESSENCE_OF_ALACRITY_ASSET_ID = "dc:poe2:economy-asset:essence:perfect-essence-of-alacrity"
GREATER_ESSENCE_OF_ICE_ASSET_ID = "dc:poe2:economy-asset:essence:greater-essence-of-ice"
ESSENCE_OF_ENHANCEMENT_ASSET_ID = "dc:poe2:economy-asset:essence:essence-of-enhancement"
ESSENCE_OF_HYSTERIA_ASSET_ID = "dc:poe2:economy-asset:essence:essence-of-hysteria"
EXALTED_ECONOMIC_UNIT = "EXALTED_ECONOMIC_UNIT"


class FreshnessState(str, Enum):
    FRESH = "FRESH"
    AGING = "AGING"
    STALE = "STALE"
    UNAVAILABLE = "UNAVAILABLE"


class EconomyCategory(str, Enum):
    CURRENCY = "Currency"
    RITUAL = "Ritual"
    ESSENCES = "Essences"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class FreshnessPolicy:
    fresh_after: timedelta = timedelta(hours=2)
    aging_after: timedelta = timedelta(hours=6)


DEFAULT_FRESHNESS_POLICY = FreshnessPolicy()


@dataclass(frozen=True)
class EconomyAsset:
    asset_id: str
    game: str
    display_name: str
    category: EconomyCategory | str
    source_aliases: dict[str, str]
    provenance: tuple[DataProvenance, ...] = ()

    def __post_init__(self) -> None:
        if ":" not in self.asset_id:
            raise ValueError("asset_id must be namespaced")
        if self.asset_id.lower().endswith(self.display_name.lower().replace(" ", "-")) is False:
            # The ID may contain the display slug, but it must be namespaced and
            # semantically scoped. This guard mainly rejects plain display names.
            pass


@dataclass(frozen=True)
class ExchangeRate:
    base_asset_id: str
    quote_asset_id: str
    rate: Decimal
    source: str
    league: str
    snapshot_id: str
    observed_at: datetime | None = None
    retrieved_at: datetime | None = None
    confidence: Confidence | None = None
    provenance: tuple[DataProvenance, ...] = ()

    def __post_init__(self) -> None:
        rate = _decimal(self.rate, "exchange rate")
        if rate <= Decimal("0"):
            raise ValueError("exchange rate must be positive")
        if not self.league:
            raise ValueError("exchange rate league is required")
        object.__setattr__(self, "rate", rate)


@dataclass(frozen=True)
class EconomyQuote:
    asset_id: str
    league: str
    normalized_value: EconomicValue | None
    source_native_value: Decimal | None
    native_reference_asset_id: str | None
    source: str
    snapshot_id: str
    category: EconomyCategory | str = EconomyCategory.UNKNOWN
    observed_at: datetime | None = None
    retrieved_at: datetime | None = None
    volume: Decimal | None = None
    confidence: Confidence | None = None
    freshness: FreshnessState = FreshnessState.UNAVAILABLE
    provenance: tuple[DataProvenance, ...] = ()

    def __post_init__(self) -> None:
        if not self.league:
            raise ValueError("economy quote league is required")
        if self.source_native_value is not None:
            native = _decimal(self.source_native_value, "source native value")
            if native < Decimal("0"):
                raise ValueError("source native value cannot be negative")
            object.__setattr__(self, "source_native_value", native)
        if self.volume is not None:
            volume = _decimal(self.volume, "volume")
            if volume < Decimal("0"):
                raise ValueError("volume cannot be negative")
            object.__setattr__(self, "volume", volume)


@dataclass(frozen=True)
class EconomySnapshot:
    snapshot_id: str
    provider: str
    game: str
    league: str
    retrieved_at: datetime
    freshness: FreshnessState
    quotes: tuple[EconomyQuote, ...]
    exchange_rates: tuple[ExchangeRate, ...]
    observed_at: datetime | None = None
    provenance: tuple[DataProvenance, ...] = ()
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.league:
            raise ValueError("economy snapshot league is required")
        if not self.snapshot_id:
            raise ValueError("economy snapshot_id is required")


def generate_snapshot_id() -> str:
    if not hasattr(uuid, "uuid7"):
        raise RuntimeError("DonnieCraftShell requires Python with stdlib uuid.uuid7 support.")
    return f"economy-snapshot-{uuid.uuid7()}"


def classify_freshness(
    retrieved_at: datetime | None,
    as_of: datetime,
    policy: FreshnessPolicy = DEFAULT_FRESHNESS_POLICY,
) -> FreshnessState:
    if retrieved_at is None:
        return FreshnessState.UNAVAILABLE
    age = _aware(as_of) - _aware(retrieved_at)
    if age < timedelta(0):
        age = timedelta(0)
    if age <= policy.fresh_after:
        return FreshnessState.FRESH
    if age <= policy.aging_after:
        return FreshnessState.AGING
    return FreshnessState.STALE


def normalized_exalted_value(amount: Decimal | int | str) -> EconomicValue:
    value = _decimal(amount, "normalized value")
    if value < Decimal("0"):
        raise ValueError("normalized value cannot be negative")
    return EconomicValue(value, EXALTED_ECONOMIC_UNIT)


def convert_native_to_exalted(primary_value: Decimal, primary_to_exalted_rate: ExchangeRate) -> EconomicValue:
    value = _decimal(primary_value, "primary value")
    if value < Decimal("0"):
        raise ValueError("primary value cannot be negative")
    return normalized_exalted_value(value * primary_to_exalted_rate.rate)


def _decimal(value: Decimal | int | str, field_name: str) -> Decimal:
    if isinstance(value, float):
        raise TypeError(f"{field_name} must not use binary floating point")
    return Decimal(value)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def least_fresh(states: tuple[FreshnessState, ...]) -> FreshnessState:
    if not states:
        return FreshnessState.UNAVAILABLE
    order = {
        FreshnessState.FRESH: 0,
        FreshnessState.AGING: 1,
        FreshnessState.STALE: 2,
        FreshnessState.UNAVAILABLE: 3,
    }
    return max(states, key=lambda state: order[state])
