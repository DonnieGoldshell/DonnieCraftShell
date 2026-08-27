"""Framework-independent rare-item valuation evidence contracts.

Task 10B structures comparable evidence and manual trade observations. Task
10C adds conservative listing-derived aggregation. This module does not scrape
trade sites, calculate EV, or recommend.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import ROUND_FLOOR, Decimal
from enum import Enum

from .craft_outcomes import HypotheticalItemState
from .domain import (
    AffixType,
    ComparableStrategy,
    Confidence,
    ConfidenceLevel,
    DataProvenance,
    EconomicValue,
    ItemModifier,
    ParsedItem,
    Rarity,
    RollValue,
    Valuation,
)
from .economy import DIVINE_ASSET_ID, EXALTED_ASSET_ID, FreshnessState, normalized_exalted_value
from .economy_repository import EconomyRepository


VALUATION_CONTRACT_VERSION = "valuation-contract-task10c"


class ModifierComparableRole(str, Enum):
    VALUE_DRIVING = "VALUE_DRIVING"
    SUPPORTING = "SUPPORTING"
    IGNORE_FOR_COMPARABLE = "IGNORE_FOR_COMPARABLE"
    UNKNOWN = "UNKNOWN"


class ModifierMatchMode(str, Enum):
    EXACT = "EXACT"
    RELAXED = "RELAXED"
    UNKNOWN = "UNKNOWN"


class ValuationReadiness(str, Enum):
    READY = "READY"
    PARTIAL = "PARTIAL"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class ListingStatus(str, Enum):
    LISTED = "LISTED"
    OBSERVED = "OBSERVED"
    SOLD = "SOLD"
    UNKNOWN = "UNKNOWN"


class LiquidityStatus(str, Enum):
    UNKNOWN = "UNKNOWN"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ValuationEstimateType(str, Enum):
    LISTING_DERIVED = "LISTING_DERIVED"
    NONE = "NONE"


class ComparableExclusionReason(str, Enum):
    DUPLICATE_LISTING = "DUPLICATE_LISTING"
    UNNORMALIZED_PRICE = "UNNORMALIZED_PRICE"
    OUTLIER_POLICY = "OUTLIER_POLICY"
    STALE_POLICY = "STALE_POLICY"


class ComparableRelevanceBand(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    NOT_COMPARABLE = "NOT_COMPARABLE"
    INSUFFICIENT_STATE = "INSUFFICIENT_STATE"


class ModifierRelevanceRelationship(str, Enum):
    EXACT_MATCH = "EXACT_MATCH"
    TIER_DIFFERENCE = "TIER_DIFFERENCE"
    ORIGIN_DIFFERENCE = "ORIGIN_DIFFERENCE"
    TIER_AND_ORIGIN_DIFFERENCE = "TIER_AND_ORIGIN_DIFFERENCE"
    MISSING_FROM_COMPARABLE = "MISSING_FROM_COMPARABLE"
    EXTRA_ON_COMPARABLE = "EXTRA_ON_COMPARABLE"


class ModifierQualityRelationship(str, Enum):
    CURRENT_BETTER = "CURRENT_BETTER"
    COMPARABLE_BETTER = "COMPARABLE_BETTER"
    ROUGHLY_EQUIVALENT = "ROUGHLY_EQUIVALENT"
    UNKNOWN = "UNKNOWN"
    MISSING_FROM_COMPARABLE = "MISSING_FROM_COMPARABLE"
    EXTRA_ON_COMPARABLE = "EXTRA_ON_COMPARABLE"


class ModifierQualityEvidence(str, Enum):
    TIER = "TIER"
    ROLL_WITHIN_TIER = "ROLL_WITHIN_TIER"
    TIER_AND_ROLL = "TIER_AND_ROLL"
    IDENTITY_ONLY = "IDENTITY_ONLY"
    INSUFFICIENT = "INSUFFICIENT"


class ComparableAnchorRole(str, Enum):
    LOWER_ANCHOR = "LOWER_ANCHOR"
    UPPER_ANCHOR = "UPPER_ANCHOR"
    EQUIVALENT_ANCHOR = "EQUIVALENT_ANCHOR"
    UNINTERPRETED = "UNINTERPRETED"


class ComparableValuationStatus(str, Enum):
    READY = "READY"
    PARTIAL = "PARTIAL"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


@dataclass(frozen=True)
class ValuationSubject:
    subject_id: str
    item_class: str | None
    base_type: str | None
    item_level: int | None
    rarity: Rarity
    modifiers: tuple[ItemModifier, ...]
    source_item_analysis_id: str | None = None
    hypothetical_state_id: str | None = None
    dataset_versions: tuple[str, ...] = ()
    provenance: tuple[DataProvenance, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class ModifierComparableRoleAssignment:
    modifier: ItemModifier
    role: ModifierComparableRole
    confidence: Confidence | None = None
    reason: str | None = None
    provenance: tuple[DataProvenance, ...] = ()


@dataclass(frozen=True)
class ModifierConstraint:
    modifier_identity: str
    role: ModifierComparableRole
    affix_type: AffixType = AffixType.UNKNOWN
    canonical_modifier_id: str | None = None
    modifier_family_id: str | None = None
    display_name: str | None = None
    min_tier: str | None = None
    max_tier: str | None = None
    min_roll: RollValue | None = None
    max_roll: RollValue | None = None
    match_mode: ModifierMatchMode = ModifierMatchMode.UNKNOWN
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class ComparableQuery:
    query_id: str
    valuation_subject_id: str
    strategy: ComparableStrategy
    item_class: str | None
    base_type: str | None = None
    rarity: Rarity | None = None
    min_item_level: int | None = None
    max_item_level: int | None = None
    included_modifier_constraints: tuple[ModifierConstraint, ...] = ()
    ignored_modifiers: tuple[str, ...] = ()
    relaxation_rules: tuple[str, ...] = ()
    league: str | None = None
    generated_at: datetime | None = None
    provenance: tuple[DataProvenance, ...] = ()
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.query_id:
            raise ValueError("comparable query_id is required")
        if self.min_item_level is not None and self.min_item_level < 0:
            raise ValueError("min_item_level cannot be negative")
        if self.max_item_level is not None and self.max_item_level < 0:
            raise ValueError("max_item_level cannot be negative")


@dataclass(frozen=True)
class TradeProviderCapabilities:
    supports_automatic_search: bool
    supports_manual_observations: bool
    supports_trade_url_generation: bool = False
    supports_completed_sales: bool = False


@dataclass(frozen=True)
class ManualTradeWorkflow:
    query: ComparableQuery
    provider: str
    instructions: tuple[str, ...]
    structured_summary: str
    capabilities: TradeProviderCapabilities
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class StructuredComparableItem:
    raw_clipboard_text: str
    parsed_item: ParsedItem
    detected_format: str
    warnings: tuple[str, ...] = ()
    unparsed_sections: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.raw_clipboard_text.strip():
            raise ValueError("structured comparable raw_clipboard_text is required")


@dataclass(frozen=True)
class ComparableModifierRelevance:
    relationship: ModifierRelevanceRelationship
    semantic_identity: str
    affix_type: AffixType
    current_display_name: str | None = None
    comparable_display_name: str | None = None
    current_tier: str | None = None
    comparable_tier: str | None = None
    current_origin: str | None = None
    comparable_origin: str | None = None
    current_tags: tuple[str, ...] = ()
    comparable_tags: tuple[str, ...] = ()
    current_roll_values: tuple[str, ...] = ()
    comparable_roll_values: tuple[str, ...] = ()
    tag_match: bool | None = None
    roll_observation_match: bool | None = None
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class ComparableRelevance:
    score: Decimal | None
    band: ComparableRelevanceBand
    base_similarity: tuple[str, ...] = ()
    matched_modifiers: tuple[ComparableModifierRelevance, ...] = ()
    differing_modifiers: tuple[ComparableModifierRelevance, ...] = ()
    missing_modifiers: tuple[ComparableModifierRelevance, ...] = ()
    extra_modifiers: tuple[ComparableModifierRelevance, ...] = ()
    warnings: tuple[str, ...] = ()
    policy_id: str = "comparable-relevance-policy-v1"

    def __post_init__(self) -> None:
        if self.score is not None:
            score = _decimal(self.score, "comparable relevance score")
            if score < Decimal("0") or score > Decimal("1"):
                raise ValueError("comparable relevance score must be between 0 and 1")
            object.__setattr__(self, "score", score)


@dataclass(frozen=True)
class ModifierQualityDelta:
    relationship: ModifierQualityRelationship
    evidence: ModifierQualityEvidence
    semantic_identity: str
    affix_type: AffixType
    current_display_name: str | None = None
    comparable_display_name: str | None = None
    current_tier: str | None = None
    comparable_tier: str | None = None
    current_origin: str | None = None
    comparable_origin: str | None = None
    current_roll_quality: Decimal | None = None
    comparable_roll_quality: Decimal | None = None
    current_roll_values: tuple[str, ...] = ()
    comparable_roll_values: tuple[str, ...] = ()
    origin_difference: bool = False
    reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field_name in ("current_roll_quality", "comparable_roll_quality"):
            value = getattr(self, field_name)
            if value is not None:
                decimal_value = _decimal(value, field_name)
                if decimal_value < Decimal("0") or decimal_value > Decimal("1"):
                    raise ValueError(f"{field_name} must be between 0 and 1")
                object.__setattr__(self, field_name, decimal_value)


@dataclass(frozen=True)
class ComparableQualityDelta:
    modifier_deltas: tuple[ModifierQualityDelta, ...] = ()
    current_better_count: int = 0
    comparable_better_count: int = 0
    roughly_equivalent_count: int = 0
    unknown_count: int = 0
    missing_from_comparable_count: int = 0
    extra_on_comparable_count: int = 0
    warnings: tuple[str, ...] = ()
    policy_id: str = "comparable-modifier-quality-delta-policy-v1"


@dataclass(frozen=True)
class ComparableValuationPolicy:
    policy_id: str = "comparable-valuation-model-v1"
    minimum_structured_anchors_for_estimate: int = 2
    high_relevance_threshold: Decimal = Decimal("0.75")
    wide_anchor_spread_threshold: Decimal = Decimal("5")

    def __post_init__(self) -> None:
        if self.minimum_structured_anchors_for_estimate < 2:
            raise ValueError("minimum_structured_anchors_for_estimate must be at least 2")
        for field_name in ("high_relevance_threshold", "wide_anchor_spread_threshold"):
            value = _decimal(getattr(self, field_name), field_name)
            if value < Decimal("0"):
                raise ValueError(f"{field_name} cannot be negative")
            object.__setattr__(self, field_name, value)


@dataclass(frozen=True)
class ComparableValuationAnchor:
    comparable_id: str
    external_listing_id: str | None
    item_name: str | None
    base_type: str | None
    role: ComparableAnchorRole
    listing_price: Decimal
    listing_currency_asset_id: str
    normalized_value: EconomicValue | None
    structural_relevance_band: ComparableRelevanceBand | None = None
    structural_relevance_score: Decimal | None = None
    current_better_count: int = 0
    comparable_better_count: int = 0
    roughly_equivalent_count: int = 0
    unknown_count: int = 0
    reasons: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "listing_price", _decimal(self.listing_price, "anchor listing price"))
        if self.structural_relevance_score is not None:
            score = _decimal(self.structural_relevance_score, "anchor structural relevance score")
            if score < Decimal("0") or score > Decimal("1"):
                raise ValueError("anchor structural relevance score must be between 0 and 1")
            object.__setattr__(self, "structural_relevance_score", score)


@dataclass(frozen=True)
class ComparableValuationEstimate:
    status: ComparableValuationStatus
    central_estimate: EconomicValue | None = None
    plausible_low: EconomicValue | None = None
    plausible_high: EconomicValue | None = None
    confidence: Confidence | None = None
    anchor_results: tuple[ComparableValuationAnchor, ...] = ()
    included_observation_ids: tuple[str, ...] = ()
    excluded_observation_ids: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    policy_id: str = "comparable-valuation-model-v1"

    def __post_init__(self) -> None:
        if self.plausible_low and self.central_estimate and self.plausible_low.amount > self.central_estimate.amount:
            raise ValueError("comparable valuation low bound must be <= central estimate")
        if self.plausible_high and self.central_estimate and self.central_estimate.amount > self.plausible_high.amount:
            raise ValueError("comparable valuation central estimate must be <= high bound")


@dataclass(frozen=True)
class ManualListingObservation:
    observation_id: str
    query_id: str
    amount: Decimal
    currency_asset_id: str
    league: str
    observed_at: datetime
    external_listing_id: str | None = None
    item_summary: str | None = None
    comparable_item: StructuredComparableItem | None = None
    provenance: tuple[DataProvenance, ...] = ()
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        amount = _decimal(self.amount, "listing amount")
        if amount < Decimal("0"):
            raise ValueError("listing amount cannot be negative")
        object.__setattr__(self, "amount", amount)


@dataclass(frozen=True)
class ComparableResult:
    comparable_id: str
    query_id: str
    provider: str
    external_listing_id: str | None
    listing_price: Decimal
    listing_currency_asset_id: str
    normalized_value: EconomicValue | None
    item_summary: str | None
    matched_constraints: tuple[str, ...]
    observed_at: datetime
    retrieved_at: datetime
    league: str
    listing_status: ListingStatus = ListingStatus.OBSERVED
    economy_snapshot_id: str | None = None
    economy_freshness: FreshnessState = FreshnessState.UNAVAILABLE
    provenance: tuple[DataProvenance, ...] = ()
    warnings: tuple[str, ...] = ()
    comparable_item: StructuredComparableItem | None = None
    comparable_relevance: ComparableRelevance | None = None
    comparable_quality_delta: ComparableQualityDelta | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "listing_price", _decimal(self.listing_price, "listing price"))
        if self.listing_status == ListingStatus.SOLD:
            raise ValueError("ComparableResult represents listings/observations, not realized sale records")


@dataclass(frozen=True)
class ValuationEvidencePolicy:
    minimum_usable_comparables: int = 3

    def __post_init__(self) -> None:
        if self.minimum_usable_comparables < 1:
            raise ValueError("minimum_usable_comparables must be positive")


@dataclass(frozen=True)
class ValuationAggregationPolicy:
    policy_id: str = "valuation-aggregation-policy-task10c-default"
    minimum_ready_comparables: int = 3
    minimum_partial_comparables: int = 2
    lower_quantile: Decimal = Decimal("0.25")
    upper_quantile: Decimal = Decimal("0.75")
    trim_fraction: Decimal = Decimal("0")
    exclude_duplicate_listing_ids: bool = True
    exclude_outliers: bool = True
    outlier_median_multiplier: Decimal = Decimal("3")
    stale_evidence_is_allowed: bool = True
    stale_evidence_reduces_confidence: bool = True
    strict_preferred: bool = True
    price_spread_warning_threshold: Decimal = Decimal("1.00")

    def __post_init__(self) -> None:
        if self.minimum_ready_comparables < 1:
            raise ValueError("minimum_ready_comparables must be positive")
        if self.minimum_partial_comparables < 1:
            raise ValueError("minimum_partial_comparables must be positive")
        for name in ("lower_quantile", "upper_quantile", "trim_fraction", "outlier_median_multiplier", "price_spread_warning_threshold"):
            value = _decimal(getattr(self, name), name)
            if value < Decimal("0"):
                raise ValueError(f"{name} cannot be negative")
            object.__setattr__(self, name, value)
        if self.lower_quantile > self.upper_quantile:
            raise ValueError("lower_quantile must be <= upper_quantile")
        if self.upper_quantile > Decimal("1"):
            raise ValueError("upper_quantile must be <= 1")
        if self.trim_fraction >= Decimal("0.5"):
            raise ValueError("trim_fraction must be < 0.5")


@dataclass(frozen=True)
class ExcludedComparable:
    comparable_id: str
    reason: ComparableExclusionReason
    policy_id: str
    original_result: ComparableResult
    notes: str | None = None


@dataclass(frozen=True)
class StrategyComposition:
    strategy: ComparableStrategy
    total_results: int
    usable_results: int
    used_results: int
    excluded_results: int


@dataclass(frozen=True)
class PriceSpread:
    minimum: EconomicValue | None
    maximum: EconomicValue | None
    median: EconomicValue | None
    lower_quantile: EconomicValue | None
    upper_quantile: EconomicValue | None
    relative_spread: Decimal | None = None


@dataclass(frozen=True)
class ComparableEvidenceSet:
    evidence_set_id: str
    query: ComparableQuery
    provider: str
    results: tuple[ComparableResult, ...]
    policy: ValuationEvidencePolicy = ValuationEvidencePolicy()
    economy_snapshot_ids: tuple[str, ...] = ()
    contract_version: str = VALUATION_CONTRACT_VERSION
    warnings: tuple[str, ...] = ()

    @property
    def usable_results(self) -> tuple[ComparableResult, ...]:
        return tuple(result for result in self.results if result.normalized_value is not None)

    @property
    def unusable_result_count(self) -> int:
        return len(self.results) - len(self.usable_results)

    @property
    def readiness(self) -> ValuationReadiness:
        usable = len(self.usable_results)
        if usable == 0:
            return ValuationReadiness.INSUFFICIENT_DATA
        if usable < self.policy.minimum_usable_comparables:
            return ValuationReadiness.PARTIAL
        return ValuationReadiness.READY

    @property
    def duplicate_listing_ids(self) -> tuple[str, ...]:
        seen: set[str] = set()
        duplicates: set[str] = set()
        for result in self.results:
            if not result.external_listing_id:
                continue
            if result.external_listing_id in seen:
                duplicates.add(result.external_listing_id)
            seen.add(result.external_listing_id)
        return tuple(sorted(duplicates))


@dataclass(frozen=True)
class ValuationResult:
    readiness: ValuationReadiness
    estimate_type: ValuationEstimateType = ValuationEstimateType.NONE
    estimated_value: EconomicValue | None = None
    plausible_low: EconomicValue | None = None
    plausible_high: EconomicValue | None = None
    confidence: Confidence | None = None
    strategy: ComparableStrategy | None = None
    comparable_count: int = 0
    source_evidence_ids: tuple[str, ...] = ()
    used_comparable_ids: tuple[str, ...] = ()
    excluded_comparables: tuple[ExcludedComparable, ...] = ()
    strategy_composition: tuple[StrategyComposition, ...] = ()
    price_spread: PriceSpread | None = None
    aggregation_policy_id: str | None = None
    methodology: str | None = None
    economy_snapshot_ids: tuple[str, ...] = ()
    league: str | None = None
    liquidity: LiquidityStatus = LiquidityStatus.UNKNOWN
    observed_at: datetime | None = None
    provenance: tuple[DataProvenance, ...] = ()
    warnings: tuple[str, ...] = ()

    def to_domain_valuation(self) -> Valuation:
        return Valuation(
            estimated_value=self.estimated_value,
            plausible_low=self.plausible_low,
            plausible_high=self.plausible_high,
            confidence=self.confidence,
            comparable_count=self.comparable_count,
            comparable_strategy=self.strategy,
            observed_at=self.observed_at,
            provenance=self.provenance,
        )


class ValuationAggregator:
    def __init__(self, policy: ValuationAggregationPolicy | None = None):
        self.policy = policy or ValuationAggregationPolicy()

    def aggregate(self, evidence_set: ComparableEvidenceSet) -> ValuationResult:
        return self.aggregate_evidence_sets((evidence_set,))

    def aggregate_evidence_sets(self, evidence_sets: tuple[ComparableEvidenceSet, ...]) -> ValuationResult:
        selected_sets, strategy_warning = _select_evidence_sets(evidence_sets, self.policy)
        if not selected_sets:
            return ValuationResult(
                readiness=ValuationReadiness.INSUFFICIENT_DATA,
                aggregation_policy_id=self.policy.policy_id,
                methodology=_methodology_summary(self.policy),
                warnings=("No comparable evidence sets supplied.",),
            )
        used, excluded = _select_usable_results(selected_sets, self.policy)
        warnings = [warning for evidence_set in selected_sets for warning in evidence_set.warnings]
        if strategy_warning:
            warnings.append(strategy_warning)
        if any(result.economy_freshness == FreshnessState.STALE for result in used):
            warnings.append("One or more used comparable observations rely on stale economy conversion evidence.")
        values = tuple(result.normalized_value.amount for result in used if result.normalized_value is not None)
        readiness = _aggregation_readiness(len(values), self.policy)
        composition = tuple(_composition(evidence_set, used, excluded) for evidence_set in selected_sets)
        result_strategy = selected_sets[0].query.strategy
        if any(evidence_set.query.strategy != result_strategy for evidence_set in selected_sets):
            result_strategy = ComparableStrategy.OTHER
        common = {
            "readiness": readiness,
            "strategy": result_strategy,
            "comparable_count": len(values),
            "source_evidence_ids": tuple(evidence_set.evidence_set_id for evidence_set in selected_sets),
            "used_comparable_ids": tuple(result.comparable_id for result in used),
            "excluded_comparables": tuple(excluded),
            "strategy_composition": composition,
            "aggregation_policy_id": self.policy.policy_id,
            "methodology": _methodology_summary(self.policy),
            "economy_snapshot_ids": tuple(sorted({snapshot for evidence_set in selected_sets for snapshot in evidence_set.economy_snapshot_ids})),
            "league": selected_sets[0].query.league,
            "observed_at": max((result.observed_at for result in used), default=None),
            "warnings": tuple(warnings),
        }
        if readiness == ValuationReadiness.INSUFFICIENT_DATA:
            return ValuationResult(
                **common,
                estimate_type=ValuationEstimateType.NONE,
                confidence=Confidence(level=ConfidenceLevel.LOW, reasons=("No defensible listing-derived estimate; insufficient usable evidence.",)),
                liquidity=LiquidityStatus.UNKNOWN,
            )

        sorted_values = tuple(sorted(values))
        trimmed_values = _trim_values(sorted_values, self.policy.trim_fraction)
        median = decimal_median(trimmed_values)
        low = decimal_quantile(trimmed_values, self.policy.lower_quantile)
        high = decimal_quantile(trimmed_values, self.policy.upper_quantile)
        spread = _price_spread(trimmed_values, self.policy)
        if spread.relative_spread is not None and spread.relative_spread > self.policy.price_spread_warning_threshold:
            warnings.append("Comparable listing spread exceeds configured warning threshold.")
        if excluded:
            warnings.append("One or more comparable observations were excluded by deterministic policy.")
        return ValuationResult(
            **{**common, "warnings": tuple(warnings)},
            estimate_type=ValuationEstimateType.LISTING_DERIVED,
            estimated_value=normalized_exalted_value(median),
            plausible_low=normalized_exalted_value(low),
            plausible_high=normalized_exalted_value(high),
            confidence=_confidence(readiness, len(values), spread, used, excluded),
            liquidity=_liquidity(len(values), spread),
            price_spread=spread,
        )


class ComparableValuationModel:
    """Conservative listing-derived valuation from structured comparable anchors."""

    def __init__(self, policy: ComparableValuationPolicy | None = None):
        self.policy = policy or ComparableValuationPolicy()

    def estimate(self, evidence_set: ComparableEvidenceSet) -> ComparableValuationEstimate:
        anchors = tuple(_anchor_from_result(result, self.policy) for result in evidence_set.results)
        included = tuple(
            anchor
            for anchor in anchors
            if anchor.normalized_value is not None and anchor.role != ComparableAnchorRole.UNINTERPRETED
        )
        excluded_ids = tuple(anchor.comparable_id for anchor in anchors if anchor not in included)
        warnings = [
            "Comparable valuation model uses listing-derived anchor brackets, not realized sale prices.",
        ]
        warnings.extend(warning for anchor in anchors for warning in anchor.warnings)
        if len(included) < self.policy.minimum_structured_anchors_for_estimate:
            return ComparableValuationEstimate(
                status=ComparableValuationStatus.INSUFFICIENT_DATA,
                confidence=Confidence(
                    level=ConfidenceLevel.LOW,
                    reasons=("Insufficient structured comparable anchors for a defensible current-item estimate.",),
                    sample_size=len(included),
                ),
                anchor_results=anchors,
                included_observation_ids=tuple(anchor.comparable_id for anchor in included),
                excluded_observation_ids=excluded_ids,
                warnings=tuple(warnings),
                policy_id=self.policy.policy_id,
            )

        lower_values = [anchor.normalized_value.amount for anchor in included if anchor.role in {ComparableAnchorRole.LOWER_ANCHOR, ComparableAnchorRole.EQUIVALENT_ANCHOR}]
        upper_values = [anchor.normalized_value.amount for anchor in included if anchor.role in {ComparableAnchorRole.UPPER_ANCHOR, ComparableAnchorRole.EQUIVALENT_ANCHOR}]
        if not lower_values or not upper_values:
            warnings.append("Structured anchors do not provide both lower and upper/equivalent bracket evidence.")
            return ComparableValuationEstimate(
                status=ComparableValuationStatus.INSUFFICIENT_DATA,
                confidence=Confidence(
                    level=ConfidenceLevel.LOW,
                    reasons=("Comparable valuation needs lower and upper/equivalent anchor evidence.",),
                    sample_size=len(included),
                ),
                anchor_results=anchors,
                included_observation_ids=tuple(anchor.comparable_id for anchor in included),
                excluded_observation_ids=excluded_ids,
                warnings=tuple(warnings),
                policy_id=self.policy.policy_id,
            )

        low = min(lower_values)
        high = max(upper_values)
        if low > high:
            warnings.append("Comparable anchor directions conflict with observed listing brackets.")
            return ComparableValuationEstimate(
                status=ComparableValuationStatus.INSUFFICIENT_DATA,
                confidence=Confidence(
                    level=ConfidenceLevel.LOW,
                    reasons=("Anchor bracket is internally inconsistent.",),
                    sample_size=len(included),
                ),
                anchor_results=anchors,
                included_observation_ids=tuple(anchor.comparable_id for anchor in included),
                excluded_observation_ids=excluded_ids,
                warnings=tuple(warnings),
                policy_id=self.policy.policy_id,
            )

        central = (low + high) / Decimal("2")
        spread_ratio = (high / low) if low > Decimal("0") else None
        if spread_ratio is not None and spread_ratio >= self.policy.wide_anchor_spread_threshold:
            warnings.append("Comparable anchor spread exceeds configured warning threshold.")
        status = ComparableValuationStatus.READY
        confidence_level = ConfidenceLevel.MEDIUM
        reasons = [
            f"{len(included)} structured comparable valuation anchor(s) included.",
            "Central estimate is the midpoint of the conservative lower/upper anchor bracket.",
        ]
        if len(included) < 3 or (spread_ratio is not None and spread_ratio >= self.policy.wide_anchor_spread_threshold):
            status = ComparableValuationStatus.PARTIAL
            confidence_level = ConfidenceLevel.LOW
            reasons.append("Small anchor count or wide spread limits confidence.")
        return ComparableValuationEstimate(
            status=status,
            central_estimate=normalized_exalted_value(central),
            plausible_low=normalized_exalted_value(low),
            plausible_high=normalized_exalted_value(high),
            confidence=Confidence(level=confidence_level, reasons=tuple(reasons), sample_size=len(included)),
            anchor_results=anchors,
            included_observation_ids=tuple(anchor.comparable_id for anchor in included),
            excluded_observation_ids=excluded_ids,
            warnings=tuple(warnings),
            policy_id=self.policy.policy_id,
        )


def _anchor_from_result(
    result: ComparableResult,
    policy: ComparableValuationPolicy,
) -> ComparableValuationAnchor:
    reasons: list[str] = []
    warnings = list(result.warnings)
    relevance = result.comparable_relevance
    quality_delta = result.comparable_quality_delta
    role = ComparableAnchorRole.UNINTERPRETED

    if result.normalized_value is None:
        warnings.append("Comparable listing has no normalized Exalted value; it cannot anchor valuation.")
    if relevance is None or relevance.score is None:
        warnings.append("Comparable listing has no structured relevance assessment; price-only evidence is not adjusted.")
    elif relevance.score < policy.high_relevance_threshold:
        warnings.append("Comparable structural relevance is below the configured high-relevance anchor threshold.")
    else:
        reasons.append(
            f"Structured relevance {relevance.band.value} ({relevance.score}) meets anchor threshold {policy.high_relevance_threshold}."
        )
    if quality_delta is None:
        warnings.append("Comparable listing has no modifier quality delta; anchor direction cannot be inferred.")

    if (
        result.normalized_value is not None
        and relevance is not None
        and relevance.score is not None
        and relevance.score >= policy.high_relevance_threshold
        and quality_delta is not None
    ):
        role, role_reason = _anchor_role_from_quality(quality_delta)
        reasons.append(role_reason)
        if role == ComparableAnchorRole.UNINTERPRETED:
            warnings.append("Modifier quality delta does not provide a directional valuation anchor.")

    comparable_item = result.comparable_item.parsed_item if result.comparable_item is not None else None
    return ComparableValuationAnchor(
        comparable_id=result.comparable_id,
        external_listing_id=result.external_listing_id,
        item_name=comparable_item.item_name if comparable_item is not None else None,
        base_type=comparable_item.base_type if comparable_item is not None else None,
        role=role,
        listing_price=result.listing_price,
        listing_currency_asset_id=result.listing_currency_asset_id,
        normalized_value=result.normalized_value,
        structural_relevance_band=relevance.band if relevance is not None else None,
        structural_relevance_score=relevance.score if relevance is not None else None,
        current_better_count=quality_delta.current_better_count if quality_delta is not None else 0,
        comparable_better_count=quality_delta.comparable_better_count if quality_delta is not None else 0,
        roughly_equivalent_count=quality_delta.roughly_equivalent_count if quality_delta is not None else 0,
        unknown_count=quality_delta.unknown_count if quality_delta is not None else 0,
        reasons=tuple(reasons),
        warnings=tuple(warnings),
    )


def _anchor_role_from_quality(quality_delta: ComparableQualityDelta) -> tuple[ComparableAnchorRole, str]:
    if quality_delta.current_better_count > quality_delta.comparable_better_count:
        return (
            ComparableAnchorRole.LOWER_ANCHOR,
            "Current item is structurally stronger on more matched modifiers; comparable listing is treated as a lower anchor.",
        )
    if quality_delta.comparable_better_count > quality_delta.current_better_count:
        return (
            ComparableAnchorRole.UPPER_ANCHOR,
            "Comparable item is structurally stronger on more matched modifiers; comparable listing is treated as an upper anchor.",
        )
    if quality_delta.roughly_equivalent_count > 0:
        return (
            ComparableAnchorRole.EQUIVALENT_ANCHOR,
            "Comparable item is roughly equivalent by matched modifier quality summary.",
        )
    return (
        ComparableAnchorRole.UNINTERPRETED,
        "Modifier quality summary is not directional enough to anchor a current-item valuation.",
    )


def decimal_median(values: tuple[Decimal, ...]) -> Decimal:
    if not values:
        raise ValueError("median requires at least one value")
    ordered = tuple(sorted(values))
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / Decimal("2")


def decimal_quantile(values: tuple[Decimal, ...], quantile: Decimal) -> Decimal:
    if not values:
        raise ValueError("quantile requires at least one value")
    q = _decimal(quantile, "quantile")
    if q < Decimal("0") or q > Decimal("1"):
        raise ValueError("quantile must be between 0 and 1")
    ordered = tuple(sorted(values))
    if len(ordered) == 1:
        return ordered[0]
    index = int((Decimal(len(ordered) - 1) * q).to_integral_value(rounding=ROUND_FLOOR))
    return ordered[index]


def _select_evidence_sets(
    evidence_sets: tuple[ComparableEvidenceSet, ...],
    policy: ValuationAggregationPolicy,
) -> tuple[tuple[ComparableEvidenceSet, ...], str | None]:
    if not policy.strict_preferred:
        return evidence_sets, None
    strict = tuple(evidence_set for evidence_set in evidence_sets if evidence_set.query.strategy == ComparableStrategy.STRICT)
    moderate = tuple(evidence_set for evidence_set in evidence_sets if evidence_set.query.strategy == ComparableStrategy.MODERATE)
    strict_usable = sum(len(evidence_set.usable_results) for evidence_set in strict)
    if strict and strict_usable >= policy.minimum_ready_comparables:
        return strict, None
    if moderate:
        warning = "STRICT evidence insufficient; MODERATE comparable evidence used as fallback."
        return strict + moderate if strict else moderate, warning
    return strict or evidence_sets, None


def _select_usable_results(
    evidence_sets: tuple[ComparableEvidenceSet, ...],
    policy: ValuationAggregationPolicy,
) -> tuple[tuple[ComparableResult, ...], tuple[ExcludedComparable, ...]]:
    usable = [result for evidence_set in evidence_sets for result in evidence_set.usable_results]
    selected: list[ComparableResult] = []
    excluded: list[ExcludedComparable] = []
    seen_listing_ids: set[str] = set()
    for result in usable:
        if policy.exclude_duplicate_listing_ids and result.external_listing_id:
            if result.external_listing_id in seen_listing_ids:
                excluded.append(ExcludedComparable(result.comparable_id, ComparableExclusionReason.DUPLICATE_LISTING, policy.policy_id, result))
                continue
            seen_listing_ids.add(result.external_listing_id)
        if not policy.stale_evidence_is_allowed and result.economy_freshness == FreshnessState.STALE:
            excluded.append(ExcludedComparable(result.comparable_id, ComparableExclusionReason.STALE_POLICY, policy.policy_id, result))
            continue
        selected.append(result)
    if policy.exclude_outliers and len(selected) >= 3:
        values = tuple(result.normalized_value.amount for result in selected if result.normalized_value is not None)
        median = decimal_median(values)
        threshold = median * policy.outlier_median_multiplier
        kept = []
        for result in selected:
            assert result.normalized_value is not None
            if median > Decimal("0") and result.normalized_value.amount > threshold:
                excluded.append(ExcludedComparable(result.comparable_id, ComparableExclusionReason.OUTLIER_POLICY, policy.policy_id, result, notes=f"value exceeds {policy.outlier_median_multiplier}x median"))
                continue
            kept.append(result)
        selected = kept
    return tuple(selected), tuple(excluded)


def _aggregation_readiness(count: int, policy: ValuationAggregationPolicy) -> ValuationReadiness:
    if count < policy.minimum_partial_comparables:
        return ValuationReadiness.INSUFFICIENT_DATA
    if count < policy.minimum_ready_comparables:
        return ValuationReadiness.PARTIAL
    return ValuationReadiness.READY


def _trim_values(values: tuple[Decimal, ...], trim_fraction: Decimal) -> tuple[Decimal, ...]:
    if trim_fraction == Decimal("0") or len(values) < 3:
        return values
    count = int((Decimal(len(values)) * trim_fraction).to_integral_value(rounding=ROUND_FLOOR))
    if count == 0:
        return values
    trimmed = values[count:-count]
    return trimmed or values


def _price_spread(values: tuple[Decimal, ...], policy: ValuationAggregationPolicy) -> PriceSpread:
    minimum = values[0]
    maximum = values[-1]
    median = decimal_median(values)
    low = decimal_quantile(values, policy.lower_quantile)
    high = decimal_quantile(values, policy.upper_quantile)
    relative = ((maximum - minimum) / median) if median > Decimal("0") else None
    return PriceSpread(
        minimum=normalized_exalted_value(minimum),
        maximum=normalized_exalted_value(maximum),
        median=normalized_exalted_value(median),
        lower_quantile=normalized_exalted_value(low),
        upper_quantile=normalized_exalted_value(high),
        relative_spread=relative,
    )


def _confidence(
    readiness: ValuationReadiness,
    count: int,
    spread: PriceSpread,
    used: tuple[ComparableResult, ...],
    excluded: list[ExcludedComparable],
) -> Confidence:
    reasons = [f"{count} usable normalized manual listing comparables."]
    if readiness == ValuationReadiness.READY:
        level = ConfidenceLevel.MEDIUM
        reasons.append("Configured READY evidence threshold reached.")
    elif readiness == ValuationReadiness.PARTIAL:
        level = ConfidenceLevel.LOW
        reasons.append("Only PARTIAL comparable evidence is available.")
    else:
        level = ConfidenceLevel.LOW
    if spread.relative_spread is not None and spread.relative_spread > Decimal("1.00"):
        level = ConfidenceLevel.LOW
        reasons.append("Large listing-price spread reduces confidence.")
    if excluded:
        reasons.append("Some observations were excluded by aggregation policy.")
    if any(result.economy_freshness == FreshnessState.STALE for result in used):
        level = ConfidenceLevel.LOW
        reasons.append("Stale economy conversion evidence reduces confidence.")
    return Confidence(level=level, reasons=tuple(reasons), sample_size=count)


def _liquidity(count: int, spread: PriceSpread) -> LiquidityStatus:
    if count <= 0:
        return LiquidityStatus.UNKNOWN
    if count < 3:
        return LiquidityStatus.LOW
    if spread.relative_spread is not None and spread.relative_spread > Decimal("1.00"):
        return LiquidityStatus.LOW
    if count >= 8:
        return LiquidityStatus.HIGH
    return LiquidityStatus.MEDIUM


def _composition(
    evidence_set: ComparableEvidenceSet,
    used: tuple[ComparableResult, ...],
    excluded: list[ExcludedComparable],
) -> StrategyComposition:
    ids = {result.comparable_id for result in evidence_set.results}
    used_count = sum(1 for result in used if result.comparable_id in ids)
    excluded_count = sum(1 for item in excluded if item.comparable_id in ids)
    return StrategyComposition(
        strategy=evidence_set.query.strategy,
        total_results=len(evidence_set.results),
        usable_results=len(evidence_set.usable_results),
        used_results=used_count,
        excluded_results=excluded_count,
    )


def _methodology_summary(policy: ValuationAggregationPolicy) -> str:
    return (
        "Listing-derived manual comparable aggregation using Decimal median as estimate, "
        f"{policy.lower_quantile}/{policy.upper_quantile} nearest-lower-index quantiles as plausible range, "
        "deterministic duplicate handling, and configurable outlier exclusion."
    )


class ManualTradeProvider:
    provider_name = "manual-trade-provider"
    capabilities = TradeProviderCapabilities(
        supports_automatic_search=False,
        supports_manual_observations=True,
        supports_trade_url_generation=False,
        supports_completed_sales=False,
    )

    def prepare_manual_workflow(self, query: ComparableQuery) -> ManualTradeWorkflow:
        return ManualTradeWorkflow(
            query=query,
            provider=self.provider_name,
            capabilities=self.capabilities,
            structured_summary=_query_summary(query),
            instructions=(
                "Open the official Path of Exile Trade site manually.",
                "Recreate the comparable query constraints shown in the structured summary.",
                "Record listing observations without treating them as completed sales.",
            ),
            warnings=("ManualTradeProvider performs no network calls and uses no undocumented Trade API.",),
        )

    def result_from_observation(
        self,
        observation: ManualListingObservation,
        economy_repository: EconomyRepository,
        as_of: datetime,
    ) -> ComparableResult:
        normalized, snapshot_id, freshness, warnings = _normalize_listing(
            observation,
            economy_repository,
            as_of,
        )
        return ComparableResult(
            comparable_id=f"manual-comparable:{observation.observation_id}",
            query_id=observation.query_id,
            provider=self.provider_name,
            external_listing_id=observation.external_listing_id,
            listing_price=observation.amount,
            listing_currency_asset_id=observation.currency_asset_id,
            normalized_value=normalized,
            item_summary=observation.item_summary,
            comparable_item=observation.comparable_item,
            matched_constraints=(),
            observed_at=observation.observed_at,
            retrieved_at=as_of,
            league=observation.league,
            economy_snapshot_id=snapshot_id,
            economy_freshness=freshness,
            provenance=observation.provenance,
            warnings=observation.warnings + tuple(warnings) + _structured_comparable_warnings(observation),
        )


class ComparableRelevanceAssessor:
    """Deterministic structural comparable similarity, not market-value weighting."""

    def assess(self, current_item: ParsedItem | None, comparable: StructuredComparableItem | None) -> ComparableRelevance:
        if current_item is None or comparable is None:
            return ComparableRelevance(
                score=None,
                band=ComparableRelevanceBand.INSUFFICIENT_STATE,
                warnings=("Parsed current item and parsed comparable item are required for structural relevance.",),
            )
        comparable_item = comparable.parsed_item
        if not current_item.explicit_modifiers or not comparable_item.explicit_modifiers:
            return ComparableRelevance(
                score=None,
                band=ComparableRelevanceBand.INSUFFICIENT_STATE,
                warnings=("Both items need parsed explicit modifier state for structural relevance.",),
            )

        base_points, base_reasons = _base_similarity_points(current_item, comparable_item)
        current_modifiers = tuple(current_item.explicit_modifiers)
        comparable_modifiers = tuple(comparable_item.explicit_modifiers)
        available = list(comparable_modifiers)
        matched: list[ComparableModifierRelevance] = []
        differing: list[ComparableModifierRelevance] = []
        missing: list[ComparableModifierRelevance] = []
        score_points = base_points

        for current_modifier in current_modifiers:
            match = _best_modifier_match(current_modifier, available)
            if match is None:
                missing.append(
                    _modifier_relevance(
                        ModifierRelevanceRelationship.MISSING_FROM_COMPARABLE,
                        current_modifier,
                        None,
                        ("Current modifier has no parsed structural counterpart on the comparable.",),
                    )
                )
                continue
            available.remove(match)
            same_tier = _same_tier(current_modifier.tier, match.tier)
            same_origin = current_modifier.origin == match.origin
            if same_tier and same_origin:
                score_points += Decimal("10")
                matched.append(
                    _modifier_relevance(
                        ModifierRelevanceRelationship.EXACT_MATCH,
                        current_modifier,
                        match,
                        ("Same parsed modifier identity, tier, side, and origin.",),
                    )
                )
            else:
                score_points += Decimal("5")
                if same_tier:
                    score_points += Decimal("2")
                    relationship = ModifierRelevanceRelationship.ORIGIN_DIFFERENCE
                    reasons = ("Same parsed modifier identity and tier, but modifier origin differs.",)
                elif same_origin:
                    score_points += Decimal("1")
                    relationship = ModifierRelevanceRelationship.TIER_DIFFERENCE
                    reasons = ("Same parsed modifier identity and origin, but tier differs.",)
                else:
                    relationship = ModifierRelevanceRelationship.TIER_AND_ORIGIN_DIFFERENCE
                    reasons = ("Same parsed modifier identity, but tier and modifier origin differ.",)
                differing.append(_modifier_relevance(relationship, current_modifier, match, reasons))

        extra = tuple(
            _modifier_relevance(
                ModifierRelevanceRelationship.EXTRA_ON_COMPARABLE,
                None,
                modifier,
                ("Comparable has an extra parsed modifier with no current-item counterpart.",),
            )
            for modifier in available
        )
        max_points = Decimal("55") + (Decimal("10") * Decimal(len(current_modifiers)))
        score = min(Decimal("1"), score_points / max_points) if max_points > 0 else Decimal("0")
        warnings = []
        if current_item.item_class != comparable_item.item_class:
            warnings.append("Comparable item class differs from current item.")
        if current_item.rarity != comparable_item.rarity:
            warnings.append("Comparable rarity differs from current item.")
        if extra:
            warnings.append("Comparable has extra parsed modifiers not matched to the current item.")
        return ComparableRelevance(
            score=score.quantize(Decimal("0.0001")),
            band=_relevance_band(score),
            base_similarity=tuple(base_reasons),
            matched_modifiers=tuple(matched),
            differing_modifiers=tuple(differing),
            missing_modifiers=tuple(missing),
            extra_modifiers=extra,
            warnings=tuple(warnings),
        )


class ComparableQualityDeltaAssessor:
    """Directional modifier-quality comparison, separate from structural relevance and market value."""

    def assess(self, current_item: ParsedItem | None, comparable: StructuredComparableItem | None) -> ComparableQualityDelta:
        if current_item is None or comparable is None:
            return ComparableQualityDelta(
                warnings=("Parsed current item and parsed comparable item are required for modifier quality delta.",),
            )
        comparable_item = comparable.parsed_item
        if not current_item.explicit_modifiers or not comparable_item.explicit_modifiers:
            return ComparableQualityDelta(
                warnings=("Both items need parsed explicit modifier state for modifier quality delta.",),
            )

        current_modifiers = tuple(current_item.explicit_modifiers)
        available = list(comparable_item.explicit_modifiers)
        deltas: list[ModifierQualityDelta] = []
        for current_modifier in current_modifiers:
            match = _best_modifier_match(current_modifier, available)
            if match is None:
                deltas.append(
                    _quality_delta(
                        ModifierQualityRelationship.MISSING_FROM_COMPARABLE,
                        ModifierQualityEvidence.INSUFFICIENT,
                        current_modifier,
                        None,
                        ("Current modifier has no same-side parsed semantic counterpart on the comparable.",),
                    )
                )
                continue
            available.remove(match)
            deltas.append(_quality_delta_for_match(current_modifier, match))
        deltas.extend(
            _quality_delta(
                ModifierQualityRelationship.EXTRA_ON_COMPARABLE,
                ModifierQualityEvidence.INSUFFICIENT,
                None,
                modifier,
                ("Comparable has an extra parsed modifier with no current-item counterpart.",),
            )
            for modifier in available
        )
        return ComparableQualityDelta(
            modifier_deltas=tuple(deltas),
            current_better_count=sum(1 for delta in deltas if delta.relationship == ModifierQualityRelationship.CURRENT_BETTER),
            comparable_better_count=sum(1 for delta in deltas if delta.relationship == ModifierQualityRelationship.COMPARABLE_BETTER),
            roughly_equivalent_count=sum(1 for delta in deltas if delta.relationship == ModifierQualityRelationship.ROUGHLY_EQUIVALENT),
            unknown_count=sum(1 for delta in deltas if delta.relationship == ModifierQualityRelationship.UNKNOWN),
            missing_from_comparable_count=sum(1 for delta in deltas if delta.relationship == ModifierQualityRelationship.MISSING_FROM_COMPARABLE),
            extra_on_comparable_count=sum(1 for delta in deltas if delta.relationship == ModifierQualityRelationship.EXTRA_ON_COMPARABLE),
            warnings=(
                "Modifier quality delta is structural only; it is not a price multiplier, valuation weight, or recommendation signal.",
            ),
        )


def subject_from_parsed_item(
    item: ParsedItem,
    dataset_versions: tuple[str, ...] = (),
) -> ValuationSubject:
    return ValuationSubject(
        subject_id=f"valuation-subject:item:{item.analysis_id}",
        item_class=item.item_class,
        base_type=item.base_type,
        item_level=item.item_level,
        rarity=item.rarity,
        modifiers=item.modifiers,
        source_item_analysis_id=item.analysis_id,
        dataset_versions=dataset_versions,
        provenance=item.provenance,
    )


def subject_from_hypothetical_state(
    source_item: ParsedItem,
    hypothetical_state: HypotheticalItemState,
    dataset_versions: tuple[str, ...] = (),
) -> ValuationSubject:
    return ValuationSubject(
        subject_id=f"valuation-subject:hypothetical:{hypothetical_state.outcome_id}",
        item_class=source_item.item_class,
        base_type=source_item.base_type,
        item_level=source_item.item_level,
        rarity=source_item.rarity,
        modifiers=source_item.modifiers,
        source_item_analysis_id=source_item.analysis_id,
        hypothetical_state_id=hypothetical_state.outcome_id,
        dataset_versions=dataset_versions,
        provenance=source_item.provenance,
        warnings=("Hypothetical state deltas are retained by identity; Task 10B does not materialize final item modifiers.",),
    )


def build_comparable_query(
    subject: ValuationSubject,
    roles: tuple[ModifierComparableRoleAssignment, ...],
    strategy: ComparableStrategy,
    league: str,
    generated_at: datetime,
    require_same_base: bool = True,
) -> ComparableQuery:
    if strategy == ComparableStrategy.BUILD_EQUIVALENT:
        return ComparableQuery(
            query_id=f"comparable-query:{subject.subject_id}:build-equivalent",
            valuation_subject_id=subject.subject_id,
            strategy=strategy,
            item_class=subject.item_class,
            league=league,
            generated_at=generated_at,
            warnings=("Build-equivalent comparable generation requires future modifier relevance data.",),
        )
    if strategy == ComparableStrategy.COST_TO_REPRODUCE:
        return ComparableQuery(
            query_id=f"comparable-query:{subject.subject_id}:cost-to-reproduce",
            valuation_subject_id=subject.subject_id,
            strategy=strategy,
            item_class=subject.item_class,
            league=league,
            generated_at=generated_at,
            warnings=("Cost-to-reproduce is a future supporting signal, not a listing comparable query.",),
        )

    value_driving = tuple(role for role in roles if role.role == ModifierComparableRole.VALUE_DRIVING)
    warnings: list[str] = []
    if not value_driving:
        warnings.append("No VALUE_DRIVING modifier roles supplied; comparable query is insufficient.")
    relaxation_rules: tuple[str, ...] = ()
    match_mode = ModifierMatchMode.EXACT
    if strategy == ComparableStrategy.MODERATE:
        relaxation_rules = ("Allow one-tier relaxation where tier identity is known.", "Use relaxed roll thresholds instead of exact rolls.")
        match_mode = ModifierMatchMode.RELAXED
    constraints = tuple(_constraint(role, match_mode) for role in value_driving)
    ignored = tuple(_modifier_identity(role.modifier) for role in roles if role.role == ModifierComparableRole.IGNORE_FOR_COMPARABLE)
    return ComparableQuery(
        query_id=f"comparable-query:{subject.subject_id}:{strategy.value.lower()}",
        valuation_subject_id=subject.subject_id,
        strategy=strategy,
        item_class=subject.item_class,
        base_type=subject.base_type if require_same_base else None,
        rarity=subject.rarity,
        min_item_level=subject.item_level,
        included_modifier_constraints=constraints,
        ignored_modifiers=ignored,
        relaxation_rules=relaxation_rules,
        league=league,
        generated_at=generated_at,
        warnings=tuple(warnings),
    )


def evidence_set_from_results(
    query: ComparableQuery,
    provider: str,
    results: tuple[ComparableResult, ...],
    policy: ValuationEvidencePolicy = ValuationEvidencePolicy(),
) -> ComparableEvidenceSet:
    warnings = []
    economy_snapshot_ids = tuple(
        sorted({result.economy_snapshot_id for result in results if result.economy_snapshot_id})
    )
    evidence = ComparableEvidenceSet(
        evidence_set_id=f"comparable-evidence:{query.query_id}",
        query=query,
        provider=provider,
        results=results,
        policy=policy,
        economy_snapshot_ids=economy_snapshot_ids,
        warnings=(),
    )
    if evidence.duplicate_listing_ids:
        warnings.append(f"Duplicate listing IDs observed: {', '.join(evidence.duplicate_listing_ids)}")
    if evidence.unusable_result_count:
        warnings.append(f"{evidence.unusable_result_count} comparable result(s) lack normalized prices.")
    return ComparableEvidenceSet(
        evidence_set_id=evidence.evidence_set_id,
        query=query,
        provider=provider,
        results=results,
        policy=policy,
        economy_snapshot_ids=economy_snapshot_ids,
        warnings=tuple(warnings),
    )


def _base_similarity_points(current_item: ParsedItem, comparable_item: ParsedItem) -> tuple[Decimal, tuple[str, ...]]:
    points = Decimal("0")
    reasons: list[str] = []
    if current_item.item_class and current_item.item_class == comparable_item.item_class:
        points += Decimal("20")
        reasons.append(f"Both items are {current_item.item_class}.")
    elif current_item.item_class or comparable_item.item_class:
        reasons.append(f"Item class differs: {current_item.item_class or 'UNKNOWN'} vs {comparable_item.item_class or 'UNKNOWN'}.")
    if current_item.rarity == comparable_item.rarity:
        points += Decimal("15")
        reasons.append(f"Both items have rarity {current_item.rarity.value}.")
    else:
        reasons.append(f"Rarity differs: {current_item.rarity.value} vs {comparable_item.rarity.value}.")
    if current_item.item_level is not None and comparable_item.item_level is not None:
        difference = abs(current_item.item_level - comparable_item.item_level)
        if difference == 0:
            points += Decimal("10")
            reasons.append(f"Both items have item level {current_item.item_level}.")
        elif difference <= 5:
            points += Decimal("6")
            reasons.append(f"Item levels are close: {current_item.item_level} vs {comparable_item.item_level}.")
        else:
            reasons.append(f"Item levels differ materially: {current_item.item_level} vs {comparable_item.item_level}.")
    if current_item.base_type and current_item.base_type == comparable_item.base_type:
        points += Decimal("10")
        reasons.append(f"Both items use base type {current_item.base_type}.")
    elif current_item.base_type or comparable_item.base_type:
        points += Decimal("3")
        reasons.append(f"Base type differs: {current_item.base_type or 'UNKNOWN'} vs {comparable_item.base_type or 'UNKNOWN'}.")
    current_implicit = {_modifier_semantic_identity(modifier) for modifier in current_item.implicit_modifiers}
    comparable_implicit = {_modifier_semantic_identity(modifier) for modifier in comparable_item.implicit_modifiers}
    if current_implicit and current_implicit == comparable_implicit:
        points += Decimal("10")
        reasons.append("Implicit modifier effect matches structurally.")
    elif current_implicit or comparable_implicit:
        reasons.append("Implicit modifier effect differs.")
    current_states = tuple(sorted(state.value for state in current_item.special_states))
    comparable_states = tuple(sorted(state.value for state in comparable_item.special_states))
    if current_states == comparable_states and current_states:
        reasons.append(f"Special item states match: {', '.join(current_states)}.")
    elif current_states or comparable_states:
        reasons.append(
            "Special item states differ: "
            f"{', '.join(current_states) if current_states else 'NONE'} vs "
            f"{', '.join(comparable_states) if comparable_states else 'NONE'}."
        )
    return points, tuple(reasons)


def _best_modifier_match(current_modifier: ItemModifier, candidates: list[ItemModifier]) -> ItemModifier | None:
    identity = _modifier_semantic_identity(current_modifier)
    same_side = [
        candidate
        for candidate in candidates
        if candidate.affix_type == current_modifier.affix_type
        and _modifier_semantic_identity(candidate) == identity
    ]
    if not same_side:
        return None
    same_tier_origin = [
        candidate
        for candidate in same_side
        if _same_tier(current_modifier.tier, candidate.tier) and candidate.origin == current_modifier.origin
    ]
    if same_tier_origin:
        return same_tier_origin[0]
    same_tier = [candidate for candidate in same_side if _same_tier(current_modifier.tier, candidate.tier)]
    if same_tier:
        return same_tier[0]
    same_origin = [candidate for candidate in same_side if candidate.origin == current_modifier.origin]
    if same_origin:
        return same_origin[0]
    return same_side[0]


def _modifier_relevance(
    relationship: ModifierRelevanceRelationship,
    current_modifier: ItemModifier | None,
    comparable_modifier: ItemModifier | None,
    reasons: tuple[str, ...],
) -> ComparableModifierRelevance:
    reference = current_modifier or comparable_modifier
    assert reference is not None
    current_tags = tuple(sorted(current_modifier.tags)) if current_modifier else ()
    comparable_tags = tuple(sorted(comparable_modifier.tags)) if comparable_modifier else ()
    current_roll_values = _roll_values(current_modifier) if current_modifier else ()
    comparable_roll_values = _roll_values(comparable_modifier) if comparable_modifier else ()
    tag_match = current_tags == comparable_tags if current_modifier and comparable_modifier else None
    roll_match = current_roll_values == comparable_roll_values if current_modifier and comparable_modifier else None
    expanded_reasons = list(reasons)
    if tag_match is False:
        expanded_reasons.append("Parsed modifier tags differ.")
    if roll_match is False:
        expanded_reasons.append("Observed roll values or displayed ranges differ.")
    return ComparableModifierRelevance(
        relationship=relationship,
        semantic_identity=_modifier_semantic_identity(reference),
        affix_type=reference.affix_type,
        current_display_name=current_modifier.display_name if current_modifier else None,
        comparable_display_name=comparable_modifier.display_name if comparable_modifier else None,
        current_tier=current_modifier.tier if current_modifier else None,
        comparable_tier=comparable_modifier.tier if comparable_modifier else None,
        current_origin=current_modifier.origin.value if current_modifier else None,
        comparable_origin=comparable_modifier.origin.value if comparable_modifier else None,
        current_tags=current_tags,
        comparable_tags=comparable_tags,
        current_roll_values=current_roll_values,
        comparable_roll_values=comparable_roll_values,
        tag_match=tag_match,
        roll_observation_match=roll_match,
        reasons=tuple(expanded_reasons),
    )


def _roll_values(modifier: ItemModifier) -> tuple[str, ...]:
    values: list[str] = []
    for roll in modifier.observed_rolls:
        parts = []
        if roll.label:
            parts.append(f"label={roll.label}")
        if roll.value is not None:
            parts.append(f"value={roll.value}")
        if roll.min_value is not None or roll.max_value is not None:
            parts.append(f"range={roll.min_value}:{roll.max_value}")
        values.append(";".join(parts) if parts else "unknown-roll")
    return tuple(values)


def _quality_delta_for_match(current_modifier: ItemModifier, comparable_modifier: ItemModifier) -> ModifierQualityDelta:
    origin_difference = current_modifier.origin != comparable_modifier.origin
    reasons: list[str] = []
    if origin_difference:
        reasons.append(
            f"Modifier origin differs: {current_modifier.origin.value} vs {comparable_modifier.origin.value}; no market premium is inferred."
        )
    tier_result = _tier_quality_relationship(current_modifier.tier, comparable_modifier.tier)
    if tier_result is not None:
        relationship, reason = tier_result
        reasons.append(reason)
        return _quality_delta(
            relationship,
            ModifierQualityEvidence.TIER,
            current_modifier,
            comparable_modifier,
            tuple(reasons),
        )

    roll_result = _roll_quality_relationship(current_modifier, comparable_modifier)
    if roll_result is not None:
        relationship, current_quality, comparable_quality, reason = roll_result
        reasons.append(reason)
        return _quality_delta(
            relationship,
            ModifierQualityEvidence.ROLL_WITHIN_TIER,
            current_modifier,
            comparable_modifier,
            tuple(reasons),
            current_roll_quality=current_quality,
            comparable_roll_quality=comparable_quality,
        )

    if _same_tier(current_modifier.tier, comparable_modifier.tier):
        reasons.append("Same parsed semantic identity and tier; roll quality could not provide a directional distinction.")
        return _quality_delta(
            ModifierQualityRelationship.ROUGHLY_EQUIVALENT,
            ModifierQualityEvidence.IDENTITY_ONLY,
            current_modifier,
            comparable_modifier,
            tuple(reasons),
        )

    reasons.append("Parsed semantic identity matches, but tier or roll evidence is insufficient for directional quality.")
    return _quality_delta(
        ModifierQualityRelationship.UNKNOWN,
        ModifierQualityEvidence.INSUFFICIENT,
        current_modifier,
        comparable_modifier,
        tuple(reasons),
    )


def _quality_delta(
    relationship: ModifierQualityRelationship,
    evidence: ModifierQualityEvidence,
    current_modifier: ItemModifier | None,
    comparable_modifier: ItemModifier | None,
    reasons: tuple[str, ...],
    current_roll_quality: Decimal | None = None,
    comparable_roll_quality: Decimal | None = None,
) -> ModifierQualityDelta:
    reference = current_modifier or comparable_modifier
    assert reference is not None
    return ModifierQualityDelta(
        relationship=relationship,
        evidence=evidence,
        semantic_identity=_modifier_semantic_identity(reference),
        affix_type=reference.affix_type,
        current_display_name=current_modifier.display_name if current_modifier else None,
        comparable_display_name=comparable_modifier.display_name if comparable_modifier else None,
        current_tier=current_modifier.tier if current_modifier else None,
        comparable_tier=comparable_modifier.tier if comparable_modifier else None,
        current_origin=current_modifier.origin.value if current_modifier else None,
        comparable_origin=comparable_modifier.origin.value if comparable_modifier else None,
        current_roll_quality=current_roll_quality,
        comparable_roll_quality=comparable_roll_quality,
        current_roll_values=_roll_values(current_modifier) if current_modifier else (),
        comparable_roll_values=_roll_values(comparable_modifier) if comparable_modifier else (),
        origin_difference=(current_modifier.origin != comparable_modifier.origin) if current_modifier and comparable_modifier else False,
        reasons=reasons,
    )


def _tier_quality_relationship(
    current_tier: str | None,
    comparable_tier: str | None,
) -> tuple[ModifierQualityRelationship, str] | None:
    current_number = _tier_number(current_tier)
    comparable_number = _tier_number(comparable_tier)
    if current_number is None or comparable_number is None:
        return None
    if current_number < comparable_number:
        return (
            ModifierQualityRelationship.CURRENT_BETTER,
            f"Current item has the stronger parsed tier: T{current_number} vs comparable T{comparable_number}.",
        )
    if comparable_number < current_number:
        return (
            ModifierQualityRelationship.COMPARABLE_BETTER,
            f"Comparable has the stronger parsed tier: T{comparable_number} vs current T{current_number}.",
        )
    return None


def _roll_quality_relationship(
    current_modifier: ItemModifier,
    comparable_modifier: ItemModifier,
) -> tuple[ModifierQualityRelationship, Decimal, Decimal, str] | None:
    current_quality = _roll_quality(current_modifier.observed_rolls)
    comparable_quality = _roll_quality(comparable_modifier.observed_rolls)
    if current_quality is None or comparable_quality is None:
        return None
    if current_quality > comparable_quality:
        return (
            ModifierQualityRelationship.CURRENT_BETTER,
            current_quality,
            comparable_quality,
            f"Current item has the better same-tier observed roll quality: {current_quality} vs {comparable_quality}.",
        )
    if comparable_quality > current_quality:
        return (
            ModifierQualityRelationship.COMPARABLE_BETTER,
            current_quality,
            comparable_quality,
            f"Comparable has the better same-tier observed roll quality: {comparable_quality} vs {current_quality}.",
        )
    return (
        ModifierQualityRelationship.ROUGHLY_EQUIVALENT,
        current_quality,
        comparable_quality,
        f"Same-tier observed roll quality is equivalent: {current_quality}.",
    )


def _roll_quality(rolls: tuple[RollValue, ...]) -> Decimal | None:
    if not rolls:
        return None
    qualities: list[Decimal] = []
    for roll in rolls:
        if roll.value is None or roll.min_value is None or roll.max_value is None:
            return None
        if roll.max_value < roll.min_value:
            return None
        if roll.max_value == roll.min_value:
            qualities.append(Decimal("1"))
            continue
        qualities.append((roll.value - roll.min_value) / (roll.max_value - roll.min_value))
    return (sum(qualities, Decimal("0")) / Decimal(len(qualities))).quantize(Decimal("0.0001"))


def _tier_number(tier: str | None) -> int | None:
    if tier is None:
        return None
    try:
        value = int(str(tier).strip())
    except ValueError:
        return None
    return value if value > 0 else None


def _modifier_semantic_identity(modifier: ItemModifier) -> str:
    if modifier.canonical_id:
        return f"canonical:{modifier.canonical_id}"
    if modifier.family or modifier.group:
        return f"group:{modifier.family or modifier.group}"
    text = modifier.normalized_text or modifier.raw_text
    template = re.sub(r"[+-]?\d+(?:\.\d+)?(?:\([^)]+\))?", "#", text)
    template = re.sub(r"\s+", " ", template).strip().lower()
    return f"{modifier.affix_type.value}:{template}"


def _same_tier(first: str | None, second: str | None) -> bool:
    return (first or "").strip() == (second or "").strip()


def _relevance_band(score: Decimal) -> ComparableRelevanceBand:
    if score >= Decimal("0.75"):
        return ComparableRelevanceBand.HIGH
    if score >= Decimal("0.45"):
        return ComparableRelevanceBand.MEDIUM
    if score >= Decimal("0.20"):
        return ComparableRelevanceBand.LOW
    return ComparableRelevanceBand.NOT_COMPARABLE


def _constraint(role: ModifierComparableRoleAssignment, match_mode: ModifierMatchMode) -> ModifierConstraint:
    modifier = role.modifier
    return ModifierConstraint(
        modifier_identity=_modifier_identity(modifier),
        role=role.role,
        affix_type=modifier.affix_type,
        canonical_modifier_id=modifier.canonical_id,
        modifier_family_id=modifier.family or modifier.group,
        display_name=modifier.display_name,
        min_tier=modifier.tier if match_mode == ModifierMatchMode.EXACT else _relaxed_tier(modifier.tier, 1),
        max_tier=modifier.tier,
        min_roll=modifier.observed_rolls[0] if modifier.observed_rolls else None,
        match_mode=match_mode,
    )


def _normalize_listing(
    observation: ManualListingObservation,
    repository: EconomyRepository,
    as_of: datetime,
) -> tuple[EconomicValue | None, str | None, FreshnessState, list[str]]:
    if observation.currency_asset_id == EXALTED_ASSET_ID:
        return normalized_exalted_value(observation.amount), None, FreshnessState.FRESH, []
    quote = repository.get_current_quote(observation.league, observation.currency_asset_id, as_of)
    if quote is None or quote.normalized_value is None:
        return None, None, FreshnessState.UNAVAILABLE, [f"Missing economy conversion for {observation.currency_asset_id}"]
    return normalized_exalted_value(observation.amount * quote.normalized_value.amount), quote.snapshot_id, quote.freshness, []


def _structured_comparable_warnings(observation: ManualListingObservation) -> tuple[str, ...]:
    if observation.comparable_item is None:
        return ("Manual observation has no parsed comparable item state; it is not structurally verified.",)
    return ()


def _query_summary(query: ComparableQuery) -> str:
    modifier_bits = ", ".join(
        constraint.display_name or constraint.modifier_family_id or constraint.modifier_identity
        for constraint in query.included_modifier_constraints
    )
    return (
        f"{query.strategy.value} {query.item_class or 'item'} query"
        f" base={query.base_type or 'ANY'}"
        f" modifiers=[{modifier_bits or 'NONE'}]"
        f" league={query.league or 'UNKNOWN'}"
    )


def _modifier_identity(modifier: ItemModifier) -> str:
    return modifier.canonical_id or modifier.display_name or modifier.normalized_text or modifier.raw_text


def _relaxed_tier(tier: str | None, amount: int) -> str | None:
    if tier is None or not tier.isdigit():
        return tier
    return str(max(1, int(tier) - amount))


def _decimal(value: Decimal | int | str, field_name: str) -> Decimal:
    if isinstance(value, float):
        raise TypeError(f"{field_name} must not use binary floating point")
    return Decimal(value)
