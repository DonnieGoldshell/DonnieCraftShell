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


class EvidenceReadinessCategory(str, Enum):
    CURRENT_ITEM_VALUATION = "CURRENT_ITEM_VALUATION"
    ECONOMY_CRAFTING_COST = "ECONOMY_CRAFTING_COST"
    PROBABILITY = "PROBABILITY"
    OUTCOME_VALUATION = "OUTCOME_VALUATION"
    VERIFIED_MECHANICS = "VERIFIED_MECHANICS"


class EvidenceReadinessStatus(str, Enum):
    READY = "READY"
    PARTIAL = "PARTIAL"
    MISSING = "MISSING"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class MissingAnalysisRequirement:
    kind: MissingRequirementKind
    affected_action_id: str | None
    reason: str
    blocks: str


@dataclass(frozen=True)
class EvidenceReadinessTarget:
    target_type: str
    target_id: str
    reason: str
    action_id: str | None = None
    action_display_name: str | None = None
    asset_id: str | None = None
    outcome_ids: tuple[str, ...] = ()
    blocks: tuple[str, ...] = ()


@dataclass(frozen=True)
class EvidenceReadinessItem:
    category: EvidenceReadinessCategory
    label: str
    status: EvidenceReadinessStatus
    summary: str
    targets: tuple[EvidenceReadinessTarget, ...] = ()
    evidence_tool: str | None = None
    diagnostics: tuple[MissingAnalysisRequirement, ...] = ()


@dataclass(frozen=True)
class AdvisorEvidenceReadiness:
    items: tuple[EvidenceReadinessItem, ...]
    warnings: tuple[str, ...] = ()


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
    evidence_readiness: AdvisorEvidenceReadiness | None = None
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

    def with_economy_repository(self, economy_repository: EconomyRepository) -> "CraftAdvisorOrchestrator":
        """Return an equivalent orchestrator using a request-scoped economy repository."""
        return CraftAdvisorOrchestrator(
            game_data_repository=self.game_data_repository,
            affix_state_resolver=self.affix_state_resolver,
            craft_action_engine=self.craft_action_engine,
            economy_repository=economy_repository,
            outcome_engine=self.outcome_engine,
            probability_provider=self.probability_provider,
            scenario_service=self.scenario_service,
            expected_value_engine=self.expected_value_engine,
            advisor_decision_engine=self.advisor_decision_engine,
            risk_policy_engine=self.risk_policy_engine,
            parser=self.parser,
        )

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
        evidence_readiness = _evidence_readiness(request, action_results, missing)
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
            evidence_readiness=evidence_readiness,
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
        if candidate.applicability.status == CraftApplicabilityStatus.NOT_APPLICABLE:
            return ActionAnalysisResult(
                action_id=candidate.action.action_id,
                candidate=candidate,
                warnings=candidate.warnings,
            )
        missing = list(_cost_missing(candidate))
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


def _evidence_readiness(
    request: AdvisorAnalysisRequest,
    action_results: tuple[ActionAnalysisResult, ...],
    missing_requirements: tuple[MissingAnalysisRequirement, ...],
) -> AdvisorEvidenceReadiness:
    return AdvisorEvidenceReadiness(
        items=(
            _current_valuation_readiness(request, missing_requirements),
            _economy_readiness(action_results, missing_requirements),
            _probability_readiness(action_results, missing_requirements),
            _outcome_valuation_readiness(request, action_results, missing_requirements),
            _verified_mechanics_readiness(action_results, missing_requirements),
        ),
        warnings=(
            "Evidence readiness is derived from explicit Advisor inputs, action analysis, and missing requirements; it does not fabricate confidence or recommendation eligibility.",
        ),
    )


