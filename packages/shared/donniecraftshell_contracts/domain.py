"""Item-class-agnostic DonnieCraftShell domain contracts.

These models intentionally do not encode Path of Exile 2 crafting mechanics.
Unknown values are represented as ``None`` instead of guessed defaults.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Mapping, Sequence


class VerificationStatus(str, Enum):
    VERIFIED = "VERIFIED"
    DERIVED = "DERIVED"
    CURATED = "CURATED"
    PROVISIONAL = "PROVISIONAL"
    NEEDS_VERIFICATION = "NEEDS_VERIFICATION"


class ConfidenceLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    UNKNOWN = "UNKNOWN"


class SourceType(str, Enum):
    OFFICIAL = "OFFICIAL"
    COMMUNITY = "COMMUNITY"
    TRADE_API = "TRADE_API"
    MANUAL_RESEARCH = "MANUAL_RESEARCH"
    DERIVED_ANALYSIS = "DERIVED_ANALYSIS"
    INTERNAL = "INTERNAL"
    OTHER = "OTHER"


class Rarity(str, Enum):
    NORMAL = "NORMAL"
    MAGIC = "MAGIC"
    RARE = "RARE"
    UNIQUE = "UNIQUE"
    UNKNOWN = "UNKNOWN"


class AffixType(str, Enum):
    PREFIX = "PREFIX"
    SUFFIX = "SUFFIX"
    IMPLICIT = "IMPLICIT"
    ENCHANT = "ENCHANT"
    CORRUPTED = "CORRUPTED"
    UNKNOWN = "UNKNOWN"


class RelevanceOrigin(str, Enum):
    VERIFIED_GAME_RELATIONSHIP = "VERIFIED_GAME_RELATIONSHIP"
    DERIVED_STATISTICAL = "DERIVED_STATISTICAL"
    CURATED = "CURATED"


class ComparableStrategy(str, Enum):
    STRICT = "STRICT"
    MODERATE = "MODERATE"
    BUILD_EQUIVALENT = "BUILD_EQUIVALENT"
    OTHER = "OTHER"


class CraftActionCategory(str, Enum):
    SELL_NOW = "SELL_NOW"
    CURRENCY = "CURRENCY"
    OMEN_COMBINATION = "OMEN_COMBINATION"
    ESSENCE = "ESSENCE"
    OTHER = "OTHER"


class RiskProfile(str, Enum):
    CONSERVATIVE = "CONSERVATIVE"
    BALANCED = "BALANCED"
    AGGRESSIVE = "AGGRESSIVE"


class RecommendationStatus(str, Enum):
    RECOMMENDED = "RECOMMENDED"
    NO_RECOMMENDATION = "NO_RECOMMENDATION"


@dataclass(frozen=True)
class Confidence:
    score: Decimal | None = None
    level: ConfidenceLevel | None = None
    reasons: tuple[str, ...] = ()
    sample_size: int | None = None

    def __post_init__(self) -> None:
        if self.score is not None:
            score = _decimal(self.score, "confidence.score")
            if score < Decimal("0") or score > Decimal("1"):
                raise ValueError("confidence.score must be between 0 and 1")
            object.__setattr__(self, "score", score)
        if self.sample_size is not None and self.sample_size < 0:
            raise ValueError("confidence.sample_size cannot be negative")


@dataclass(frozen=True)
class GameContext:
    game: str
    league: str | None = None
    game_version: str | None = None
    locale: str | None = None
    snapshot_at: datetime | None = None


@dataclass(frozen=True)
class DataProvenance:
    source_id: str
    source_type: SourceType
    source_uri: str | None = None
    retrieved_at: datetime | None = None
    game_version: str | None = None
    league: str | None = None
    verification_status: VerificationStatus = VerificationStatus.NEEDS_VERIFICATION
    confidence: Confidence | None = None
    notes: str | None = None


@dataclass(frozen=True)
class EconomicValue:
    amount: Decimal
    unit: str = "EXALTED_ECONOMIC_UNIT"

    def __post_init__(self) -> None:
        object.__setattr__(self, "amount", _decimal(self.amount, "economic amount"))


@dataclass(frozen=True)
class CurrencyAmount:
    asset_id: str
    amount: Decimal
    native_symbol: str | None = None
    economic_value: EconomicValue | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "amount", _decimal(self.amount, "currency amount"))


@dataclass(frozen=True)
class RollValue:
    label: str | None = None
    value: Decimal | None = None
    min_value: Decimal | None = None
    max_value: Decimal | None = None

    def __post_init__(self) -> None:
        for name in ("value", "min_value", "max_value"):
            current = getattr(self, name)
            if current is not None:
                object.__setattr__(self, name, _decimal(current, f"roll {name}"))


@dataclass(frozen=True)
class ItemModifier:
    raw_text: str
    canonical_id: str | None = None
    normalized_text: str | None = None
    affix_type: AffixType = AffixType.UNKNOWN
    family: str | None = None
    group: str | None = None
    tier: str | None = None
    observed_rolls: tuple[RollValue, ...] = ()
    allowed_range: tuple[RollValue, ...] = ()
    tags: tuple[str, ...] = ()
    confidence: Confidence | None = None
    provenance: tuple[DataProvenance, ...] = ()


@dataclass(frozen=True)
class AffixState:
    known_prefixes: tuple[ItemModifier, ...] = ()
    known_suffixes: tuple[ItemModifier, ...] = ()
    prefix_capacity: int | None = None
    suffix_capacity: int | None = None
    open_prefix_count: int | None = None
    open_suffix_count: int | None = None
    uncertainty: Confidence | None = None

    def __post_init__(self) -> None:
        for name in (
            "prefix_capacity",
            "suffix_capacity",
            "open_prefix_count",
            "open_suffix_count",
        ):
            value = getattr(self, name)
            if value is not None and value < 0:
                raise ValueError(f"{name} cannot be negative")


@dataclass(frozen=True)
class ParsedItem:
    analysis_id: str
    raw_clipboard_text: str
    game_context: GameContext
    rarity: Rarity = Rarity.UNKNOWN
    item_class: str | None = None
    base_type: str | None = None
    item_level: int | None = None
    properties: Mapping[str, Any] = field(default_factory=dict)
    modifiers: tuple[ItemModifier, ...] = ()
    affix_state: AffixState | None = None
    parser_confidence: Confidence | None = None
    provenance: tuple[DataProvenance, ...] = ()

    def __post_init__(self) -> None:
        if self.item_level is not None and self.item_level < 0:
            raise ValueError("item_level cannot be negative")


@dataclass(frozen=True)
class ModifierRelevance:
    modifier_id: str | None
    item_class: str | None = None
    character_class: str | None = None
    ascendancy: str | None = None
    build_archetype: str | None = None
    primary_skill: str | None = None
    origin: RelevanceOrigin = RelevanceOrigin.CURATED
    score: Confidence | None = None
    explanation: str | None = None
    provenance: tuple[DataProvenance, ...] = ()


@dataclass(frozen=True)
class EconomyQuote:
    asset_id: str
    league: str | None
    normalized_price: EconomicValue
    native_pair: str | None = None
    native_rate: Decimal | None = None
    observed_at: datetime | None = None
    volume: Decimal | None = None
    confidence: Confidence | None = None
    provenance: tuple[DataProvenance, ...] = ()

    def __post_init__(self) -> None:
        for name in ("native_rate", "volume"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, _decimal(value, name))


@dataclass(frozen=True)
class Valuation:
    estimated_value: EconomicValue | None = None
    plausible_low: EconomicValue | None = None
    plausible_high: EconomicValue | None = None
    confidence: Confidence | None = None
    comparable_count: int | None = None
    comparable_strategy: ComparableStrategy | None = None
    observed_at: datetime | None = None
    provenance: tuple[DataProvenance, ...] = ()

    def __post_init__(self) -> None:
        if self.comparable_count is not None and self.comparable_count < 0:
            raise ValueError("comparable_count cannot be negative")
        values = (self.plausible_low, self.estimated_value, self.plausible_high)
        if all(value is not None for value in values):
            low, estimate, high = values
            assert low is not None and estimate is not None and high is not None
            if not low.amount <= estimate.amount <= high.amount:
                raise ValueError("valuation must satisfy low <= estimate <= high")


@dataclass(frozen=True)
class CraftRequirement:
    description: str
    verification_status: VerificationStatus = VerificationStatus.NEEDS_VERIFICATION
    provenance: tuple[DataProvenance, ...] = ()


@dataclass(frozen=True)
class CraftAction:
    action_id: str
    display_name: str
    category: CraftActionCategory
    requirements: tuple[CraftRequirement, ...] = ()
    cost_components: tuple[CurrencyAmount, ...] = ()
    provenance: tuple[DataProvenance, ...] = ()
    verification_status: VerificationStatus = VerificationStatus.NEEDS_VERIFICATION
    simulation_supported: bool = False

    @classmethod
    def sell_now(cls) -> "CraftAction":
        return cls(
            action_id="core.action.sell_now",
            display_name="SELL NOW",
            category=CraftActionCategory.SELL_NOW,
            verification_status=VerificationStatus.VERIFIED,
            simulation_supported=True,
        )


@dataclass(frozen=True)
class ItemStateDelta:
    description: str
    changed_fields: Mapping[str, Any] = field(default_factory=dict)
    confidence: Confidence | None = None


@dataclass(frozen=True)
class CraftOutcome:
    resulting_item: ParsedItem | None = None
    state_delta: ItemStateDelta | None = None
    probability: Decimal | None = None
    probability_confidence: Confidence | None = None
    resulting_valuation: Valuation | None = None
    profit_loss: EconomicValue | None = None
    provenance: tuple[DataProvenance, ...] = ()

    def __post_init__(self) -> None:
        if self.probability is not None:
            probability = _decimal(self.probability, "outcome probability")
            if probability < Decimal("0") or probability > Decimal("1"):
                raise ValueError("outcome probability must be between 0 and 1")
            object.__setattr__(self, "probability", probability)


@dataclass(frozen=True)
class SimulationResult:
    source_item: ParsedItem
    craft_action: CraftAction
    action_cost: EconomicValue | None = None
    outcomes: tuple[CraftOutcome, ...] = ()
    probability_coverage: Decimal | None = None
    expected_resulting_value: EconomicValue | None = None
    expected_net_value: EconomicValue | None = None
    expected_profit_loss: EconomicValue | None = None
    roi: Decimal | None = None
    probability_of_profit: Decimal | None = None
    downside: EconomicValue | None = None
    upside: EconomicValue | None = None
    confidence: Confidence | None = None
    assumptions: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    complete: bool = False

    def __post_init__(self) -> None:
        for name in ("probability_coverage", "roi", "probability_of_profit"):
            value = getattr(self, name)
            if value is not None:
                decimal_value = _decimal(value, name)
                if name != "roi" and (
                    decimal_value < Decimal("0") or decimal_value > Decimal("1")
                ):
                    raise ValueError(f"{name} must be between 0 and 1")
                object.__setattr__(self, name, decimal_value)


@dataclass(frozen=True)
class BankrollContext:
    risk_profile: RiskProfile
    bankroll: EconomicValue | None = None
    exposure_percentage: Decimal | None = None
    maximum_acceptable_loss: EconomicValue | None = None

    def __post_init__(self) -> None:
        if self.exposure_percentage is not None:
            exposure = _decimal(self.exposure_percentage, "exposure_percentage")
            if exposure < Decimal("0"):
                raise ValueError("exposure_percentage cannot be negative")
            object.__setattr__(self, "exposure_percentage", exposure)


@dataclass(frozen=True)
class RiskAssessment:
    profile: RiskProfile | None = None
    bankroll_context: BankrollContext | None = None
    exposure: Decimal | None = None
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.exposure is not None:
            object.__setattr__(self, "exposure", _decimal(self.exposure, "exposure"))


@dataclass(frozen=True)
class AdvisorRecommendation:
    status: RecommendationStatus
    current_item_valuation: Valuation | None
    candidate_actions: tuple[CraftAction, ...]
    selected_action: CraftAction | None = None
    simulations: tuple[SimulationResult, ...] = ()
    expected_value_comparison: Mapping[str, EconomicValue | None] = field(
        default_factory=dict
    )
    risk_assessment: RiskAssessment | None = None
    bankroll_context: BankrollContext | None = None
    recommendation_confidence: Confidence | None = None
    reasons: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    recommended_at: datetime | None = None

    def __post_init__(self) -> None:
        if (
            self.status == RecommendationStatus.NO_RECOMMENDATION
            and self.selected_action is not None
        ):
            raise ValueError("NO_RECOMMENDATION cannot include a selected_action")


@dataclass(frozen=True)
class CraftSessionStep:
    step_id: str
    action: CraftAction
    resulting_item: ParsedItem | None = None
    cost: EconomicValue | None = None
    created_at: datetime | None = None
    notes: str | None = None


@dataclass(frozen=True)
class CraftSession:
    session_id: str
    game_context: GameContext
    initial_item: ParsedItem
    item_states: tuple[ParsedItem, ...] = ()
    steps: tuple[CraftSessionStep, ...] = ()
    total_invested: EconomicValue | None = None
    current_estimated_value: Valuation | None = None
    unrealized_profit_loss: EconomicValue | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


def _decimal(value: Decimal | int | str, field_name: str) -> Decimal:
    if isinstance(value, float):
        raise TypeError(f"{field_name} must not use binary floating point")
    try:
        return Decimal(value)
    except Exception as exc:  # pragma: no cover - keeps error message focused
        raise TypeError(f"{field_name} must be Decimal-compatible") from exc


def sum_economic_values(values: Sequence[EconomicValue]) -> EconomicValue:
    """Utility for tests and future mapping code; not valuation logic."""

    return EconomicValue(sum((value.amount for value in values), Decimal("0")))
