"""Manual empirical craft observation recorder contracts.

The recorder collects evidence only. It does not calculate probabilities,
valuation, EV, or Advisor recommendations.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from .craft_outcomes import CraftOutcomeOperation, CraftOutcomeSet, HypotheticalItemState
from .domain import DataProvenance, ParsedItem, SourceType, VerificationStatus
from .empirical_observation_import import EmpiricalCraftingObservation


OBSERVATION_RECORDER_VERSION = "dc-observation-recorder-v1"


class ObservationClassificationMethod(str, Enum):
    AUTOMATIC = "AUTOMATIC"
    MANUAL = "MANUAL"
    UNCLASSIFIED = "UNCLASSIFIED"


@dataclass(frozen=True)
class ObservationClassification:
    method: ObservationClassificationMethod
    outcome_id: str | None = None
    reason: str = ""
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.method == ObservationClassificationMethod.UNCLASSIFIED and self.outcome_id is not None:
            raise ValueError("unclassified observations must not include outcome_id")
        if self.method in {
            ObservationClassificationMethod.AUTOMATIC,
            ObservationClassificationMethod.MANUAL,
        } and not self.outcome_id:
            raise ValueError(f"{self.method.value} classification requires outcome_id")


@dataclass(frozen=True)
class ObservationDraft:
    action_id: str
    source_outcome_set_id: str
    item_class: str
    league: str
    before_item: ParsedItem
    after_item: ParsedItem
    observed_at: datetime
    source_id: str
    game: str = "Path of Exile 2"
    game_version: str | None = None
    crafting_dataset_version: str | None = None
    modifier_dataset_version: str | None = None
    source_uri: str | None = None
    synthetic: bool = False
    verification_status: VerificationStatus = VerificationStatus.NEEDS_VERIFICATION
    provenance: tuple[DataProvenance, ...] = ()
    notes: str | None = None

    def __post_init__(self) -> None:
        required = {
            "action_id": self.action_id,
            "source_outcome_set_id": self.source_outcome_set_id,
            "item_class": self.item_class,
            "league": self.league,
            "source_id": self.source_id,
            "game": self.game,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError(f"observation draft missing required fields: {', '.join(missing)}")
        if self.observed_at.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")


@dataclass(frozen=True)
class RecordedCraftObservation:
    raw_record_id: str
    draft: ObservationDraft
    classification: ObservationClassification
    before_item_fingerprint: str
    after_item_fingerprint: str
    warnings: tuple[str, ...] = ()

    def to_empirical_observation(self) -> EmpiricalCraftingObservation:
        return EmpiricalCraftingObservation(
            raw_record_id=self.raw_record_id,
            action_id=self.draft.action_id,
            source_outcome_set_id=self.draft.source_outcome_set_id,
            item_class=self.draft.item_class,
            league=self.draft.league,
            observed_at=self.draft.observed_at,
            source_id=self.draft.source_id,
            source_type=SourceType.MANUAL_RESEARCH,
            outcome_id=self.classification.outcome_id,
            unclassified=self.classification.method == ObservationClassificationMethod.UNCLASSIFIED,
            game=self.draft.game,
            game_version=self.draft.game_version,
            crafting_dataset_version=self.draft.crafting_dataset_version,
            modifier_dataset_version=self.draft.modifier_dataset_version,
            source_uri=self.draft.source_uri,
            synthetic=self.draft.synthetic,
            notes=self._notes(),
            verification_status=self.draft.verification_status,
        )

    def to_export_record(self) -> dict[str, Any]:
        observation = self.to_empirical_observation()
        return {
            "raw_record_id": observation.raw_record_id,
            "action_id": observation.action_id,
            "source_outcome_set_id": observation.source_outcome_set_id,
            "item_class": observation.item_class,
            "league": observation.league,
            "game": observation.game,
            "game_version": observation.game_version,
            "crafting_dataset_version": observation.crafting_dataset_version,
            "modifier_dataset_version": observation.modifier_dataset_version,
            "observed_at": observation.observed_at.isoformat(),
            "source_id": observation.source_id,
            "source_type": observation.source_type.value,
            "source_uri": observation.source_uri,
            "synthetic": observation.synthetic,
            "outcome_id": observation.outcome_id,
            "unclassified": observation.unclassified,
            "verification_status": observation.verification_status.value,
            "notes": observation.notes,
            "classification_method": self.classification.method.value,
            "classification_reason": self.classification.reason,
            "classification_warnings": list(self.classification.warnings),
            "before_item_fingerprint": self.before_item_fingerprint,
            "after_item_fingerprint": self.after_item_fingerprint,
            "before_raw_clipboard_text": self.draft.before_item.raw_clipboard_text,
            "after_raw_clipboard_text": self.draft.after_item.raw_clipboard_text,
            "recorder_version": OBSERVATION_RECORDER_VERSION,
            "warnings": list(self.warnings),
        }

    def _notes(self) -> str:
        parts = [
            f"Recorder={OBSERVATION_RECORDER_VERSION}",
            f"classification_method={self.classification.method.value}",
            f"classification_reason={self.classification.reason}",
            f"before_fingerprint={self.before_item_fingerprint}",
            f"after_fingerprint={self.after_item_fingerprint}",
        ]
        if self.draft.notes:
            parts.append(self.draft.notes)
        return "; ".join(parts)


@dataclass(frozen=True)
class ObservationExportPayload:
    recorder_version: str
    exported_at: datetime
    observations: tuple[dict[str, Any], ...]
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "recorder_version": self.recorder_version,
            "exported_at": self.exported_at.isoformat(),
            "observations": list(self.observations),
            "warnings": list(self.warnings),
        }


class CraftObservationRecorder:
    def classify_automatically(
        self,
        before_item: ParsedItem,
        after_item: ParsedItem,
        outcome_set: CraftOutcomeSet,
    ) -> ObservationClassification:
        before = tuple(modifier.raw_text for modifier in before_item.explicit_modifiers)
        after = tuple(modifier.raw_text for modifier in after_item.explicit_modifiers)
        removed = sorted(set(before) - set(after))
        added = sorted(set(after) - set(before))
        if len(removed) != 1 or added:
            return ObservationClassification(
                method=ObservationClassificationMethod.UNCLASSIFIED,
                reason="Before/after state does not map to exactly one supported explicit modifier removal.",
                warnings=("Automatic classification is limited to single explicit removal outcomes.",),
            )

        matching = tuple(
            state
            for state in outcome_set.hypothetical_states
            if _state_removes_exact_modifier(state, removed[0])
        )
        if len(matching) == 1:
            return ObservationClassification(
                method=ObservationClassificationMethod.AUTOMATIC,
                outcome_id=matching[0].outcome_id,
                reason="After item uniquely matches one existing outcome by removed explicit modifier.",
            )
        if len(matching) > 1:
            return ObservationClassification(
                method=ObservationClassificationMethod.UNCLASSIFIED,
                reason="Before/after state matched multiple possible outcome IDs.",
                warnings=("Ambiguous classification was preserved as unclassified.",),
            )
        return ObservationClassification(
            method=ObservationClassificationMethod.UNCLASSIFIED,
            reason="Removed modifier did not match any existing outcome ID.",
        )

    def classify_manually(
        self,
        outcome_id: str | None,
        allowed_outcome_ids: tuple[str, ...],
        reason: str,
    ) -> ObservationClassification:
        if not outcome_id:
            return ObservationClassification(
                method=ObservationClassificationMethod.UNCLASSIFIED,
                reason=reason or "User recorded this craft as unclassified.",
            )
        if outcome_id not in allowed_outcome_ids:
            return ObservationClassification(
                method=ObservationClassificationMethod.UNCLASSIFIED,
                reason="Manual outcome ID was not present in the supplied outcome set.",
                warnings=("Manual classification was rejected and recorded as unclassified.",),
            )
        return ObservationClassification(
            method=ObservationClassificationMethod.MANUAL,
            outcome_id=outcome_id,
            reason=reason or "User explicitly selected this outcome ID.",
        )

    def record(self, draft: ObservationDraft, classification: ObservationClassification) -> RecordedCraftObservation:
        before_fingerprint = item_fingerprint(draft.before_item)
        after_fingerprint = item_fingerprint(draft.after_item)
        raw_record_id = raw_record_id_for_draft(draft, classification, before_fingerprint, after_fingerprint)
        warnings = tuple(
            warning
            for warning in (
                "Recorded observation is synthetic/test-only." if draft.synthetic else "",
                "Observation does not make probability evidence complete by itself.",
            )
            if warning
        )
        return RecordedCraftObservation(
            raw_record_id=raw_record_id,
            draft=draft,
            classification=classification,
            before_item_fingerprint=before_fingerprint,
            after_item_fingerprint=after_fingerprint,
            warnings=warnings,
        )

    def export(self, records: tuple[RecordedCraftObservation, ...], exported_at: datetime | None = None) -> ObservationExportPayload:
        exported_at = exported_at or datetime.now(timezone.utc)
        return ObservationExportPayload(
            recorder_version=OBSERVATION_RECORDER_VERSION,
            exported_at=exported_at,
            observations=tuple(record.to_export_record() for record in records),
            warnings=("Recorder exports are raw observations; import/readiness gates still apply.",),
        )


def item_fingerprint(item: ParsedItem) -> str:
    payload = "|".join(
        (
            item.raw_clipboard_text,
            item.item_class or "",
            item.base_type or "",
            item.rarity.value,
            str(item.item_level or ""),
            "|".join(modifier.raw_text for modifier in item.modifiers),
        )
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def raw_record_id_for_draft(
    draft: ObservationDraft,
    classification: ObservationClassification,
    before_fingerprint: str,
    after_fingerprint: str,
) -> str:
    payload = "|".join(
        (
            draft.action_id,
            draft.source_outcome_set_id,
            draft.item_class,
            draft.league,
            draft.observed_at.isoformat(),
            before_fingerprint,
            after_fingerprint,
            classification.method.value,
            classification.outcome_id or "UNCLASSIFIED",
        )
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]
    return f"manual-craft-observation-{digest}"


def _state_removes_exact_modifier(state: HypotheticalItemState, raw_modifier_text: str) -> bool:
    removed = tuple(
        delta.removed_modifier.raw_text
        for delta in state.deltas
        if delta.operation == CraftOutcomeOperation.REMOVE_MODIFIER and delta.removed_modifier is not None
    )
    return removed == (raw_modifier_text,)
