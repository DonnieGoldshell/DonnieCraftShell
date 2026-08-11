"""Canonical modifier resolver using normalized offline game data."""

from __future__ import annotations

import uuid
from decimal import Decimal

from .domain import Confidence, ConfidenceLevel, ItemModifier, ParsedItem, RollValue
from .game_data import (
    GameDataSnapshot,
    ItemEnrichment,
    ModifierResolution,
    ModifierResolutionCandidate,
    ModifierResolver,
    ResolutionStatus,
)
from .game_data_repository import GameDataRepository


class CanonicalModifierResolver(ModifierResolver):
    def __init__(self, repository: GameDataRepository, dataset_version: str):
        self.repository = repository
        self.dataset_version = dataset_version

    def resolve_modifier(
        self,
        parsed_item: ParsedItem,
        modifier: ItemModifier,
        snapshot: GameDataSnapshot | None = None,
    ) -> ModifierResolution:
        if not modifier.display_name and not modifier.tier:
            return ModifierResolution(
                parsed_modifier=modifier,
                status=ResolutionStatus.UNRESOLVED,
                confidence=Confidence(
                    Decimal("0"),
                    ConfidenceLevel.LOW,
                    reasons=("Structured display name or tier evidence is required for canonical resolution.",),
                ),
                warnings=("Insufficient structured modifier identity; no broad dataset search attempted.",),
            )
        candidates = self.repository.candidates_for_modifier(
            self.dataset_version,
            parsed_item.item_class,
            modifier.affix_type,
            modifier.display_name,
            modifier.tier,
        )
        supported = []
        rejected_reasons: list[str] = []
        for modifier_tier, family, applicability in candidates:
            range_match, range_reason = _ranges_match(modifier.allowed_range, modifier_tier.roll_ranges)
            if not range_match:
                rejected_reasons.append(
                    f"{modifier_tier.canonical_id} rejected: {range_reason}"
                )
                continue
            tag_reason = _tags_reason(modifier.tags, family.tags)
            reasons = (
                "item class matched applicability",
                "affix type matched",
                "display name matched",
                "tier matched",
                range_reason,
                tag_reason,
            )
            supported.append(
                ModifierResolutionCandidate(
                    canonical_modifier_id=modifier_tier.canonical_id,
                    confidence=Confidence(Decimal("0.90"), ConfidenceLevel.HIGH, reasons=reasons),
                    match_reasons=reasons,
                    provenance=modifier_tier.provenance,
                    warnings=(
                        "Community source remains NEEDS REVIEW / NEEDS VERIFICATION.",
                    ),
                )
            )
        if len(supported) == 1:
            candidate = supported[0]
            return ModifierResolution(
                parsed_modifier=modifier,
                status=ResolutionStatus.RESOLVED,
                selected_canonical_modifier_id=candidate.canonical_modifier_id,
                candidates=(candidate,),
                confidence=candidate.confidence,
                match_reasons=candidate.match_reasons,
                provenance=candidate.provenance,
                warnings=candidate.warnings,
            )
        if len(supported) > 1:
            return ModifierResolution(
                parsed_modifier=modifier,
                status=ResolutionStatus.AMBIGUOUS,
                candidates=tuple(supported),
                confidence=Confidence(
                    Decimal("0.40"),
                    ConfidenceLevel.LOW,
                    reasons=("Multiple candidates satisfied structured evidence.",),
                ),
                warnings=("Ambiguous modifier resolution; no canonical ID selected.",),
            )
        return ModifierResolution(
            parsed_modifier=modifier,
            status=ResolutionStatus.UNRESOLVED,
            confidence=Confidence(
                Decimal("0"),
                ConfidenceLevel.LOW,
                reasons=("No normalized dataset candidate satisfied required evidence.",),
            ),
            warnings=tuple(rejected_reasons) or ("No normalized dataset candidates found.",),
        )


def enrich_item(
    parsed_item: ParsedItem,
    repository: GameDataRepository,
    dataset_version: str,
) -> ItemEnrichment:
    dataset = repository.get_dataset(dataset_version)
    resolver = CanonicalModifierResolver(repository, dataset_version)
    resolutions = tuple(
        resolver.resolve_modifier(parsed_item, modifier, dataset.snapshot)
        for modifier in parsed_item.modifiers
    )
    return ItemEnrichment(
        enrichment_id=generate_enrichment_id(),
        parsed_item=parsed_item,
        snapshot_id=dataset.snapshot.snapshot_id,
        modifier_resolutions=resolutions,
        metadata={"dataset_version": dataset_version},
    )


def generate_enrichment_id() -> str:
    if not hasattr(uuid, "uuid7"):
        raise RuntimeError("DonnieCraftShell requires Python with stdlib uuid.uuid7 support.")
    return f"enrichment-{uuid.uuid7()}"


def _ranges_match(observed: tuple[RollValue, ...], canonical: tuple[RollValue, ...]) -> tuple[bool, str]:
    observed_ranges = tuple(roll for roll in observed if roll.min_value is not None or roll.max_value is not None)
    if not canonical or not observed_ranges:
        return True, "range evidence unavailable or not required"
    if len(observed_ranges) != len(canonical):
        return False, "range count mismatch"
    parsed_ranges = sorted(_range_pair(roll) for roll in observed_ranges)
    canonical_ranges = sorted(_range_pair(roll) for roll in canonical)
    if parsed_ranges != canonical_ranges:
        return False, "displayed range conflicts with canonical range"
    return True, "displayed range matched"


def _range_pair(roll: RollValue) -> tuple[str, str]:
    return (
        str(roll.min_value) if roll.min_value is not None else "",
        str(roll.max_value) if roll.max_value is not None else "",
    )


def _tags_reason(observed_tags: tuple[str, ...], canonical_tags: tuple[str, ...]) -> str:
    if not canonical_tags or not observed_tags:
        return "tag evidence unavailable or nonessential"
    if set(tag.lower() for tag in observed_tags).issubset(set(tag.lower() for tag in canonical_tags)):
        return "tags supported"
    return "tag mismatch tolerated as supporting-only evidence"
