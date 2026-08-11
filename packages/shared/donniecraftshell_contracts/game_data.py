"""Canonical game-data and modifier-enrichment contracts.

These models describe the boundary between parsed clipboard observations and
external game-data snapshots. They do not fetch, scrape, rank, or simulate.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Mapping

from .domain import (
    AffixType,
    Confidence,
    DataProvenance,
    GameContext,
    ItemModifier,
    ParsedItem,
    RollValue,
    VerificationStatus,
)


class ResolutionStatus(str, Enum):
    RESOLVED = "RESOLVED"
    AMBIGUOUS = "AMBIGUOUS"
    UNRESOLVED = "UNRESOLVED"


class WeightMethodology(str, Enum):
    GAME_FILE_EXTRACTED = "GAME_FILE_EXTRACTED"
    COMMUNITY_DERIVED = "COMMUNITY_DERIVED"
    EMPIRICAL_OBSERVATION = "EMPIRICAL_OBSERVATION"
    CURATED_ESTIMATE = "CURATED_ESTIMATE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class GameDataSnapshot:
    snapshot_id: str
    source: str
    source_uri: str | None = None
    retrieved_at: datetime | None = None
    game_context: GameContext | None = None
    checksum: str | None = None
    verification_status: VerificationStatus = VerificationStatus.NEEDS_VERIFICATION
    notes: str | None = None
    provenance: tuple[DataProvenance, ...] = ()


@dataclass(frozen=True)
class ItemBaseDefinition:
    canonical_id: str
    item_class: str
    base_name: str
    required_level: int | None = None
    implicit_modifier_ids: tuple[str, ...] = ()
    provenance: tuple[DataProvenance, ...] = ()
    dataset_version: str | None = None

    def __post_init__(self) -> None:
        _require_source_backed_id(self.canonical_id, "base canonical_id")
        if self.required_level is not None and self.required_level < 0:
            raise ValueError("required_level cannot be negative")


@dataclass(frozen=True)
class ModifierFamily:
    canonical_id: str
    normalized_stat_template: str
    affix_type: AffixType = AffixType.UNKNOWN
    tags: tuple[str, ...] = ()
    modifier_group: str | None = None
    provenance: tuple[DataProvenance, ...] = ()

    def __post_init__(self) -> None:
        _require_source_backed_id(self.canonical_id, "modifier family canonical_id")


@dataclass(frozen=True)
class ModifierTierDefinition:
    canonical_id: str
    modifier_family_id: str
    tier: str | None = None
    display_name: str | None = None
    required_item_level: int | None = None
    roll_ranges: tuple[RollValue, ...] = ()
    provenance: tuple[DataProvenance, ...] = ()
    dataset_version: str | None = None

    def __post_init__(self) -> None:
        _require_source_backed_id(self.canonical_id, "modifier tier canonical_id")
        _require_source_backed_id(self.modifier_family_id, "modifier_family_id")
        if self.display_name and self.canonical_id.lower() == self.display_name.lower():
            raise ValueError("canonical_id must not be based solely on display name")
        if self.required_item_level is not None and self.required_item_level < 0:
            raise ValueError("required_item_level cannot be negative")


@dataclass(frozen=True)
class ModifierApplicability:
    modifier_id: str
    item_class: str | None = None
    base_restrictions: tuple[str, ...] = ()
    tags_or_conditions: tuple[str, ...] = ()
    provenance: tuple[DataProvenance, ...] = ()

    def __post_init__(self) -> None:
        _require_source_backed_id(self.modifier_id, "modifier_id")


@dataclass(frozen=True)
class ModifierWeight:
    modifier_id: str
    weight: Decimal | None = None
    source: str | None = None
    confidence: Confidence | None = None
    methodology: WeightMethodology = WeightMethodology.UNKNOWN
    provenance: tuple[DataProvenance, ...] = ()

    def __post_init__(self) -> None:
        _require_source_backed_id(self.modifier_id, "modifier_id")
        if self.weight is not None and self.weight < Decimal("0"):
            raise ValueError("weight cannot be negative")


@dataclass(frozen=True)
class ModifierResolutionCandidate:
    canonical_modifier_id: str
    confidence: Confidence | None = None
    match_reasons: tuple[str, ...] = ()
    provenance: tuple[DataProvenance, ...] = ()
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_source_backed_id(self.canonical_modifier_id, "canonical_modifier_id")


@dataclass(frozen=True)
class ModifierResolution:
    parsed_modifier: ItemModifier
    status: ResolutionStatus
    selected_canonical_modifier_id: str | None = None
    candidates: tuple[ModifierResolutionCandidate, ...] = ()
    confidence: Confidence | None = None
    match_reasons: tuple[str, ...] = ()
    provenance: tuple[DataProvenance, ...] = ()
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.selected_canonical_modifier_id is not None:
            _require_source_backed_id(
                self.selected_canonical_modifier_id,
                "selected_canonical_modifier_id",
            )
        if self.status == ResolutionStatus.RESOLVED and self.selected_canonical_modifier_id is None:
            raise ValueError("RESOLVED resolution requires selected_canonical_modifier_id")
        if self.status != ResolutionStatus.RESOLVED and self.selected_canonical_modifier_id is not None:
            raise ValueError("Only RESOLVED resolution may select a canonical modifier")
        if self.status == ResolutionStatus.AMBIGUOUS and len(self.candidates) < 2:
            raise ValueError("AMBIGUOUS resolution requires at least two candidates")


@dataclass(frozen=True)
class ItemEnrichment:
    enrichment_id: str
    parsed_item: ParsedItem
    snapshot_id: str
    modifier_resolutions: tuple[ModifierResolution, ...] = ()
    resolved_base_id: str | None = None
    warnings: tuple[str, ...] = ()
    metadata: Mapping[str, str] | None = None


class ModifierResolver:
    """Interface contract for future resolver implementations."""

    def resolve_modifier(
        self,
        parsed_item: ParsedItem,
        modifier: ItemModifier,
        snapshot: GameDataSnapshot,
    ) -> ModifierResolution:
        raise NotImplementedError


def _require_source_backed_id(value: str, field_name: str) -> None:
    if ":" not in value:
        raise ValueError(f"{field_name} must be source-backed and namespaced")
