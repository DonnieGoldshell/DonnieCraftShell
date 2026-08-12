"""Legal modifier-pool resolution for Exalted-style outcome enumeration."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .affix_capacity import AffixStateResolution, SlotScope
from .domain import AffixType, ItemModifier, ParsedItem
from .game_data import ModifierFamily, ModifierTierDefinition
from .game_data_repository import GameDataRepository


class ModifierPoolCompleteness(str, Enum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class ExcludedModifierCandidate:
    modifier_tier_id: str
    reason: str


@dataclass(frozen=True)
class ModifierPoolResult:
    dataset_version: str
    item_class: str | None
    side: SlotScope
    candidates: tuple[tuple[ModifierTierDefinition, ModifierFamily], ...]
    excluded: tuple[ExcludedModifierCandidate, ...]
    completeness: ModifierPoolCompleteness
    warnings: tuple[str, ...] = ()


class ModifierPoolResolver:
    def get_legal_candidates(
        self,
        item: ParsedItem,
        affix_state: AffixStateResolution | None,
        side: SlotScope,
        game_data_repository: GameDataRepository,
        dataset_version: str,
    ) -> ModifierPoolResult:
        dataset = game_data_repository.get_dataset(dataset_version)
        families = {family.canonical_id: family for family in dataset.modifier_families}
        applicable_ids = {
            entry.modifier_id
            for entry in dataset.modifier_applicability
            if entry.item_class == item.item_class
        }
        warnings = [
            "Modifier pool dataset is fixture-backed and not proven complete for all natural Quiver affixes."
        ]
        if _has_unresolved_existing_modifier(item):
            warnings.append("One or more existing explicit modifiers lack conflict-group data; conflict filtering is incomplete.")

        if affix_state is not None and _side_is_full(affix_state, side):
            return ModifierPoolResult(
                dataset_version=dataset_version,
                item_class=item.item_class,
                side=side,
                candidates=(),
                excluded=(),
                completeness=ModifierPoolCompleteness.PARTIAL,
                warnings=tuple(warnings),
            )

        existing_groups = _existing_groups(item)
        candidates: list[tuple[ModifierTierDefinition, ModifierFamily]] = []
        excluded: list[ExcludedModifierCandidate] = []
        for tier in dataset.modifier_tiers:
            family = families[tier.modifier_family_id]
            if tier.canonical_id not in applicable_ids:
                excluded.append(ExcludedModifierCandidate(tier.canonical_id, "not applicable to item class"))
                continue
            if not _affix_matches_side(family.affix_type, side):
                excluded.append(ExcludedModifierCandidate(tier.canonical_id, "affix side does not match action side"))
                continue
            if tier.required_item_level is not None and item.item_level is not None and tier.required_item_level > item.item_level:
                excluded.append(ExcludedModifierCandidate(tier.canonical_id, "required item level exceeds item level"))
                continue
            if family.modifier_group and family.modifier_group in existing_groups:
                excluded.append(ExcludedModifierCandidate(tier.canonical_id, "same modifier group already present"))
                continue
            candidates.append((tier, family))

        return ModifierPoolResult(
            dataset_version=dataset_version,
            item_class=item.item_class,
            side=side,
            candidates=tuple(candidates),
            excluded=tuple(excluded),
            completeness=ModifierPoolCompleteness.PARTIAL,
            warnings=tuple(warnings),
        )


def _affix_matches_side(affix_type: AffixType, side: SlotScope) -> bool:
    if affix_type not in {AffixType.PREFIX, AffixType.SUFFIX}:
        return False
    if side == SlotScope.PREFIX:
        return affix_type == AffixType.PREFIX
    if side == SlotScope.SUFFIX:
        return affix_type == AffixType.SUFFIX
    return True


def _side_is_full(affix_state: AffixStateResolution, side: SlotScope) -> bool:
    if side == SlotScope.PREFIX:
        return affix_state.open_prefix_count == 0
    if side == SlotScope.SUFFIX:
        return affix_state.open_suffix_count == 0
    return affix_state.open_prefix_count == 0 and affix_state.open_suffix_count == 0


def _existing_groups(item: ParsedItem) -> set[str]:
    return {
        modifier.family or modifier.group
        for modifier in item.explicit_modifiers
        if modifier.family or modifier.group
    }


def _has_unresolved_existing_modifier(item: ParsedItem) -> bool:
    return any(
        modifier.affix_type in {AffixType.PREFIX, AffixType.SUFFIX}
        and not (modifier.family or modifier.group or modifier.canonical_id)
        for modifier in item.explicit_modifiers
    )