def _current_valuation_readiness(
    request: AdvisorAnalysisRequest,
    missing_requirements: tuple[MissingAnalysisRequirement, ...],
) -> EvidenceReadinessItem:
    diagnostics = _requirements_for(missing_requirements, MissingRequirementKind.CURRENT_VALUATION_EVIDENCE_REQUIRED)
    if request.current_valuation is None:
        return EvidenceReadinessItem(
            category=EvidenceReadinessCategory.CURRENT_ITEM_VALUATION,
            label="Current item valuation",
            status=EvidenceReadinessStatus.MISSING,
            summary="Manual comparable listing evidence is needed for the SELL NOW baseline.",
            targets=(
                EvidenceReadinessTarget(
                    target_type="CURRENT_ITEM",
                    target_id="current",
                    reason="Current item valuation evidence is missing.",
                    blocks=_blocks_for(diagnostics),
                ),
            ),
            evidence_tool="manual-current-valuation",
            diagnostics=diagnostics,
        )
    status = (
        EvidenceReadinessStatus.READY
        if request.current_valuation.readiness.value == "READY"
        else EvidenceReadinessStatus.PARTIAL
        if request.current_valuation.readiness.value == "PARTIAL"
        else EvidenceReadinessStatus.MISSING
    )
    return EvidenceReadinessItem(
        category=EvidenceReadinessCategory.CURRENT_ITEM_VALUATION,
        label="Current item valuation",
        status=status,
        summary=f"Current item valuation evidence is {request.current_valuation.readiness.value}.",
        evidence_tool="manual-current-valuation",
        diagnostics=diagnostics,
    )


def _economy_readiness(
    action_results: tuple[ActionAnalysisResult, ...],
    missing_requirements: tuple[MissingAnalysisRequirement, ...],
) -> EvidenceReadinessItem:
    diagnostics = _requirements_for(missing_requirements, MissingRequirementKind.ECONOMY_QUOTE_REQUIRED)
    diagnostics_by_action = _requirements_by_action(diagnostics)
    action_by_id = {result.action_id: result for result in action_results}
    targets: list[EvidenceReadinessTarget] = []
    seen: set[tuple[str, str | None]] = set()
    for action_id, action_diagnostics in diagnostics_by_action.items():
        result = action_by_id.get(action_id)
        if result is None:
            targets.append(
                EvidenceReadinessTarget(
                    target_type="ECONOMY_REQUIREMENT",
                    target_id=action_id or "global",
                    action_id=action_id,
                    action_display_name=_action_display_name(action_results, action_id),
                    reason=action_diagnostics[0].reason,
                    blocks=_blocks_for(action_diagnostics),
                )
            )
            continue
        for line in result.candidate.material_cost.lines:
            if line.quote is not None and line.unit_price is not None and line.subtotal is not None:
                continue
            key = (line.asset_id, result.action_id)
            if key in seen:
                continue
            seen.add(key)
            targets.append(
                EvidenceReadinessTarget(
                    target_type="ECONOMY_ASSET",
                    target_id=line.asset_id,
                    action_id=result.action_id,
                    action_display_name=result.candidate.action.display_name,
                    asset_id=line.asset_id,
                    reason=f"Missing economy quote for {_display_asset(line.asset_id)}.",
                    blocks=_blocks_for(action_diagnostics),
                )
            )
        if not any(target.action_id == action_id for target in targets):
            targets.append(
                EvidenceReadinessTarget(
                    target_type="ECONOMY_REQUIREMENT",
                    target_id=action_id or "global",
                    action_id=action_id,
                    action_display_name=_action_display_name(action_results, action_id),
                    reason=action_diagnostics[0].reason,
                    blocks=_blocks_for(action_diagnostics),
                )
            )
    status = EvidenceReadinessStatus.MISSING if targets else EvidenceReadinessStatus.READY if action_results else EvidenceReadinessStatus.UNKNOWN
    summary = (
        f"{len(targets)} crafting material price target{' is' if len(targets) == 1 else 's are'} missing."
        if targets
        else "Required crafting material prices are available for analyzed actions."
        if action_results
        else "No action cost evidence was analyzed."
    )
    return EvidenceReadinessItem(
        category=EvidenceReadinessCategory.ECONOMY_CRAFTING_COST,
        label="Economy prices",
        status=status,
        summary=summary,
        targets=tuple(targets),
        evidence_tool="local-economy-quotes",
        diagnostics=diagnostics,
    )


