"""Advisor API request/response mappers."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from packages.shared.donniecraftshell_contracts.advisor_decision import AdvisorDecision
from packages.shared.donniecraftshell_contracts.advisor_orchestration import (
    AdvisorAnalysisRequest,
    AdvisorAnalysisResult,
)
from packages.shared.donniecraftshell_contracts.advisor_risk import AdvisorRiskContext, RiskProfile
from packages.shared.donniecraftshell_contracts.domain import (
    AffixType,
    ComparableStrategy,
    DataProvenance,
    EconomicValue,
    GameContext,
    ItemModifier,
    SourceType,
)
from packages.shared.donniecraftshell_contracts.economy import EXALTED_ECONOMIC_UNIT
from packages.shared.donniecraftshell_contracts.economy_repository import EconomyRepository
from packages.shared.donniecraftshell_contracts.game_data import ItemEnrichment, ResolutionStatus
from packages.shared.donniecraftshell_contracts.valuation import (
    ComparableQuery,
    ManualListingObservation,
    ManualTradeProvider,
    ValuationAggregator,
    ValuationEvidencePolicy,
    ValuationResult,
    evidence_set_from_results,
)

from services.api.app.mappers.common import economic_value_to_dto, to_jsonable
from services.api.app.schemas.advisor import (
    ActionAnalysisDto,
    AdvisorAnalyzeRequestDto,
    AdvisorAnalyzeResponseDto,
    AdvisorContextDto,
    AdvisorDecisionDto,
    AffixStateDto,
    EnrichmentSummaryDto,
    ExpectedValueSummaryDto,
    ItemSummaryDto,
    ManualValuationEvidenceDto,
    MaterialCostDto,
    MaterialRequirementDto,
    MissingRequirementDto,
    ModifierDto,
    RiskAdjustedDecisionDto,
    ScenarioSummaryDto,
)


def advisor_request_to_domain(
    request: AdvisorAnalyzeRequestDto,
    economy_repository: EconomyRepository,
) -> AdvisorAnalysisRequest:
    as_of = request.as_of or datetime.now(timezone.utc)
    current_valuation = _valuation_from_evidence(
        request.current_valuation_evidence,
        "current",
        request.league,
        economy_repository,
        as_of,
    )
    outcome_valuations = {
        item.outcome_id: valuation
        for item in request.outcome_valuation_evidence
        if (
            valuation := _valuation_from_evidence(
                item.evidence,
                f"outcome:{item.outcome_id}",
                request.league,
                economy_repository,
                as_of,
            )
        )
        is not None
    }
    game_context = (
        GameContext(
            game=request.game_context.game,
            league=request.game_context.league or request.league,
            game_version=request.game_context.game_version,
            locale=request.game_context.locale,
        )
        if request.game_context is not None
        else GameContext(game="Path of Exile 2", league=request.league)
    )
    return AdvisorAnalysisRequest(
        raw_clipboard_text=request.clipboard_text,
        game_context=game_context,
        league=request.league,
        game_data_dataset_version=request.game_data_dataset_version,
        crafting_dataset_version=request.crafting_dataset_version,
        affix_capacity_dataset_version=request.affix_capacity_dataset_version,
        current_valuation=current_valuation,
        outcome_valuations_by_outcome_id=outcome_valuations,
        risk_context=_risk_context(request),
        as_of=as_of,
    )


def advisor_result_to_dto(result: AdvisorAnalysisResult) -> AdvisorAnalyzeResponseDto:
    advisor_status = _advisor_status_by_action(result.raw_advisor_decision)
    return AdvisorAnalyzeResponseDto(
        analysis_id=result.analysis_id,
        status=result.status.value,
        context=AdvisorContextDto(
            league=result.league or "",
            game_data_dataset_version=result.dataset_versions[0] if len(result.dataset_versions) > 0 else "",
            crafting_dataset_version=result.dataset_versions[1] if len(result.dataset_versions) > 1 else "",
            affix_capacity_dataset_version=result.dataset_versions[2] if len(result.dataset_versions) > 2 else "",
            as_of=result.as_of,
            economy_snapshot_ids=list(result.economy_snapshot_ids),
        ),
        item=_item_summary(result),
        enrichment_summary=_enrichment_summary(result.item_enrichment),
        affix_state=_affix_state(result),
        actions=[
            _action_result_to_dto(action_result, advisor_status.get(action_result.action_id))
            for action_result in result.action_results
        ],
        decision=_decision_to_dto(result.raw_advisor_decision),
        risk_adjusted_decision=_risk_decision_to_dto(result.risk_adjusted_decision),
        missing_requirements=[_missing_to_dto(item) for item in result.missing_requirements],
        warnings=list(result.warnings),
        provenance=[to_jsonable(item) for item in result.provenance],
    )


def _valuation_from_evidence(
    evidence: ManualValuationEvidenceDto | None,
    subject_id: str,
    league: str,
    economy_repository: EconomyRepository,
    as_of: datetime,
) -> ValuationResult | None:
    if evidence is None:
        return None
    strategy = ComparableStrategy(evidence.strategy)
    query = ComparableQuery(
        query_id=f"api-manual-query:{subject_id}:{strategy.value.lower()}",
        valuation_subject_id=f"api-valuation-subject:{subject_id}",
        strategy=strategy,
        item_class=None,
        league=league,
        generated_at=as_of,
        warnings=("API manual valuation evidence does not bypass aggregation.",),
    )
    provider = ManualTradeProvider()
    results = tuple(
        provider.result_from_observation(
            ManualListingObservation(
                observation_id=f"{query.query_id}:{index}",
                query_id=query.query_id,
                amount=Decimal(observation.amount),
                currency_asset_id=observation.currency_asset_id,
                league=league,
                observed_at=observation.observed_at or as_of,
                external_listing_id=observation.external_listing_id,
                item_summary=observation.item_summary,
                provenance=(
                    DataProvenance(
                        source_id="api-manual-valuation-evidence",
                        source_type=SourceType.OTHER,
                        retrieved_at=as_of,
                        league=league,
                        notes=observation.notes or evidence.notes,
                    ),
                ),
                warnings=("Manual API observation; listing price is not a realized sale.",),
            ),
            economy_repository,
            as_of,
        )
        for index, observation in enumerate(evidence.observations)
    )
    evidence_set = evidence_set_from_results(query, provider.provider_name, results, ValuationEvidencePolicy())
    return ValuationAggregator().aggregate(evidence_set)


def _risk_context(request: AdvisorAnalyzeRequestDto) -> AdvisorRiskContext | None:
    if request.risk_profile is None and request.bankroll is None:
        return None
    bankroll = None
    if request.bankroll is not None:
        bankroll = EconomicValue(Decimal(request.bankroll.amount), request.bankroll.unit)
        if bankroll.unit != EXALTED_ECONOMIC_UNIT:
            raise ValueError("bankroll must use EXALTED_ECONOMIC_UNIT")
    return AdvisorRiskContext(
        bankroll=bankroll,
        risk_profile=RiskProfile(request.risk_profile or RiskProfile.BALANCED.value),
    )


def _item_summary(result: AdvisorAnalysisResult) -> ItemSummaryDto | None:
    item = result.parsed_item
    if item is None:
        return None
    resolutions = _resolution_by_raw(result.item_enrichment)
    return ItemSummaryDto(
        rarity=item.rarity.value,
        item_name=item.item_name,
        base_type=item.base_type,
        item_class=item.item_class,
        item_level=item.item_level,
        required_level=item.required_level,
        special_states=[state.value for state in item.special_states],
        implicit_modifiers=[_modifier_to_dto(modifier, resolutions) for modifier in item.implicit_modifiers],
        prefixes=[
            _modifier_to_dto(modifier, resolutions)
            for modifier in item.explicit_modifiers
            if modifier.affix_type == AffixType.PREFIX
        ],
        suffixes=[
            _modifier_to_dto(modifier, resolutions)
            for modifier in item.explicit_modifiers
            if modifier.affix_type == AffixType.SUFFIX
        ],
        corruption_enhancements=[
            _modifier_to_dto(modifier, resolutions)
            for modifier in item.special_modifiers
            if modifier.affix_type == AffixType.CORRUPTION_ENHANCEMENT
        ],
        unparsed_lines=list(item.unparsed_lines),
    )


def _modifier_to_dto(
    modifier: ItemModifier,
    resolutions: dict[str, tuple[str, str | None]],
) -> ModifierDto:
    status, canonical_id = resolutions.get(modifier.raw_text, (None, None))
    return ModifierDto(
        display_name=modifier.display_name,
        tier=modifier.tier,
        affix_type=modifier.affix_type.value,
        origin=modifier.origin.value,
        tags=list(modifier.tags),
        raw_text=modifier.raw_text,
        resolution_status=status,
        canonical_id=canonical_id,
    )


def _resolution_by_raw(enrichment: ItemEnrichment | None) -> dict[str, tuple[str, str | None]]:
    if enrichment is None:
        return {}
    return {
        resolution.parsed_modifier.raw_text: (
            resolution.status.value,
            resolution.selected_canonical_modifier_id,
        )
        for resolution in enrichment.modifier_resolutions
    }


def _enrichment_summary(enrichment: ItemEnrichment | None) -> EnrichmentSummaryDto | None:
    if enrichment is None:
        return None
    return EnrichmentSummaryDto(
        enrichment_id=enrichment.enrichment_id,
        snapshot_id=enrichment.snapshot_id,
        resolved_base_id=enrichment.resolved_base_id,
        resolved_modifier_count=sum(1 for item in enrichment.modifier_resolutions if item.status == ResolutionStatus.RESOLVED),
        ambiguous_modifier_count=sum(1 for item in enrichment.modifier_resolutions if item.status == ResolutionStatus.AMBIGUOUS),
        unresolved_modifier_count=sum(1 for item in enrichment.modifier_resolutions if item.status == ResolutionStatus.UNRESOLVED),
        warnings=list(enrichment.warnings),
    )


def _affix_state(result: AdvisorAnalysisResult) -> AffixStateDto | None:
    affix = result.affix_state_resolution
    if affix is None:
        return None
    return AffixStateDto(
        observed_prefix_count=affix.observed_prefix_count,
        observed_suffix_count=affix.observed_suffix_count,
        prefix_capacity=affix.prefix_capacity,
        suffix_capacity=affix.suffix_capacity,
        open_prefix_count=affix.open_prefix_count,
        open_suffix_count=affix.open_suffix_count,
        warnings=list(affix.warnings),
    )


def _action_result_to_dto(action_result, advisor_status: str | None) -> ActionAnalysisDto:
    candidate = action_result.candidate
    outcome_set = action_result.outcome_set
    scenario = action_result.scenario_analysis
    ev = action_result.expected_value_result
    return ActionAnalysisDto(
        action_id=action_result.action_id,
        display_name=candidate.action.display_name,
        applicability=candidate.applicability.status.value,
        applicability_reasons=list(candidate.applicability.reasons),
        failed_preconditions=list(candidate.applicability.failed_preconditions),
        unknown_preconditions=list(candidate.applicability.unknown_preconditions),
        required_materials=[
            MaterialRequirementDto(asset_id=item.asset_id, quantity=str(item.quantity))
            for item in candidate.required_materials
        ],
        material_cost=_material_cost_to_dto(candidate.material_cost),
        outcome_count=len(outcome_set.hypothetical_states) if outcome_set else 0,
        outcome_ids=[state.outcome_id for state in outcome_set.hypothetical_states] if outcome_set else [],
        outcome_space_completeness=outcome_set.outcome_space_completeness.value if outcome_set else None,
        probability_completeness=(
            action_result.probability_model.probability_completeness.value
            if action_result.probability_model
            else None
        ),
        scenario=_scenario_to_dto(scenario),
        expected_value=_ev_to_dto(ev),
        advisor_candidate_status=advisor_status,
        warnings=list(action_result.warnings),
        missing_requirements=[_missing_to_dto(item) for item in action_result.missing_requirements],
    )


def _material_cost_to_dto(cost) -> MaterialCostDto:
    return MaterialCostDto(
        complete=cost.complete,
        total=economic_value_to_dto(cost.total),
        freshness=cost.freshness.value,
        warnings=list(cost.warnings),
        lines=[
            {
                "asset_id": line.asset_id,
                "quantity": str(line.quantity),
                "unit_price": economic_value_to_dto(line.unit_price).model_dump() if line.unit_price else None,
                "subtotal": economic_value_to_dto(line.subtotal).model_dump() if line.subtotal else None,
                "freshness": line.freshness.value,
                "snapshot_id": line.quote.snapshot_id if line.quote else None,
                "warnings": list(line.warnings),
            }
            for line in cost.lines
        ],
    )


def _scenario_to_dto(scenario) -> ScenarioSummaryDto | None:
    if scenario is None:
        return None
    return ScenarioSummaryDto(
        readiness=scenario.decision_readiness.value,
        outcome_count=scenario.outcome_count,
        valued_outcome_count=scenario.valued_outcome_count,
        unvalued_outcome_count=scenario.unvalued_outcome_count,
        valuation_completeness=scenario.valuation_completeness.value,
        best_valuated_outcome=economic_value_to_dto(scenario.best_valuated_outcome.gross_value) if scenario.best_valuated_outcome else None,
        worst_valuated_outcome=economic_value_to_dto(scenario.worst_valuated_outcome.gross_value) if scenario.worst_valuated_outcome else None,
        median_valuated_outcome=economic_value_to_dto(scenario.median_valuated_outcome),
        upside_relative_to_current=economic_value_to_dto(scenario.upside_relative_to_current),
        downside_relative_to_current=economic_value_to_dto(scenario.downside_relative_to_current),
        reasons=list(scenario.reasons),
    )


def _ev_to_dto(ev) -> ExpectedValueSummaryDto | None:
    if ev is None:
        return None
    return ExpectedValueSummaryDto(
        available=ev.available,
        status=ev.status.value,
        gross_expected_outcome_value=economic_value_to_dto(ev.gross_expected_outcome_value),
        craft_cost=economic_value_to_dto(ev.craft_cost),
        net_expected_value=economic_value_to_dto(ev.net_expected_value),
        current_item_value=economic_value_to_dto(ev.current_item_value),
        expected_gain_vs_sell_now=economic_value_to_dto(ev.expected_gain_vs_sell_now),
        roi_on_craft_cost=str(ev.roi_on_craft_cost) if ev.roi_on_craft_cost is not None else None,
        unavailable_reasons=list(ev.unavailable_reasons),
        algorithm_version=ev.methodology_version,
    )


def _decision_to_dto(decision: AdvisorDecision | None) -> AdvisorDecisionDto | None:
    if decision is None:
        return None
    return AdvisorDecisionDto(
        decision_type=decision.decision_type.value,
        selected_candidate_id=decision.selected_candidate_id,
        reasons=list(decision.decision_reasons),
        warnings=list(decision.warnings),
        algorithm_version=decision.algorithm_version,
    )


def _risk_decision_to_dto(decision) -> RiskAdjustedDecisionDto | None:
    if decision is None:
        return None
    return RiskAdjustedDecisionDto(
        decision_type=decision.risk_adjusted_decision_type.value,
        raw_winner_candidate_id=decision.raw_winner_candidate_id,
        selected_candidate_id=decision.selected_candidate_id,
        changed_by_policy=decision.risk_policy_changed_outcome,
        risk_policy_version=decision.risk_policy_version,
        reasons=list(decision.decision_reasons),
        triggered_rules=sorted(
            {
                rule
                for candidate in decision.risk_adjusted_candidates
                for rule in candidate.risk_assessment.triggered_policy_rules
            }
        ),
    )


def _missing_to_dto(requirement) -> MissingRequirementDto:
    return MissingRequirementDto(
        type=requirement.kind.value,
        action_id=requirement.affected_action_id,
        blocks=[part for part in requirement.blocks.replace("/", ",").split(",") if part],
        reason=requirement.reason,
    )


def _advisor_status_by_action(decision: AdvisorDecision | None) -> dict[str, str]:
    if decision is None:
        return {}
    return {
        candidate.action_id: candidate.status.value
        for candidate in decision.craft_candidates
        if candidate.action_id is not None
    }
