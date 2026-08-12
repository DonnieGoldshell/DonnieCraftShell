"""Framework-independent rare-item valuation evidence contracts.

Task 10B structures comparable evidence and manual trade observations. It does
not scrape trade sites, aggregate market value, calculate EV, or recommend.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum

from .craft_outcomes import HypotheticalItemState
from .domain import (
    AffixType,
    ComparableStrategy,
    Confidence,
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


VALUATION_CONTRACT_VERSION = "valuation-contract-task10b"


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
    estimated_value: EconomicValue | None = None
    plausible_low: EconomicValue | None = None
    plausible_high: EconomicValue | None = None
    confidence: Confidence | None = None
    strategy: ComparableStrategy | None = None
    comparable_count: int = 0
    source_evidence_ids: tuple[str, ...] = ()
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
    def aggregate(self, evidence_set: ComparableEvidenceSet) -> ValuationResult:
        return ValuationResult(
            readiness=evidence_set.readiness,
            strategy=evidence_set.query.strategy,
            comparable_count=len(evidence_set.usable_results),
            source_evidence_ids=(evidence_set.evidence_set_id,),
            warnings=("Task 10B does not implement market-value aggregation.",),
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
        normalized, snapshot_id, warnings = _normalize_listing(
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
) -> tuple[EconomicValue | None, str | None, list[str]]:
    if observation.currency_asset_id == EXALTED_ASSET_ID:
        return normalized_exalted_value(observation.amount), None, []
    quote = repository.get_current_quote(observation.league, observation.currency_asset_id, as_of)
    if quote is None or quote.normalized_value is None:
        return None, None, [f"Missing economy conversion for {observation.currency_asset_id}"]
    return normalized_exalted_value(observation.amount * quote.normalized_value.amount), quote.snapshot_id, []


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
