"""Framework-independent rare-item valuation evidence contracts.

Task 10B structures comparable evidence and manual trade observations. Task
10C adds conservative listing-derived aggregation. This module does not scrape
trade sites, calculate EV, or recommend.
"""

from __future__ import annotations

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
class ManualListingObservation:
    observation_id: str
    query_id: str
    amount: Decimal
    currency_asset_id: str
    league: str
    observed_at: datetime
    external_listing_id: str | None = None
    item_summary: str | None = None
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
            matched_constraints=(),
            observed_at=observation.observed_at,
            retrieved_at=as_of,
            league=observation.league,
            economy_snapshot_id=snapshot_id,
            economy_freshness=freshness,
            provenance=observation.provenance,
            warnings=observation.warnings + tuple(warnings),
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
