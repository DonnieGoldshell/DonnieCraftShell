"""Craft outcome-space contracts and enumeration.

This module models mechanically possible outcome states. It intentionally does
not assign probabilities, calculate valuation, EV, ROI, or recommendations.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import Enum

from .affix_capacity import AffixStateResolution, SlotScope
from .crafting_actions import CraftActionApplicability, CraftActionDefinition, CraftApplicabilityStatus
from .domain import AffixType, DataProvenance, ItemModifier, ModifierOrigin, ParsedItem
from .game_data import ModifierFamily, ModifierTierDefinition
from .game_data_repository import GameDataRepository


class CraftOutcomeOperation(str, Enum):
    ADD_MODIFIER = "ADD_MODIFIER"
    REMOVE_MODIFIER = "REMOVE_MODIFIER"
    ADD_MULTIPLE_MODIFIERS = "ADD_MULTIPLE_MODIFIERS"
    REMOVE_MULTIPLE_MODIFIERS = "REMOVE_MULTIPLE_MODIFIERS"
    REPLACE_MODIFIER = "REPLACE_MODIFIER"
    GUARANTEE_MODIFIER = "GUARANTEE_MODIFIER"
    MODIFY_SELECTION_RULE = "MODIFY_SELECTION_RULE"
    OTHER = "OTHER"


class OutcomeSelectionRule(str, Enum):
    ANY_ELIGIBLE_EXPLICIT_MODIFIER = "ANY_ELIGIBLE_EXPLICIT_MODIFIER"
    PREFIX_ONLY = "PREFIX_ONLY"
    SUFFIX_ONLY = "SUFFIX_ONLY"
    MODIFIER_POOL_RESTRICTED_BY_ACTION = "MODIFIER_POOL_RESTRICTED_BY_ACTION"
    GUARANTEED_MODIFIER_FAMILY = "GUARANTEED_MODIFIER_FAMILY"
    UNKNOWN = "UNKNOWN"


class OutcomeProbabilityStatus(str, Enum):
    KNOWN = "KNOWN"
    PARTIAL = "PARTIAL"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class OutcomeSpaceCompleteness(str, Enum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass(frozen=True)
class CraftOutcomeDefinition:
    action_id: str
    operations: tuple[CraftOutcomeOperation, ...]
    selection_rule: OutcomeSelectionRule
    eligible_scope: SlotScope = SlotScope.ANY
    add_count: int | None = None
    remove_count: int | None = None
    guaranteed_modifier_family_id: str | None = None
    required_free_slots: int | None = None
    probability_status: OutcomeProbabilityStatus = OutcomeProbabilityStatus.UNKNOWN
    provenance: tuple[DataProvenance, ...] = ()
    verification_status: str | None = None
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class ItemStateDelta:
    operation: CraftOutcomeOperation
    removed_modifier: ItemModifier | None = None
    added_modifier_id: str | None = None
    added_modifier_family_id: str | None = None
    guaranteed_modifier_family_id: str | None = None
    description: str | None = None

    def fingerprint_payload(self) -> str:
        removed = self.removed_modifier.raw_text if self.removed_modifier else ""
        return "|".join(
            (
                self.operation.value,
                removed,
                self.added_modifier_id or "",
                self.added_modifier_family_id or "",
                self.guaranteed_modifier_family_id or "",
                self.description or "",
            )
        )


@dataclass(frozen=True)
class HypotheticalItemState:
    outcome_id: str
    source_item_analysis_id: str
    action_id: str
    deltas: tuple[ItemStateDelta, ...]


@dataclass(frozen=True)
class CraftOutcomeSet:
    action_id: str
    source_item_analysis_id: str
    applicability_status: CraftApplicabilityStatus
    outcome_definition: CraftOutcomeDefinition | None
    hypothetical_states: tuple[HypotheticalItemState, ...]
    outcome_space_completeness: OutcomeSpaceCompleteness
    probability_completeness: OutcomeProbabilityStatus
    dataset_versions: tuple[str, ...] = ()
    provenance: tuple[DataProvenance, ...] = ()
    warnings: tuple[str, ...] = ()


class CraftOutcomeEngine:
    def enumerate_outcomes(
        self,
        item: ParsedItem,
        affix_state: AffixStateResolution | None,
        action: CraftActionDefinition,
        applicability: CraftActionApplicability,
        game_data_repository: GameDataRepository | None = None,
        game_data_dataset_version: str | None = None,
    ) -> CraftOutcomeSet:
        if applicability.status == CraftApplicabilityStatus.NOT_APPLICABLE:
            return CraftOutcomeSet(
                action_id=action.action_id,
                source_item_analysis_id=item.analysis_id,
                applicability_status=applicability.status,
                outcome_definition=None,
                hypothetical_states=(),
                outcome_space_completeness=OutcomeSpaceCompleteness.NOT_APPLICABLE,
                probability_completeness=OutcomeProbabilityStatus.NOT_APPLICABLE,
                warnings=applicability.failed_preconditions,
            )

        if _is_annulment(action.action_id):
            return self._annulment_outcomes(item, action, applicability)
        if _is_essence_hysteria(action.action_id):
            return self._essence_hysteria_outcomes(item, action, applicability)
        if _is_exalted(action.action_id):
            return self._exalted_outcomes(
                item,
                affix_state,
                action,
                applicability,
                game_data_repository,
                game_data_dataset_version,
            )
        return CraftOutcomeSet(
            action_id=action.action_id,
            source_item_analysis_id=item.analysis_id,
            applicability_status=applicability.status,
            outcome_definition=CraftOutcomeDefinition(
                action_id=action.action_id,
                operations=(CraftOutcomeOperation.OTHER,),
                selection_rule=OutcomeSelectionRule.UNKNOWN,
                probability_status=OutcomeProbabilityStatus.UNKNOWN,
                provenance=action.provenance,
                verification_status=action.verification_status.value,
                warnings=("Outcome semantics are not modeled for this action.",),
            ),
            hypothetical_states=(),
            outcome_space_completeness=OutcomeSpaceCompleteness.UNKNOWN,
            probability_completeness=OutcomeProbabilityStatus.UNKNOWN,
            provenance=action.provenance,
            warnings=("Outcome semantics are not modeled for this action.",),
        )

    def _annulment_outcomes(
        self,
        item: ParsedItem,
        action: CraftActionDefinition,
        applicability: CraftActionApplicability,
    ) -> CraftOutcomeSet:
        scope = _scope_from_action(action.action_id)
        remove_count = 2 if "greater-annulment" in action.action_id else 1
        eligible = tuple(modifier for modifier in item.explicit_modifiers if _modifier_in_scope(modifier, scope))
        eligible = tuple(modifier for modifier in eligible if modifier.origin != ModifierOrigin.FRACTURED)
        states = tuple(
            _state(
                item,
                action.action_id,
                (ItemStateDelta(CraftOutcomeOperation.REMOVE_MODIFIER, removed_modifier=modifier),),
            )
            for modifier in eligible
        )
        operation = CraftOutcomeOperation.REMOVE_MULTIPLE_MODIFIERS if remove_count > 1 else CraftOutcomeOperation.REMOVE_MODIFIER
        warnings = []
        if remove_count > 1:
            warnings.append("Greater Annulment removes two modifiers, but pairwise multi-removal state enumeration is deferred.")
        return CraftOutcomeSet(
            action_id=action.action_id,
            source_item_analysis_id=item.analysis_id,
            applicability_status=applicability.status,
            outcome_definition=CraftOutcomeDefinition(
                action_id=action.action_id,
                operations=(operation,),
                selection_rule=_selection_rule(scope),
                eligible_scope=scope,
                remove_count=remove_count,
                probability_status=OutcomeProbabilityStatus.UNKNOWN,
                provenance=action.provenance,
                verification_status=action.verification_status.value,
                warnings=tuple(warnings),
            ),
            hypothetical_states=states,
            outcome_space_completeness=OutcomeSpaceCompleteness.COMPLETE if remove_count == 1 else OutcomeSpaceCompleteness.PARTIAL,
            probability_completeness=OutcomeProbabilityStatus.UNKNOWN,
            provenance=action.provenance,
            warnings=tuple(warnings),
        )

    def _exalted_outcomes(
        self,
        item: ParsedItem,
        affix_state: AffixStateResolution | None,
        action: CraftActionDefinition,
        applicability: CraftActionApplicability,
        game_data_repository: GameDataRepository | None,
        game_data_dataset_version: str | None,
    ) -> CraftOutcomeSet:
        scope = _scope_from_action(action.action_id)
        add_count = 2 if "greater-exaltation" in action.action_id else 1
        operation = CraftOutcomeOperation.ADD_MULTIPLE_MODIFIERS if add_count > 1 else CraftOutcomeOperation.ADD_MODIFIER
        candidates: tuple[tuple[ModifierTierDefinition, ModifierFamily], ...] = ()
        warnings = ["Modifier pool is incomplete; no weights are loaded."]
        dataset_versions: tuple[str, ...] = ()
        if game_data_repository is not None and game_data_dataset_version is not None:
            candidates = _addition_candidates(item, scope, game_data_repository, game_data_dataset_version)
            dataset_versions = (game_data_dataset_version,)
        else:
            warnings.append("No game-data repository supplied for modifier pool enumeration.")
        states = tuple(
            _state(
                item,
                action.action_id,
                (
                    ItemStateDelta(
                        operation=CraftOutcomeOperation.ADD_MODIFIER,
                        added_modifier_id=modifier_tier.canonical_id,
                        added_modifier_family_id=family.canonical_id,
                    ),
                ),
            )
            for modifier_tier, family in candidates
        )
        return CraftOutcomeSet(
            action_id=action.action_id,
            source_item_analysis_id=item.analysis_id,
            applicability_status=applicability.status,
            outcome_definition=CraftOutcomeDefinition(
                action_id=action.action_id,
                operations=(operation,),
                selection_rule=OutcomeSelectionRule.MODIFIER_POOL_RESTRICTED_BY_ACTION,
                eligible_scope=scope,
                add_count=add_count,
                required_free_slots=add_count,
                probability_status=OutcomeProbabilityStatus.UNKNOWN,
                provenance=action.provenance,
                verification_status=action.verification_status.value,
                warnings=tuple(warnings),
            ),
            hypothetical_states=states,
            outcome_space_completeness=OutcomeSpaceCompleteness.PARTIAL if states else OutcomeSpaceCompleteness.UNKNOWN,
            probability_completeness=OutcomeProbabilityStatus.UNKNOWN,
            dataset_versions=dataset_versions,
            provenance=action.provenance,
            warnings=tuple(warnings),
        )

    def _essence_hysteria_outcomes(
        self,
        item: ParsedItem,
        action: CraftActionDefinition,
        applicability: CraftActionApplicability,
    ) -> CraftOutcomeSet:
        eligible = tuple(modifier for modifier in item.explicit_modifiers if modifier.origin != ModifierOrigin.FRACTURED)
        guaranteed_family = "dc:poe2:modifier-family:damagewithweapontypeskill"
        states = tuple(
            _state(
                item,
                action.action_id,
                (
                    ItemStateDelta(CraftOutcomeOperation.REMOVE_MODIFIER, removed_modifier=modifier),
                    ItemStateDelta(
                        CraftOutcomeOperation.GUARANTEE_MODIFIER,
                        guaranteed_modifier_family_id=guaranteed_family,
                        description="Essence of Hysteria guarantees increased Damage with Bow Skills for Quivers.",
                    ),
                ),
            )
            for modifier in eligible
        )
        return CraftOutcomeSet(
            action_id=action.action_id,
            source_item_analysis_id=item.analysis_id,
            applicability_status=applicability.status,
            outcome_definition=CraftOutcomeDefinition(
                action_id=action.action_id,
                operations=(CraftOutcomeOperation.REMOVE_MODIFIER, CraftOutcomeOperation.GUARANTEE_MODIFIER),
                selection_rule=OutcomeSelectionRule.GUARANTEED_MODIFIER_FAMILY,
                guaranteed_modifier_family_id=guaranteed_family,
                probability_status=OutcomeProbabilityStatus.UNKNOWN,
                provenance=action.provenance,
                verification_status=action.verification_status.value,
                warnings=("Atomic replacement/addition capacity behavior remains not fully modeled.",),
            ),
            hypothetical_states=states,
            outcome_space_completeness=OutcomeSpaceCompleteness.PARTIAL,
            probability_completeness=OutcomeProbabilityStatus.UNKNOWN,
            provenance=action.provenance,
            warnings=("Atomic replacement/addition capacity behavior remains not fully modeled.",),
        )


def _addition_candidates(
    item: ParsedItem,
    scope: SlotScope,
    repository: GameDataRepository,
    dataset_version: str,
) -> tuple[tuple[ModifierTierDefinition, ModifierFamily], ...]:
    dataset = repository.get_dataset(dataset_version)
    families = {family.canonical_id: family for family in dataset.modifier_families}
    applicability = {entry.modifier_id for entry in dataset.modifier_applicability if entry.item_class == item.item_class}
    existing_groups = {
        modifier.family or modifier.group
        for modifier in item.explicit_modifiers
        if modifier.family or modifier.group
    }
    candidates = []
    for tier in dataset.modifier_tiers:
        if tier.canonical_id not in applicability:
            continue
        family = families[tier.modifier_family_id]
        if scope == SlotScope.PREFIX and family.affix_type != AffixType.PREFIX:
            continue
        if scope == SlotScope.SUFFIX and family.affix_type != AffixType.SUFFIX:
            continue
        if tier.required_item_level is not None and item.item_level is not None and tier.required_item_level > item.item_level:
            continue
        if family.modifier_group and family.modifier_group in existing_groups:
            continue
        candidates.append((tier, family))
    return tuple(candidates)


def _state(item: ParsedItem, action_id: str, deltas: tuple[ItemStateDelta, ...]) -> HypotheticalItemState:
    payload = "|".join((item.analysis_id, action_id, *(delta.fingerprint_payload() for delta in deltas)))
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]
    return HypotheticalItemState(
        outcome_id=f"outcome-{digest}",
        source_item_analysis_id=item.analysis_id,
        action_id=action_id,
        deltas=deltas,
    )


def _modifier_in_scope(modifier: ItemModifier, scope: SlotScope) -> bool:
    if scope == SlotScope.PREFIX:
        return modifier.affix_type == AffixType.PREFIX
    if scope == SlotScope.SUFFIX:
        return modifier.affix_type == AffixType.SUFFIX
    return modifier.affix_type in {AffixType.PREFIX, AffixType.SUFFIX, AffixType.UNKNOWN}


def _selection_rule(scope: SlotScope) -> OutcomeSelectionRule:
    if scope == SlotScope.PREFIX:
        return OutcomeSelectionRule.PREFIX_ONLY
    if scope == SlotScope.SUFFIX:
        return OutcomeSelectionRule.SUFFIX_ONLY
    return OutcomeSelectionRule.ANY_ELIGIBLE_EXPLICIT_MODIFIER


def _scope_from_action(action_id: str) -> SlotScope:
    if "sinistral" in action_id:
        return SlotScope.PREFIX
    if "dextral" in action_id:
        return SlotScope.SUFFIX
    return SlotScope.ANY


def _is_annulment(action_id: str) -> bool:
    return "annulment" in action_id


def _is_exalted(action_id: str) -> bool:
    return "exalted-orb" in action_id or "exaltation" in action_id


def _is_essence_hysteria(action_id: str) -> bool:
    return action_id.endswith(":essence-of-hysteria")