def _probability_readiness(
    action_results: tuple[ActionAnalysisResult, ...],
    missing_requirements: tuple[MissingAnalysisRequirement, ...],
) -> EvidenceReadinessItem:
    diagnostics = _requirements_for(missing_requirements, MissingRequirementKind.PROBABILITY_EVIDENCE_REQUIRED)
    diagnostics_by_action = _requirements_by_action(diagnostics)
    action_by_id = {result.action_id: result for result in action_results}
    targets: list[EvidenceReadinessTarget] = []
    for action_id, action_diagnostics in diagnostics_by_action.items():
        result = action_by_id.get(action_id)
        model = result.probability_model if result is not None else None
        display_name = result.candidate.action.display_name if result is not None else _action_display_name(action_results, action_id)
        if model is None:
            targets.append(
                EvidenceReadinessTarget(
                    target_type="ACTION_PROBABILITY_MODEL",
                    target_id=action_id or "global",
                    action_id=action_id,
                    action_display_name=display_name,
                    reason=action_diagnostics[0].reason,
                    blocks=_blocks_for(action_diagnostics),
                )
            )
            continue
        missing_outcomes = tuple(item.outcome_id for item in model.outcome_probabilities if item.probability is None)
        targets.append(
            EvidenceReadinessTarget(
                target_type="ACTION_PROBABILITY_MODEL",
                target_id=model.source_outcome_set_id,
                action_id=action_id,
                action_display_name=display_name,
                outcome_ids=missing_outcomes,
                reason=(
                    f"{display_name or action_id or 'Action'} probability model is {model.probability_completeness.value}"
                    f" with {len(missing_outcomes)} unknown outcome probabilities."
                ),
                blocks=_blocks_for(action_diagnostics),
            )
        )
    status = EvidenceReadinessStatus.MISSING if targets else EvidenceReadinessStatus.READY if action_results else EvidenceReadinessStatus.UNKNOWN
    summary = (
        f"{len(targets)} action probability model{' needs' if len(targets) == 1 else 's need'} evidence."
        if targets
        else "Probability evidence is complete for analyzed outcome sets."
        if action_results
        else "No outcome probability evidence was analyzed."
    )
    return EvidenceReadinessItem(
        category=EvidenceReadinessCategory.PROBABILITY,
        label="Probability evidence",
        status=status,
        summary=summary,
        targets=tuple(targets),
        evidence_tool="observation-recorder-review-import",
        diagnostics=diagnostics,
    )


def _outcome_valuation_readiness(
    request: AdvisorAnalysisRequest,
    action_results: tuple[ActionAnalysisResult, ...],
    missing_requirements: tuple[MissingAnalysisRequirement, ...],
) -> EvidenceReadinessItem:
    diagnostics = _requirements_for(missing_requirements, MissingRequirementKind.OUTCOME_VALUATION_EVIDENCE_REQUIRED)
    diagnostics_by_action = _requirements_by_action(diagnostics)
    action_by_id = {result.action_id: result for result in action_results}
    supplied = request.outcome_valuations_by_outcome_id or {}
    targets: list[EvidenceReadinessTarget] = []
    any_outcomes = False
    any_valued = bool(supplied)
    for result in action_results:
        if result.outcome_set is not None:
            any_outcomes = any_outcomes or bool(result.outcome_set.hypothetical_states)
    for action_id, action_diagnostics in diagnostics_by_action.items():
        result = action_by_id.get(action_id)
        if result is None or result.outcome_set is None:
            targets.append(
                EvidenceReadinessTarget(
                    target_type="OUTCOME_VALUATION",
                    target_id=action_id or "global",
                    action_id=action_id,
                    action_display_name=_action_display_name(action_results, action_id),
                    reason=action_diagnostics[0].reason,
                    blocks=_blocks_for(action_diagnostics),
                )
            )
            continue
        outcome_ids = tuple(state.outcome_id for state in result.outcome_set.hypothetical_states)
        missing_outcomes = tuple(outcome_id for outcome_id in outcome_ids if outcome_id not in supplied)
        any_valued = any_valued or len(missing_outcomes) < len(outcome_ids)
        targets.append(
            EvidenceReadinessTarget(
                target_type="OUTCOME_VALUATION",
                target_id=action_id or "global",
                action_id=action_id,
                action_display_name=result.candidate.action.display_name,
                outcome_ids=missing_outcomes,
                reason=(
                    f"{result.candidate.action.display_name} has valuation coverage "
                    f"{len(outcome_ids) - len(missing_outcomes)}/{len(outcome_ids)}."
                ),
                blocks=_blocks_for(action_diagnostics),
            )
        )
    if targets and any_valued:
        status = EvidenceReadinessStatus.PARTIAL
    elif targets:
        status = EvidenceReadinessStatus.MISSING
    elif any_outcomes:
        status = EvidenceReadinessStatus.READY
    else:
        status = EvidenceReadinessStatus.UNKNOWN
    summary = (
        f"{len(targets)} action outcome set{' has' if len(targets) == 1 else 's have'} missing outcome valuations."
        if targets
        else "Outcome valuation evidence covers analyzed outcome sets."
        if any_outcomes
        else "No outcome valuation targets were available."
    )
    return EvidenceReadinessItem(
        category=EvidenceReadinessCategory.OUTCOME_VALUATION,
        label="Outcome valuation",
        status=status,
        summary=summary,
        targets=tuple(targets),
        evidence_tool="manual-outcome-valuation",
        diagnostics=diagnostics,
    )


