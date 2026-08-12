"""Affix capacity definitions and derived open-slot state.

This module derives explicit prefix/suffix slot state from parsed observations
plus a versioned, source-backed capacity dataset. It does not mutate ParsedItem
and does not encode crafting outcomes.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any

from .domain import (
    AffixType,
    Confidence,
    ConfidenceLevel,
    DataProvenance,
    ItemModifier,
    ModifierOrigin,
    ParsedItem,
    Rarity,
    SourceType,
    VerificationStatus,
)


class SlotScope(str, Enum):
    ANY = "ANY"
    PREFIX = "PREFIX"
    SUFFIX = "SUFFIX"


class SlotConsumptionStatus(str, Enum):
    CONSUMES_SLOT = "CONSUMES_SLOT"
    DOES_NOT_CONSUME_SLOT = "DOES_NOT_CONSUME_SLOT"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class ModifierSlotConsumptionRule:
    origin: ModifierOrigin
    affix_type: AffixType
    status: SlotConsumptionStatus
    provenance: tuple[DataProvenance, ...] = ()
    verification_status: VerificationStatus = VerificationStatus.NEEDS_VERIFICATION
    notes: str | None = None

    def __post_init__(self) -> None:
        if self.verification_status == VerificationStatus.VERIFIED and not self.provenance:
            raise ValueError("VERIFIED slot-consumption rule requires provenance")


@dataclass(frozen=True)
class AffixCapacityDefinition:
    definition_id: str
    item_class: str | None
    rarity: Rarity
    prefix_capacity: int | None
    suffix_capacity: int | None
    exceptions: tuple[str, ...] = ()
    slot_consumption_rules: tuple[ModifierSlotConsumptionRule, ...] = ()
    provenance: tuple[DataProvenance, ...] = ()
    verification_status: VerificationStatus = VerificationStatus.NEEDS_VERIFICATION
    dataset_id: str | None = None

    def __post_init__(self) -> None:
        if not self.definition_id:
            raise ValueError("affix capacity definition_id is required")
        for name in ("prefix_capacity", "suffix_capacity"):
            value = getattr(self, name)
            if value is not None and value < 0:
                raise ValueError(f"{name} cannot be negative")
        if self.verification_status == VerificationStatus.VERIFIED and not self.provenance:
            raise ValueError("VERIFIED affix capacity definition requires provenance")


@dataclass(frozen=True)
class AffixCapacityDatasetSnapshot:
    dataset_id: str
    source: str
    retrieved_at: datetime
    game: str
    game_version: str | None
    definitions: tuple[AffixCapacityDefinition, ...]
    provenance: tuple[DataProvenance, ...] = ()
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.dataset_id:
            raise ValueError("affix capacity dataset_id is required")


@dataclass(frozen=True)
class AffixStateResolution:
    source_item_analysis_id: str
    dataset_id: str
    observed_prefix_count: int
    observed_suffix_count: int
    prefix_capacity: int | None
    suffix_capacity: int | None
    open_prefix_count: int | None
    open_suffix_count: int | None
    confidence: Confidence
    provenance: tuple[DataProvenance, ...] = ()
    warnings: tuple[str, ...] = ()

    def has_open_slot(self, scope: SlotScope = SlotScope.ANY) -> bool | None:
        if scope == SlotScope.PREFIX:
            return None if self.open_prefix_count is None else self.open_prefix_count > 0
        if scope == SlotScope.SUFFIX:
            return None if self.open_suffix_count is None else self.open_suffix_count > 0
        if self.open_prefix_count is None and self.open_suffix_count is None:
            return None
        return (self.open_prefix_count or 0) + (self.open_suffix_count or 0) > 0


class AffixStateResolver:
    def __init__(self, dataset: AffixCapacityDatasetSnapshot):
        self.dataset = dataset

    def resolve(self, item: ParsedItem) -> AffixStateResolution:
        definition = self._definition_for(item)
        warnings: list[str] = []
        provenance: tuple[DataProvenance, ...] = ()
        prefix_capacity = None
        suffix_capacity = None

        if definition is None:
            warnings.append("No affix capacity definition matched item class and rarity.")
        else:
            prefix_capacity = definition.prefix_capacity
            suffix_capacity = definition.suffix_capacity
            provenance = definition.provenance

        prefix_count, suffix_count, slot_warnings = self._count_consuming_modifiers(item, definition)
        warnings.extend(slot_warnings)

        open_prefix_count = None
        open_suffix_count = None
        if prefix_capacity is not None:
            open_prefix_count = prefix_capacity - prefix_count
            if open_prefix_count < 0:
                warnings.append("Observed prefix count exceeds configured prefix capacity.")
        if suffix_capacity is not None:
            open_suffix_count = suffix_capacity - suffix_count
            if open_suffix_count < 0:
                warnings.append("Observed suffix count exceeds configured suffix capacity.")

        level = ConfidenceLevel.MEDIUM if definition is not None and not warnings else ConfidenceLevel.LOW
        return AffixStateResolution(
            source_item_analysis_id=item.analysis_id,
            dataset_id=self.dataset.dataset_id,
            observed_prefix_count=prefix_count,
            observed_suffix_count=suffix_count,
            prefix_capacity=prefix_capacity,
            suffix_capacity=suffix_capacity,
            open_prefix_count=open_prefix_count,
            open_suffix_count=open_suffix_count,
            confidence=Confidence(level=level, reasons=tuple(warnings) or ("Affix capacity derived from source-backed dataset.",)),
            provenance=provenance,
            warnings=tuple(warnings),
        )

    def _definition_for(self, item: ParsedItem) -> AffixCapacityDefinition | None:
        exact = [
            definition
            for definition in self.dataset.definitions
            if definition.rarity == item.rarity and definition.item_class == item.item_class
        ]
        if exact:
            return exact[0]
        generic = [
            definition
            for definition in self.dataset.definitions
            if definition.rarity == item.rarity and definition.item_class is None
        ]
        return generic[0] if generic else None

    def _count_consuming_modifiers(
        self,
        item: ParsedItem,
        definition: AffixCapacityDefinition | None,
    ) -> tuple[int, int, tuple[str, ...]]:
        prefix_count = 0
        suffix_count = 0
        warnings: list[str] = []
        for modifier in item.explicit_modifiers:
            status = _slot_consumption_status(modifier, definition)
            if status == SlotConsumptionStatus.UNKNOWN:
                warnings.append(f"Slot consumption is unknown for {modifier.origin.value} {modifier.affix_type.value}.")
                continue
            if status == SlotConsumptionStatus.DOES_NOT_CONSUME_SLOT:
                continue
            if modifier.affix_type == AffixType.PREFIX:
                prefix_count += 1
            elif modifier.affix_type == AffixType.SUFFIX:
                suffix_count += 1
        return prefix_count, suffix_count, tuple(warnings)


def load_affix_capacity_dataset(path: Path) -> AffixCapacityDatasetSnapshot:
    data = json.loads(path.read_text(encoding="utf-8"), parse_float=Decimal, parse_int=Decimal)
    dataset_id = data["dataset_id"]
    definitions = tuple(_definition(item, dataset_id) for item in data.get("definitions", []))
    return AffixCapacityDatasetSnapshot(
        dataset_id=dataset_id,
        source=data["source"],
        retrieved_at=_parse_datetime(data["retrieved_at"]),
        game=data.get("game", "Path of Exile 2"),
        game_version=data.get("game_version"),
        definitions=definitions,
        provenance=tuple(_provenance(item) for item in data.get("provenance", [])),
        notes=tuple(data.get("notes", [])),
    )


def _definition(data: dict[str, Any], dataset_id: str) -> AffixCapacityDefinition:
    return AffixCapacityDefinition(
        definition_id=data["definition_id"],
        item_class=data.get("item_class"),
        rarity=Rarity[data["rarity"]],
        prefix_capacity=_optional_int(data.get("prefix_capacity")),
        suffix_capacity=_optional_int(data.get("suffix_capacity")),
        exceptions=tuple(data.get("exceptions", [])),
        slot_consumption_rules=tuple(_slot_rule(item) for item in data.get("slot_consumption_rules", [])),
        provenance=tuple(_provenance(item) for item in data.get("provenance", [])),
        verification_status=VerificationStatus[data.get("verification_status", "NEEDS_VERIFICATION")],
        dataset_id=dataset_id,
    )


def _slot_rule(data: dict[str, Any]) -> ModifierSlotConsumptionRule:
    return ModifierSlotConsumptionRule(
        origin=ModifierOrigin[data["origin"]],
        affix_type=AffixType[data["affix_type"]],
        status=SlotConsumptionStatus[data["status"]],
        provenance=tuple(_provenance(item) for item in data.get("provenance", [])),
        verification_status=VerificationStatus[data.get("verification_status", "NEEDS_VERIFICATION")],
        notes=data.get("notes"),
    )


def _slot_consumption_status(
    modifier: ItemModifier,
    definition: AffixCapacityDefinition | None,
) -> SlotConsumptionStatus:
    if modifier.affix_type in {AffixType.IMPLICIT, AffixType.CORRUPTION_ENHANCEMENT}:
        return SlotConsumptionStatus.DOES_NOT_CONSUME_SLOT
    if modifier.affix_type not in {AffixType.PREFIX, AffixType.SUFFIX}:
        return SlotConsumptionStatus.UNKNOWN
    if modifier.origin in {ModifierOrigin.NATURAL, ModifierOrigin.CRAFTED}:
        return SlotConsumptionStatus.CONSUMES_SLOT
    if definition is not None:
        for rule in definition.slot_consumption_rules:
            if rule.origin == modifier.origin and rule.affix_type == modifier.affix_type:
                return rule.status
    return SlotConsumptionStatus.UNKNOWN


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


def _optional_int(value: Any) -> int | None:
    return None if value is None else int(value)
