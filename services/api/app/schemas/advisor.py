"""Advisor analysis API schemas."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import Field, field_validator

from .common import ApiModel, EconomicValueDto, GameContextDto


class ManualListingObservationDto(ApiModel):
    amount: str = Field(description="Decimal listing amount encoded as string.")
    currency_asset_id: str
    external_listing_id: str | None = None
    observed_at: datetime | None = None
    item_summary: str | None = None
    notes: str | None = None

    @field_validator("amount")
    @classmethod
    def amount_is_decimal(cls, value: str) -> str:
        Decimal(value)
        return value


class ManualValuationEvidenceDto(ApiModel):
    strategy: str = "STRICT"
    observations: list[ManualListingObservationDto] = []
    notes: str | None = None


class OutcomeManualValuationEvidenceDto(ApiModel):
    outcome_id: str
    evidence: ManualValuationEvidenceDto


class AdvisorAnalyzeRequestDto(ApiModel):
    clipboard_text: str
    league: str
    game_context: GameContextDto | None = None
    game_data_dataset_version: str
    crafting_dataset_version: str
    affix_capacity_dataset_version: str
    empirical_probability_dataset_version: str | None = None
    as_of: datetime | None = None
    bankroll: EconomicValueDto | None = None
    risk_profile: str | None = None
    current_valuation_evidence: ManualValuationEvidenceDto | None = None
    outcome_valuation_evidence: list[OutcomeManualValuationEvidenceDto] = []


class ModifierDto(ApiModel):
    display_name: str | None = None
    tier: str | None = None
    affix_type: str | None = None
    origin: str | None = None
    tags: list[str] = []
    raw_text: str
    resolution_status: str | None = None
    canonical_id: str | None = None


class ItemSummaryDto(ApiModel):
    rarity: str | None = None
    item_name: str | None = None
    base_type: str | None = None
    item_class: str | None = None
    item_level: int | None = None
    required_level: int | None = None
    special_states: list[str] = []
    implicit_modifiers: list[ModifierDto] = []
    prefixes: list[ModifierDto] = []
    suffixes: list[ModifierDto] = []
    corruption_enhancements: list[ModifierDto] = []
    unparsed_lines: list[str] = []


class EnrichmentSummaryDto(ApiModel):
    enrichment_id: str | None = None
    snapshot_id: str | None = None
    resolved_base_id: str | None = None
    resolved_modifier_count: int = 0
    ambiguous_modifier_count: int = 0
    unresolved_modifier_count: int = 0
    warnings: list[str] = []


class AffixStateDto(ApiModel):
    observed_prefix_count: int | None = None
    observed_suffix_count: int | None = None
    prefix_capacity: int | None = None
    suffix_capacity: int | None = None
    open_prefix_count: int | None = None
    open_suffix_count: int | None = None
    warnings: list[str] = []


class MaterialRequirementDto(ApiModel):
    asset_id: str
    quantity: str


class MaterialCostDto(ApiModel):
    complete: bool
    total: EconomicValueDto | None = None
    freshness: str
    warnings: list[str] = []
    lines: list[dict] = []


class ScenarioSummaryDto(ApiModel):
    readiness: str | None = None
    outcome_count: int = 0
    valued_outcome_count: int = 0
    unvalued_outcome_count: int = 0
    valuation_completeness: str | None = None
    best_valuated_outcome: EconomicValueDto | None = None
    worst_valuated_outcome: EconomicValueDto | None = None
    median_valuated_outcome: EconomicValueDto | None = None
    upside_relative_to_current: EconomicValueDto | None = None
    downside_relative_to_current: EconomicValueDto | None = None
    reasons: list[str] = []


class ExpectedValueSummaryDto(ApiModel):
    available: bool
    status: str | None = None
    gross_expected_outcome_value: EconomicValueDto | None = None
    craft_cost: EconomicValueDto | None = None
    net_expected_value: EconomicValueDto | None = None
    current_item_value: EconomicValueDto | None = None
    expected_gain_vs_sell_now: EconomicValueDto | None = None
    roi_on_craft_cost: str | None = None
    unavailable_reasons: list[str] = []
    algorithm_version: str | None = None


class ProbabilityIntervalDto(ApiModel):
    lower: str
    upper: str


class ProbabilityEvidenceSummaryDto(ApiModel):
    evidence_id: str
    probability_type: str
    outcome_id: str | None = None
    probability: str | None = None
    methodology: str | None = None
    sample_size: int | None = None
    uncertainty_interval: ProbabilityIntervalDto | None = None
    evidence_dataset_version: str | None = None
    warnings: list[str] = []


class OutcomeProbabilitySummaryDto(ApiModel):
    outcome_id: str
    probability: str | None = None
    evidence: list[ProbabilityEvidenceSummaryDto] = []
    warnings: list[str] = []


class ProbabilitySummaryDto(ApiModel):
    source_outcome_set_id: str
    completeness: str
    total_known_probability_mass: str | None = None
    methodology_summary: str | None = None
    known_outcome_count: int = 0
    outcome_count: int = 0
    dataset_versions: list[str] = []
    outcome_probabilities: list[OutcomeProbabilitySummaryDto] = []
    warnings: list[str] = []


class ActionAnalysisDto(ApiModel):
    action_id: str
    display_name: str
    applicability: str
    applicability_reasons: list[str] = []
    failed_preconditions: list[str] = []
    unknown_preconditions: list[str] = []
    required_materials: list[MaterialRequirementDto] = []
    material_cost: MaterialCostDto
    outcome_count: int = 0
    outcome_ids: list[str] = []
    outcome_space_completeness: str | None = None
    probability_completeness: str | None = None
    probability: ProbabilitySummaryDto | None = None
    scenario: ScenarioSummaryDto | None = None
    expected_value: ExpectedValueSummaryDto | None = None
    advisor_candidate_status: str | None = None
    warnings: list[str] = []
    missing_requirements: list["MissingRequirementDto"] = []


class AdvisorDecisionDto(ApiModel):
    decision_type: str
    selected_candidate_id: str | None = None
    reasons: list[str] = []
    warnings: list[str] = []
    algorithm_version: str | None = None


class RiskAdjustedDecisionDto(ApiModel):
    decision_type: str
    raw_winner_candidate_id: str | None = None
    selected_candidate_id: str | None = None
    changed_by_policy: bool
    risk_policy_version: str | None = None
    reasons: list[str] = []
    triggered_rules: list[str] = []


class MissingRequirementDto(ApiModel):
    type: str
    action_id: str | None = None
    blocks: list[str] = []
    reason: str


class AdvisorContextDto(ApiModel):
    league: str
    game_data_dataset_version: str
    crafting_dataset_version: str
    affix_capacity_dataset_version: str
    empirical_probability_dataset_version: str | None = None
    as_of: datetime | None = None
    economy_snapshot_ids: list[str] = []


class AdvisorAnalyzeResponseDto(ApiModel):
    analysis_id: str
    status: str
    context: AdvisorContextDto
    item: ItemSummaryDto | None = None
    enrichment_summary: EnrichmentSummaryDto | None = None
    affix_state: AffixStateDto | None = None
    actions: list[ActionAnalysisDto] = []
    decision: AdvisorDecisionDto | None = None
    risk_adjusted_decision: RiskAdjustedDecisionDto | None = None
    missing_requirements: list[MissingRequirementDto] = []
    warnings: list[str] = []
    provenance: list[dict] = []


ActionAnalysisDto.model_rebuild()
