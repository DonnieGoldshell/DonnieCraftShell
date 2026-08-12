"""Craft action definitions and applicability checks.

This module models source-backed legality and required materials only. It does
not simulate outcomes, assign probabilities, value items, or recommend actions.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any

from .affix_capacity import AffixStateResolution, SlotScope
from .domain import (
    Confidence,
    ConfidenceLevel,
    DataProvenance,
    ItemSpecialState,
    ParsedItem,
    Rarity,
    SourceType,
    VerificationStatus,
)


class CraftApplicabilityStatus(str, Enum):
    APPLICABLE = "APPLICABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNKNOWN = "UNKNOWN"


class CraftActionKind(str, Enum):
    CURRENCY = "CURRENCY"
    OMEN_MODIFIED_CURRENCY = "OMEN_MODIFIED_CURRENCY"
    ESSENCE = "ESSENCE"


class PreconditionKind(str, Enum):
    RARITY_IN = "RARITY_IN"
    NOT_CORRUPTED = "NOT_CORRUPTED"
    HAS_EXPLICIT_MODIFIER = "HAS_EXPLICIT_MODIFIER"
    MIN_EXPLICIT_MODIFIERS = "MIN_EXPLICIT_MODIFIERS"
    HAS_OPEN_AFFIX_SLOT = "HAS_OPEN_AFFIX_SLOT"
    MIN_OPEN_AFFIX_SLOTS = "MIN_OPEN_AFFIX_SLOTS"
    ITEM_CLASS_IN = "ITEM_CLASS_IN"


@dataclass(frozen=True)
class RequiredMaterial:
    asset_id: str
    quantity: Decimal

    def __post_init__(self) -> None:
        if isinstance(self.quantity, float):
            raise TypeError("required material quantity must not use binary floating point")
        quantity = Decimal(self.quantity)
        if quantity <= Decimal("0"):
            raise ValueError("required material quantity must be positive")
        if ":" not in self.asset_id:
            raise ValueError("required material asset_id must be namespaced")
        object.__setattr__(self, "quantity", quantity)


@dataclass(frozen=True)
class CraftActionPrecondition:
    kind: PreconditionKind
    values: tuple[str, ...] = ()
    description: str | None = None
    verification_status: VerificationStatus = VerificationStatus.NEEDS_VERIFICATION
    provenance: tuple[DataProvenance, ...] = ()

    def __post_init__(self) -> None:
        if self.verification_status == VerificationStatus.VERIFIED and not self.provenance:
            raise ValueError("VERIFIED precondition requires provenance")


@dataclass(frozen=True)
class CraftActionDefinition:
    action_id: str
    display_name: str
    kind: CraftActionKind
    required_materials: tuple[RequiredMaterial, ...]
    preconditions: tuple[CraftActionPrecondition, ...]
    mechanic_summary: str
    unknown_conditions: tuple[str, ...] = ()
    provenance: tuple[DataProvenance, ...] = ()
    verification_status: VerificationStatus = VerificationStatus.NEEDS_VERIFICATION
    simulation_supported: bool = False

    def __post_init__(self) -> None:
        if ":" not in self.action_id:
            raise ValueError("action_id must be namespaced")
        if self.verification_status == VerificationStatus.VERIFIED and not self.provenance:
            raise ValueError("VERIFIED action definition requires provenance")
        if self.simulation_supported:
            raise ValueError("Task 7A action definitions must not support simulation")


@dataclass(frozen=True)
class CraftingDatasetSnapshot:
    dataset_id: str
    source: str
    retrieved_at: datetime
    game: str
    game_version: str | None
    actions: tuple[CraftActionDefinition, ...]
    provenance: tuple[DataProvenance, ...] = ()
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.dataset_id:
            raise ValueError("crafting dataset_id is required")


@dataclass(frozen=True)
class CraftActionApplicability:
    action_id: str
    status: CraftApplicabilityStatus
    required_materials: tuple[RequiredMaterial, ...]
    reasons: tuple[str, ...] = ()
    failed_preconditions: tuple[str, ...] = ()
    unknown_preconditions: tuple[str, ...] = ()
    confidence: Confidence | None = None
    provenance: tuple[DataProvenance, ...] = ()


class CraftActionEngine:
    def __init__(self, dataset: CraftingDatasetSnapshot):
        self.dataset = dataset

    def get_candidate_actions(self, item: ParsedItem, enrichment: Any | None = None) -> tuple[CraftActionApplicability, ...]:
        return tuple(self.evaluate_action(action, item, enrichment) for action in self.dataset.actions)

    def evaluate_action(
        self,
        action: CraftActionDefinition,
        item: ParsedItem,
        enrichment: Any | None = None,
    ) -> CraftActionApplicability:
        reasons: list[str] = []
        failed: list[str] = []
        unknown: list[str] = list(action.unknown_conditions)
        affix_resolution = _affix_resolution_from(enrichment)

        for precondition in action.preconditions:
            result, reason = _evaluate_precondition(precondition, item, affix_resolution)
            if result == CraftApplicabilityStatus.NOT_APPLICABLE:
                failed.append(reason)
            elif result == CraftApplicabilityStatus.UNKNOWN:
                unknown.append(reason)
            else:
                reasons.append(reason)

        if failed:
            status = CraftApplicabilityStatus.NOT_APPLICABLE
            confidence = Confidence(level=ConfidenceLevel.HIGH, reasons=("One or more verified preconditions failed.",))
        elif unknown:
            status = CraftApplicabilityStatus.UNKNOWN
            confidence = Confidence(level=ConfidenceLevel.LOW, reasons=("Applicability has unresolved preconditions.",))
        else:
            status = CraftApplicabilityStatus.APPLICABLE
            confidence = Confidence(level=ConfidenceLevel.MEDIUM, reasons=("All modeled preconditions passed.",))

        return CraftActionApplicability(
            action_id=action.action_id,
            status=status,
            required_materials=action.required_materials,
            reasons=tuple(reasons),
            failed_preconditions=tuple(failed),
            unknown_preconditions=tuple(unknown),
            confidence=confidence,
            provenance=action.provenance,
        )


def load_crafting_dataset(path: Path) -> CraftingDatasetSnapshot:
    data = json.loads(path.read_text(encoding="utf-8"), parse_float=Decimal, parse_int=Decimal)
    provenance = tuple(_provenance(item) for item in data.get("provenance", []))
    actions = tuple(_action(item) for item in data.get("actions", []))
    return CraftingDatasetSnapshot(
        dataset_id=data["dataset_id"],
        source=data["source"],
        retrieved_at=_parse_datetime(data["retrieved_at"]),
        game=data.get("game", "Path of Exile 2"),
        game_version=data.get("game_version"),
        actions=actions,
        provenance=provenance,
        notes=tuple(data.get("notes", [])),
    )


def _action(data: dict[str, Any]) -> CraftActionDefinition:
    provenance = tuple(_provenance(item) for item in data.get("provenance", []))
    return CraftActionDefinition(
        action_id=data["action_id"],
        display_name=data["display_name"],
        kind=CraftActionKind[data["kind"]],
        required_materials=tuple(
            RequiredMaterial(asset_id=item["asset_id"], quantity=item["quantity"])
            for item in data.get("required_materials", [])
        ),
        preconditions=tuple(_precondition(item) for item in data.get("preconditions", [])),
        mechanic_summary=data["mechanic_summary"],
        unknown_conditions=tuple(data.get("unknown_conditions", [])),
        provenance=provenance,
        verification_status=VerificationStatus[data.get("verification_status", "NEEDS_VERIFICATION")],
        simulation_supported=data.get("simulation_supported", False),
    )


def _precondition(data: dict[str, Any]) -> CraftActionPrecondition:
    return CraftActionPrecondition(
        kind=PreconditionKind[data["kind"]],
        values=tuple(data.get("values", [])),
        description=data.get("description"),
        verification_status=VerificationStatus[data.get("verification_status", "NEEDS_VERIFICATION")],
        provenance=tuple(_provenance(item) for item in data.get("provenance", [])),
    )


def _evaluate_precondition(
    precondition: CraftActionPrecondition,
    item: ParsedItem,
    affix_resolution: AffixStateResolution | None = None,
) -> tuple[CraftApplicabilityStatus, str]:
    if precondition.verification_status != VerificationStatus.VERIFIED:
        return CraftApplicabilityStatus.UNKNOWN, precondition.description or precondition.kind.value
    if precondition.kind == PreconditionKind.RARITY_IN:
        if item.rarity.value in precondition.values:
            return CraftApplicabilityStatus.APPLICABLE, f"rarity {item.rarity.value} matched"
        return CraftApplicabilityStatus.NOT_APPLICABLE, f"rarity {item.rarity.value} not in {precondition.values}"
    if precondition.kind == PreconditionKind.NOT_CORRUPTED:
        if ItemSpecialState.CORRUPTED in item.special_states or ItemSpecialState.TWICE_CORRUPTED in item.special_states:
            return CraftApplicabilityStatus.NOT_APPLICABLE, "item is corrupted"
        return CraftApplicabilityStatus.APPLICABLE, "item is not corrupted"
    if precondition.kind == PreconditionKind.HAS_EXPLICIT_MODIFIER:
        scope = _slot_scope(precondition.values)
        count = _explicit_modifier_count(item, scope)
        if count > 0:
            return CraftApplicabilityStatus.APPLICABLE, f"item has {scope.value.lower()} explicit modifier"
        return CraftApplicabilityStatus.NOT_APPLICABLE, f"item has no {scope.value.lower()} explicit modifiers"
    if precondition.kind == PreconditionKind.MIN_EXPLICIT_MODIFIERS:
        scope = _slot_scope(precondition.values)
        required_count = _required_count(precondition.values, default=1)
        count = _explicit_modifier_count(item, scope)
        if count >= required_count:
            return CraftApplicabilityStatus.APPLICABLE, f"item has at least {required_count} {scope.value.lower()} explicit modifiers"
        if count == 0:
            return CraftApplicabilityStatus.NOT_APPLICABLE, f"item has no {scope.value.lower()} explicit modifiers"
        return CraftApplicabilityStatus.UNKNOWN, f"item has only {count} {scope.value.lower()} explicit modifier; two-modifier behavior is not verified"
    if precondition.kind == PreconditionKind.HAS_OPEN_AFFIX_SLOT:
        scope = _slot_scope(precondition.values)
        if affix_resolution is not None:
            has_open_slot = affix_resolution.has_open_slot(scope)
            if has_open_slot is None:
                return CraftApplicabilityStatus.UNKNOWN, f"{scope.value.lower()} open affix slots are unknown"
            if has_open_slot:
                return CraftApplicabilityStatus.APPLICABLE, f"{scope.value.lower()} open affix slot is known"
            return CraftApplicabilityStatus.NOT_APPLICABLE, f"no {scope.value.lower()} open affix slots"
        if item.affix_state is None:
            return CraftApplicabilityStatus.UNKNOWN, "affix state is unavailable"
        open_prefixes = item.affix_state.open_prefix_count
        open_suffixes = item.affix_state.open_suffix_count
        if open_prefixes is None and open_suffixes is None:
            return CraftApplicabilityStatus.UNKNOWN, "open affix slots are unknown"
        if (open_prefixes or 0) + (open_suffixes or 0) > 0:
            return CraftApplicabilityStatus.APPLICABLE, "at least one open affix slot is known"
        return CraftApplicabilityStatus.NOT_APPLICABLE, "no open affix slots"
    if precondition.kind == PreconditionKind.MIN_OPEN_AFFIX_SLOTS:
        scope = _slot_scope(precondition.values)
        required_count = _required_count(precondition.values, default=1)
        if affix_resolution is None:
            return CraftApplicabilityStatus.UNKNOWN, f"{scope.value.lower()} open affix slots are unknown"
        open_count = _open_slot_count(affix_resolution, scope)
        if open_count is None:
            return CraftApplicabilityStatus.UNKNOWN, f"{scope.value.lower()} open affix slots are unknown"
        if open_count >= required_count:
            return CraftApplicabilityStatus.APPLICABLE, f"at least {required_count} {scope.value.lower()} open affix slots are known"
        if open_count == 0:
            return CraftApplicabilityStatus.NOT_APPLICABLE, f"no {scope.value.lower()} open affix slots"
        return CraftApplicabilityStatus.UNKNOWN, f"only {open_count} {scope.value.lower()} open affix slot is known; two-modifier behavior is not verified"
    if precondition.kind == PreconditionKind.ITEM_CLASS_IN:
        if item.item_class in precondition.values:
            return CraftApplicabilityStatus.APPLICABLE, f"item class {item.item_class} matched"
        return CraftApplicabilityStatus.NOT_APPLICABLE, f"item class {item.item_class} not in {precondition.values}"
    return CraftApplicabilityStatus.UNKNOWN, f"unsupported precondition {precondition.kind.value}"


def _affix_resolution_from(enrichment: Any | None) -> AffixStateResolution | None:
    if enrichment is None:
        return None
    if isinstance(enrichment, AffixStateResolution):
        return enrichment
    candidate = getattr(enrichment, "affix_state_resolution", None)
    return candidate if isinstance(candidate, AffixStateResolution) else None


def _slot_scope(values: tuple[str, ...]) -> SlotScope:
    if not values:
        return SlotScope.ANY
    first = values[0].upper()
    return SlotScope.__members__.get(first, SlotScope.ANY)


def _required_count(values: tuple[str, ...], default: int) -> int:
    for value in reversed(values):
        try:
            return int(value)
        except ValueError:
            continue
    return default


def _explicit_modifier_count(item: ParsedItem, scope: SlotScope) -> int:
    if scope == SlotScope.PREFIX:
        return sum(1 for modifier in item.explicit_modifiers if modifier.affix_type.value == "PREFIX")
    if scope == SlotScope.SUFFIX:
        return sum(1 for modifier in item.explicit_modifiers if modifier.affix_type.value == "SUFFIX")
    return len(item.explicit_modifiers)


def _open_slot_count(resolution: AffixStateResolution, scope: SlotScope) -> int | None:
    if scope == SlotScope.PREFIX:
        return resolution.open_prefix_count
    if scope == SlotScope.SUFFIX:
        return resolution.open_suffix_count
    if resolution.open_prefix_count is None and resolution.open_suffix_count is None:
        return None
    return (resolution.open_prefix_count or 0) + (resolution.open_suffix_count or 0)


def _provenance(data: dict[str, Any]) -> DataProvenance:
    return DataProvenance(
        source_id=data["source_id"],
        source_type=SourceType[data.get("source_type", "COMMUNITY")],
        source_uri=data.get("source_uri"),
        retrieved_at=_parse_datetime(data.get("retrieved_at")),
        verification_status=VerificationStatus[data.get("verification_status", "NEEDS_VERIFICATION")],
        confidence=Confidence(level=ConfidenceLevel[data["confidence_level"]]) if data.get("confidence_level") else None,
        notes=data.get("notes"),
    )


def _parse_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
