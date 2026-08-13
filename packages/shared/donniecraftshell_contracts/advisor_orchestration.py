"""Framework-independent Craft Advisor orchestration service."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Mapping

from .advisor_decision import AdvisorCraftInput, AdvisorDecision, AdvisorDecisionEngine
from .advisor_risk import AdvisorRiskContext, AdvisorRiskPolicyEngine, RiskAdjustedAdvisorDecision
from .affix_capacity import AffixStateResolver, AffixStateResolution
from .craft_action_candidates import CraftActionCandidate, get_action_candidates
from .craft_outcomes import CraftOutcomeEngine, CraftOutcomeSet
from .crafting_actions import CraftActionEngine, CraftApplicabilityStatus
from .domain import DataProvenance, GameContext, ParsedItem, Rarity
from .economy_repository import EconomyRepository
from .expected_value import ExpectedValueEngine, ExpectedValueResult
from .game_data import ItemEnrichment
from .game_data_repository import GameDataRepository
from .modifier_resolver import enrich_item
from .parser import ParseResult, parse_clipboard_item
from .probability import CurrentResearchProbabilityProvider, OutcomeProbabilityModel, ProbabilityContext, ProbabilityProvider
from .scenario_analysis import OutcomeValuation, ScenarioAnalysis, ScenarioAnalysisService
from .valuation import ValuationResult


class AdvisorAnalysisStatus(str, Enum):
    PARSE_FAILED = "PARSE_FAILED"
    UNSUPPORTED_ITEM = "UNSUPPORTED_ITEM"
    ANALYSIS_PARTIAL = "ANALYSIS_PARTIAL"
    SCENARIO_READY = "SCENARIO_READY"
    EV_READY = "EV_READY"
    DECISION_READY = "DECISION_READY"


class MissingRequirementKind(str, Enum):
    CURRENT_VALUATION_EVIDENCE_REQUIRED = "CURRENT_VALUATION_EVIDENCE_REQUIRED"
    OUTCOME_VALUATION_EVIDENCE_REQUIRED = "OUTCOME_VALUATION_EVIDENCE_REQUIRED"
    PROBABILITY_EVIDENCE_REQUIRED = "PROBABILITY_EVIDENCE_REQUIRED"
    ECONOMY_QUOTE_REQUIRED = "ECONOMY_QUOTE_REQUIRED"
    VERIFIED_MECHANIC_REQUIRED = "VERIFIED_MECHANIC_REQUIRED"


@dataclass(frozen=True)
class MissingAnalysisRequirement:
    kind: MissingRequirementKind
    affected_action_id: str | None
    reason: str
    blocks: str


@dataclass(frozen=True)
class AdvisorAnalysisRequest:
    raw_clipboard_text: str
    game_context: GameContext | None
    league: str
    game_data_dataset_version: str
    crafting_dataset_version: str
    affix_capacity_dataset_version: str
    empirical_probability_dataset_version: str | None = None
    current_valuation: ValuationResult | None = None
    outcome_valuations_by_outcome_id: Mapping[str, ValuationResult] | None = None
    risk_context: AdvisorRiskContext | None = None
    as_of: datetime | None = None

    def __post_init__(self) -> None:
        if not self.league:
            raise ValueError("league is required")
        if not self.game_data_dataset_version:
            raise ValueError("game_data_dataset_version is required")
        if not self.crafting_dataset_version:
            raise ValueError("crafting_dataset_version is required")
        if not self.affix_capacity_dataset_version:
            raise ValueError("affix_capacity_dataset_version is required")


@dataclass(frozen=True)
class ActionAnalysisResult:
    action_id: str
    candidate: CraftActionCandidate
    outcome_set: CraftOutcomeSet | None = None
    probability_model: OutcomeProbabilityModel | None = None
    scenario_analysis: ScenarioAnalysis | None = None
    expected_value_result: ExpectedValueResult | None = None
    missing_requirements: tuple[MissingAnalysisRequirement, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class AdvisorAnalysisResult:
    analysis_id: str
    status: AdvisorAnalysisStatus
    parse_result: ParseResult
    parsed_item: ParsedItem | None = None
    item_enrichment: ItemEnrichment | None = None
    affix_state_resolution: AffixStateResolution | None = None
    action_results: tuple[ActionAnalysisResult, ...] = ()
    raw_advisor_decision: AdvisorDecision | None = None
    risk_adjusted_decision: RiskAdjustedAdvisorDecision | None = None
    missing_requirements: tuple[MissingAnalysisRequirement, ...] = ()
    warnings: tuple[str, ...] = ()
    dataset_versions: tuple[str, ...] = ()
    economy_snapshot_ids: tuple[str, ...] = ()
    probability_model_ids: tuple[str, ...] = ()
    valuation_evidence_ids: tuple[str, ...] = ()
    league: str | None = None
    as_of: datetime | None = None
    provenance: tuple[DataProvenance, ...] = ()


class CraftAdvisorOrchestrator:
    def __init__(
        self,
        game_data_repository: GameDataRepository,
        affix_state_resolver: AffixStateResolver,
        craft_action_engine: CraftActionEngine,
        economy_repository: EconomyRepository,
        outcome_engine: CraftOutcomeEngine | None = None,
        probability_provider: ProbabilityProvider | None = None,
        scenario_service: ScenarioAnalysisService | None = None,
        expected_value_engine: ExpectedValueEngine | None = None,
        advisor_decision_engine: AdvisorDecisionEngine | None = None,
        risk_policy_engine: AdvisorRiskPolicyEngine | None = None,
        parser=parse_clipboard_item,
    ):
        self.game_data_repository = game_data_repository
        self.affix_state_resolver = affix_state_resolver
        self.craft_action_engine = craft_action_engine
        self.economy_repository = economy_repository
        self.outcome_engine = outcome_engine or CraftOutcomeEngine()
        self.probability_provider = probability_provider or CurrentResearchProbabilityProvider()
        self.scenario_service = scenario_service or ScenarioAnalysisService()
        self.expected_value_engine = expected_value_engine or ExpectedValueEngine()
        self.advisor_decision_engine = advisor_decision_engine or AdvisorDecisionEngine()
        self.risk_policy_engine = risk_policy_engine or AdvisorRiskPolicyEngine()
        self.parser = parser or parse_clipboard_item

    def analyze(self, request: AdvisorAnalysisRequest) -> AdvisorAnalysisResult:
        as_of = request.as_of or datetime.now(timezone.utc)
        analysis_id = _analysis_id()
        parse_result = self.parser(request.raw_clipboard_text, request.game_context)
        if parse_result.item is None:
            return AdvisorAnalysisResult(
                analysis_id=analysis_id,
                status=AdvisorAnalysisStatus.PARSE_FAILED,
                parse_result=parse_result,
                warnings=parse_result.warnings,
                missing_requirements=(),
                dataset_versions=_dataset_versions(request),
                league=request.league,
                as_of=as_of,
            )
        item = parse_result.item
        if item.item_class != "Quivers" or item.rarity != Rarity.RARE:
            return AdvisorAnalysisResult(
                analysis_id=analysis_id,
                status=AdvisorAnalysisStatus.UNSUPPORTED_ITEM,
                parse_result=parse_result,
                parsed_item=item,
                warnings=("Craft Advisor MVP supports only Rare Quivers.",),
                dataset_versions=_dataset_versions(request),
                league=request.league,
                as_of=as_of,
            )

        enrichment = enrich_item(item, self.game_data_repository, request.game_data_dataset_version)
        affix_state = self.affix_state_resolver.resolve(item)
        candidates = get_action_candidates(
            item,
            affix_state,
            self.craft_action_engine,
            self.economy_repository,
            request.league,
            as_of,
        )
        action_results = tuple(
            self._safe_analyze_action(item, affix_state, candidate, request, as_of)
            for candidate in candidates
        )
        craft_inputs = tuple(
            AdvisorCraftInput(
                result.candidate,
                result.scenario_analysis,
                result.expected_value_result,
            )
            for result in action_results
        )
        raw_decision = self.advisor_decision_engine.decide(
            request.current_valuation,
            craft_inputs,
            generated_at=as_of,
        )
        risk_decision = (
            self.risk_policy_engine.apply(raw_decision, request.risk_context, as_of)
            if request.risk_context is not None
            else None
        )
        missing = _top_level_missing_requirements(request, action_results)
        status = _overall_status(action_results, raw_decision, request.current_valuation)
        return AdvisorAnalysisResult(
            analysis_id=analysis_id,
            status=status,
            parse_result=parse_result,
            parsed_item=item,
            item_enrichment=enrichment,
            affix_state_resolution=affix_state,
            action_results=action_results,
            raw_advisor_decision=raw_decision,
            risk_adjusted_decision=risk_decision,
            missing_requirements=missing,
            warnings=_warnings(parse_result, enrichment, action_results, raw_decision),
            dataset_versions=_dataset_versions(request),
            economy_snapshot_ids=_economy_snapshot_ids(action_results, raw_decision),
            probability_model_ids=tuple(
                result.probability_model.source_outcome_set_id
                for result in action_results
                if result.probability_model is not None
            ),
            valuation_evidence_ids=_valuation_evidence_ids(request, action_results),
            league=request.league,
            as_of=as_of,
            provenance=item.provenance,
        )

    def _safe_analyze_action(
        self,
        item: ParsedItem,
        affix_state: AffixStateResolution,
        candidate: CraftActionCandidate,
        request: AdvisorAnalysisRequest,
        as_of: datetime,
    ) -> ActionAnalysisResult:
        try:
            return self._analyze_action(item, affix_state, candidate, request, as_of)
        except Exception as exc:
            message = f"Action analysis failed for {candidate.action.action_id}: {exc}"
            return ActionAnalysisResult(
                action_id=candidate.action.action_id,
                candidate=candidate,
                missing_requirements=(
                    MissingAnalysisRequirement(
                        MissingRequirementKind.VERIFIED_MECHANIC_REQUIRED,
                        candidate.action.action_id,
                        message,
                        "Action analysis",
                    ),
                ),
                warnings=(message,),
            )

    def _analyze_action(
        self,
        item: ParsedItem,
        affix_state: AffixStateResolution,
        candidate: CraftActionCandidate,
        request: AdvisorAnalysisRequest,
        as_of: datetime,
    ) -> ActionAnalysisResult:
        missing = list(_cost_missing(candidate))
        if candidate.applicability.status == CraftApplicabilityStatus.NOT_APPLICABLE:
            return ActionAnalysisResult(
                action_id=candidate.action.action_id,
                candidate=candidate,
                missing_requirements=tuple(missing),
                warnings=candidate.warnings,
            )
        outcome_set = self.outcome_engine.enumerate_outcomes(
            item,
            affix_state,
            candidate.action,
            candidate.applicability,
            self.game_data_repository,
            request.game_data_dataset_version,
        )
        probability_model = self.probability_provider.get_probability_model(
            item,
            outcome_set,
            ProbabilityContext(
                crafting_dataset_version=request.crafting_dataset_version,
                modifier_dataset_version=request.game_data_dataset_version,
                evidence_dataset_version=request.empirical_probability_dataset_version,
                game_version=request.game_context.game_version if request.game_context is not None else None,
                league=request.league,
            ),
        )
        if (
            probability_model.probability_completeness.value != "COMPLETE"
            or any(probability.probability is None for probability in probability_model.outcome_probabilities)
        ):
            missing.append(
                MissingAnalysisRequirement(
                    MissingRequirementKind.PROBABILITY_EVIDENCE_REQUIRED,
                    candidate.action.action_id,
                    f"Outcome probability model is {probability_model.probability_completeness.value}.",
                    "Expected Value",
                )
            )
        outcome_valuations = _outcome_valuations(outcome_set, request.outcome_valuations_by_outcome_id or {})
        if len(outcome_valuations) < len(outcome_set.hypothetical_states):
            missing.append(
                MissingAnalysisRequirement(
                    MissingRequirementKind.OUTCOME_VALUATION_EVIDENCE_REQUIRED,
                    candidate.action.action_id,
                    f"Outcome valuation coverage is {len(outcome_valuations)}/{len(outcome_set.hypothetical_states)}.",
                    "Scenario/Expected Value",
                )
            )
        scenario = self.scenario_service.analyze_action(
            request.current_valuation,
            candidate,
            outcome_set,
            probability_model,
            outcome_valuations,
            as_of,
        )
        ev = self.expected_value_engine.calculate(scenario, probability_model, outcome_valuations, as_of)
        if not ev.available:
            missing.extend(
                MissingAnalysisRequirement(
                    MissingRequirementKind.VERIFIED_MECHANIC_REQUIRED,
                    candidate.action.action_id,
                    reason,
                    "Expected Value",
                )
                for reason in ev.unavailable_reasons
                if "Probability" not in reason
                and "valuation" not in reason.lower()
                and "cost" not in reason.lower()
                and "ScenarioAnalysis" not in reason
            )
        return ActionAnalysisResult(
            action_id=candidate.action.action_id,
            candidate=candidate,
            outcome_set=outcome_set,
            probability_model=probability_model,
            scenario_analysis=scenario,
            expected_value_result=ev,
            missing_requirements=tuple(missing),
            warnings=(*candidate.warnings, *outcome_set.warnings, *probability_model.warnings, *scenario.warnings, *ev.warnings),
        )


def _analysis_id() -> str:
    if not hasattr(uuid, "uuid7"):
        raise RuntimeError("DonnieCraftShell requires Python with stdlib uuid.uuid7 support.")
    return f"advisor-analysis-{uuid.uuid7()}"


def _dataset_versions(request: AdvisorAnalysisRequest) -> tuple[str, ...]:
    return (
        request.game_data_dataset_version,
        request.crafting_dataset_version,
        request.affix_capacity_dataset_version,
        *( (request.empirical_probability_dataset_version,) if request.empirical_probability_dataset_version else () ),
    )


def _cost_missing(candidate: CraftActionCandidate) -> tuple[MissingAnalysisRequirement, ...]:
    if candidate.material_cost.complete:
        return ()
    return tuple(
        MissingAnalysisRequirement(
            MissingRequirementKind.ECONOMY_QUOTE_REQUIRED,
            candidate.action.action_id,
            warning,
            "Craft material cost/Expected Value",
        )
        for warning in candidate.material_cost.warnings
    )


def _outcome_valuations(
    outcome_set: CraftOutcomeSet,
    supplied: Mapping[str, ValuationResult],
) -> tuple[OutcomeValuation, ...]:
    return tuple(
        OutcomeValuation(state.outcome_id, supplied[state.outcome_id])
        for state in outcome_set.hypothetical_states
        if state.outcome_id in supplied
    )


def _top_level_missing_requirements(
    request: AdvisorAnalysisRequest,
    action_results: tuple[ActionAnalysisResult, ...],
) -> tuple[MissingAnalysisRequirement, ...]:
    missing = []
    if request.current_valuation is None:
        missing.append(
            MissingAnalysisRequirement(
                MissingRequirementKind.CURRENT_VALUATION_EVIDENCE_REQUIRED,
                None,
                "Current item valuation evidence is required for SELL NOW baseline.",
                "Advisor decision",
            )
        )
    for result in action_results:
        missing.extend(result.missing_requirements)
    return tuple(missing)


def _overall_status(
    action_results: tuple[ActionAnalysisResult, ...],
    raw_decision: AdvisorDecision,
    current_valuation: ValuationResult | None,
) -> AdvisorAnalysisStatus:
    if raw_decision.decision_type.value != "NO_RECOMMENDATION":
        return AdvisorAnalysisStatus.DECISION_READY
    if any(result.expected_value_result is not None and result.expected_value_result.available for result in action_results):
        return AdvisorAnalysisStatus.EV_READY
    if any(result.scenario_analysis is not None and result.scenario_analysis.valued_outcome_count > 0 for result in action_results):
        return AdvisorAnalysisStatus.SCENARIO_READY
    return AdvisorAnalysisStatus.ANALYSIS_PARTIAL if current_valuation or action_results else AdvisorAnalysisStatus.ANALYSIS_PARTIAL


def _warnings(
    parse_result: ParseResult,
    enrichment: ItemEnrichment,
    action_results: tuple[ActionAnalysisResult, ...],
    raw_decision: AdvisorDecision,
) -> tuple[str, ...]:
    warnings = list(parse_result.warnings)
    warnings.extend(enrichment.warnings)
    for result in action_results:
        warnings.extend(result.warnings)
    warnings.extend(raw_decision.warnings)
    return tuple(warnings)


def _economy_snapshot_ids(
    action_results: tuple[ActionAnalysisResult, ...],
    raw_decision: AdvisorDecision,
) -> tuple[str, ...]:
    ids = set(raw_decision.economy_snapshot_ids)
    for result in action_results:
        for line in result.candidate.material_cost.lines:
            if line.quote is not None:
                ids.add(line.quote.snapshot_id)
        if result.expected_value_result is not None:
            ids.update(result.expected_value_result.economy_snapshot_ids)
    return tuple(sorted(ids))


def _valuation_evidence_ids(
    request: AdvisorAnalysisRequest,
    action_results: tuple[ActionAnalysisResult, ...],
) -> tuple[str, ...]:
    ids = set(request.current_valuation.source_evidence_ids if request.current_valuation else ())
    for result in action_results:
        if result.scenario_analysis is not None:
            ids.update(result.scenario_analysis.valuation_evidence_ids)
    return tuple(sorted(ids))