def _verified_mechanics_readiness(
    action_results: tuple[ActionAnalysisResult, ...],
    missing_requirements: tuple[MissingAnalysisRequirement, ...],
) -> EvidenceReadinessItem:
    diagnostics = _requirements_for(missing_requirements, MissingRequirementKind.VERIFIED_MECHANIC_REQUIRED)
    targets = tuple(
        EvidenceReadinessTarget(
            target_type="VERIFIED_MECHANIC",
            target_id=f"{requirement.affected_action_id or 'global'}:{index}",
            action_id=requirement.affected_action_id,
            action_display_name=_action_display_name(action_results, requirement.affected_action_id),
            reason=requirement.reason,
            blocks=_split_blocks(requirement.blocks),
        )
        for index, requirement in enumerate(diagnostics)
    )
    status = EvidenceReadinessStatus.MISSING if targets else EvidenceReadinessStatus.READY if action_results else EvidenceReadinessStatus.UNKNOWN
    summary = (
        f"{len(targets)} verified mechanic question{' remains' if len(targets) == 1 else 's remain'}."
        if targets
        else "No verified mechanic blockers were reported for analyzed actions."
        if action_results
        else "No mechanic evidence was analyzed."
    )
    return EvidenceReadinessItem(
        category=EvidenceReadinessCategory.VERIFIED_MECHANICS,
        label="Verified mechanics",
        status=status,
        summary=summary,
        targets=targets,
        evidence_tool="mechanic-research",
        diagnostics=diagnostics,
    )


def _requirements_for(
    requirements: tuple[MissingAnalysisRequirement, ...],
    kind: MissingRequirementKind,
) -> tuple[MissingAnalysisRequirement, ...]:
    return tuple(requirement for requirement in requirements if requirement.kind == kind)


def _requirements_by_action(
    requirements: tuple[MissingAnalysisRequirement, ...],
) -> dict[str | None, tuple[MissingAnalysisRequirement, ...]]:
    grouped: dict[str | None, list[MissingAnalysisRequirement]] = {}
    for requirement in requirements:
        grouped.setdefault(requirement.affected_action_id, []).append(requirement)
    return {action_id: tuple(items) for action_id, items in grouped.items()}


def _blocks_for(requirements: tuple[MissingAnalysisRequirement, ...]) -> tuple[str, ...]:
    return tuple(sorted({block for requirement in requirements for block in _split_blocks(requirement.blocks)}))


def _split_blocks(blocks: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in blocks.replace("/", ",").split(",") if part.strip())


def _action_display_name(action_results: tuple[ActionAnalysisResult, ...], action_id: str | None) -> str | None:
    if action_id is None:
        return None
    for result in action_results:
        if result.action_id == action_id:
            return result.candidate.action.display_name
    return None


def _display_asset(asset_id: str) -> str:
    name = asset_id.rsplit(":", 1)[-1].replace("-", " ")
    return name.title()


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
