"""Guided real-trial capture contracts for empirical craft observations.

This module helps operators collect real before/after trial evidence. It does
not classify evidence silently, calculate probabilities, or automate gameplay.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from .craft_outcomes import CraftOutcomeSet
from .domain import ItemModifier, ParsedItem
from .observation_recorder import (
    CraftObservationRecorder,
    OBSERVATION_RECORDER_VERSION,
    ObservationClassification,
    ObservationClassificationMethod,
)


GUIDED_CAPTURE_VERSION = "dc-guided-observation-capture-v1"


class GuidedTrialPreviewStatus(str, Enum):
    PROPOSED_OUTCOME = "PROPOSED_OUTCOME"
    UNCLASSIFIED = "UNCLASSIFIED"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class GuidedCaptureSessionContext:
    action_id: str
    item_class: str
    league: str
    game: str
    game_version: str
    crafting_dataset_version: str
    modifier_dataset_version: str
    source_id: str
    source_uri: str
    collection_method: str = "MANUAL_BEFORE_AFTER_PASTE"
    notes: str | None = None

    def __post_init__(self) -> None:
        required = {
            "action_id": self.action_id,
            "item_class": self.item_class,
            "league": self.league,
            "game": self.game,
            "game_version": self.game_version,
            "crafting_dataset_version": self.crafting_dataset_version,
            "modifier_dataset_version": self.modifier_dataset_version,
            "source_id": self.source_id,
            "source_uri": self.source_uri,
            "collection_method": self.collection_method,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError(f"guided observation capture session missing required fields: {', '.join(missing)}")


@dataclass(frozen=True)
class GuidedTrialModifierDiff:
    raw_text: str
    affix_type: str
    origin: str
    display_name: str | None = None
    tier: str | None = None


@dataclass(frozen=True)
class GuidedTrialDiff:
    removed_modifiers: tuple[GuidedTrialModifierDiff, ...]
    added_modifiers: tuple[GuidedTrialModifierDiff, ...]


@dataclass(frozen=True)
class GuidedTrialPreview:
    capture_version: str
    session_id: str
    trial_id: str
    status: GuidedTrialPreviewStatus
    action_id: str
    source_outcome_set_id: str
    proposed_outcome_id: str | None
    classification_reason: str
    requires_operator_confirmation: bool
    before_item_fingerprint: str
    after_item_fingerprint: str
    before_raw_sha256: str
    after_raw_sha256: str
    diff: GuidedTrialDiff
    warnings: tuple[str, ...] = ()


def preview_guided_trial(
    session: GuidedCaptureSessionContext,
    before_item: ParsedItem,
    after_item: ParsedItem,
    outcome_set: CraftOutcomeSet,
    observed_at: datetime,
) -> GuidedTrialPreview:
    before_fingerprint = CraftObservationRecorderFingerprint.item(before_item)
    after_fingerprint = CraftObservationRecorderFingerprint.item(after_item)
    diff = explicit_modifier_diff(before_item, after_item)
    classification = CraftObservationRecorder().classify_automatically(before_item, after_item, outcome_set)
    status = (
        GuidedTrialPreviewStatus.PROPOSED_OUTCOME
        if classification.method == ObservationClassificationMethod.AUTOMATIC and classification.outcome_id
        else GuidedTrialPreviewStatus.UNCLASSIFIED
    )
    warnings = tuple(
        warning
        for warning in (
            *classification.warnings,
            "Operator confirmation is required before this trial can enter the observation workspace.",
            "Guided capture does not change probability readiness by itself.",
        )
        if warning
    )
    return GuidedTrialPreview(
        capture_version=GUIDED_CAPTURE_VERSION,
        session_id=guided_session_id(session),
        trial_id=guided_trial_id(session, before_fingerprint, after_fingerprint, observed_at),
        status=status,
        action_id=session.action_id,
        source_outcome_set_id=outcome_set_source_id(outcome_set),
        proposed_outcome_id=classification.outcome_id,
        classification_reason=classification.reason,
        requires_operator_confirmation=True,
        before_item_fingerprint=before_fingerprint,
        after_item_fingerprint=after_fingerprint,
        before_raw_sha256=_sha256(before_item.raw_clipboard_text),
        after_raw_sha256=_sha256(after_item.raw_clipboard_text),
        diff=diff,
        warnings=warnings,
    )


def confirmed_guided_classification(
    preview: GuidedTrialPreview,
    *,
    operator_confirmed: bool,
    confirmed_outcome_id: str | None,
    confirm_unclassified: bool = False,
    reason: str | None = None,
) -> ObservationClassification:
    if not operator_confirmed:
        raise ValueError("operator confirmation is required before saving guided observation evidence")
    if confirm_unclassified:
        return ObservationClassification(
            method=ObservationClassificationMethod.UNCLASSIFIED,
            reason=reason or "Operator confirmed this guided trial should remain unclassified.",
            warnings=("Unclassified guided trial remains in review but does not add a classified outcome count.",),
        )
    if not confirmed_outcome_id:
        raise ValueError("confirmed_outcome_id is required unless confirm_unclassified is true")
    if preview.status != GuidedTrialPreviewStatus.PROPOSED_OUTCOME or preview.proposed_outcome_id != confirmed_outcome_id:
        raise ValueError("confirmed_outcome_id must match the guided preview proposal")
    return ObservationClassification(
        method=ObservationClassificationMethod.MANUAL,
        outcome_id=confirmed_outcome_id,
        reason=reason or "Operator explicitly confirmed the guided before/after outcome proposal.",
    )


def explicit_modifier_diff(before_item: ParsedItem, after_item: ParsedItem) -> GuidedTrialDiff:
    before_counts = Counter(modifier.raw_text for modifier in before_item.explicit_modifiers)
    after_counts = Counter(modifier.raw_text for modifier in after_item.explicit_modifiers)
    before_by_raw = {modifier.raw_text: modifier for modifier in before_item.explicit_modifiers}
    after_by_raw = {modifier.raw_text: modifier for modifier in after_item.explicit_modifiers}
    removed = []
    added = []
    for raw_text in sorted(before_counts):
        for _ in range(max(0, before_counts[raw_text] - after_counts.get(raw_text, 0))):
            removed.append(_modifier_diff(before_by_raw[raw_text]))
    for raw_text in sorted(after_counts):
        for _ in range(max(0, after_counts[raw_text] - before_counts.get(raw_text, 0))):
            added.append(_modifier_diff(after_by_raw[raw_text]))
    return GuidedTrialDiff(tuple(removed), tuple(added))


def guided_session_id(session: GuidedCaptureSessionContext) -> str:
    payload = "|".join(
        (
            session.action_id,
            session.item_class,
            session.league,
            session.game,
            session.game_version,
            session.crafting_dataset_version,
            session.modifier_dataset_version,
            session.source_id,
            session.source_uri,
            session.collection_method,
        )
    )
    return f"guided-observation-session-{hashlib.sha256(payload.encode('utf-8')).hexdigest()[:24]}"


def guided_trial_id(
    session: GuidedCaptureSessionContext,
    before_item_fingerprint: str,
    after_item_fingerprint: str,
    observed_at: datetime,
) -> str:
    payload = "|".join((guided_session_id(session), observed_at.isoformat(), before_item_fingerprint, after_item_fingerprint))
    return f"guided-observation-trial-{hashlib.sha256(payload.encode('utf-8')).hexdigest()[:24]}"


def outcome_set_source_id(outcome_set: CraftOutcomeSet) -> str:
    payload = "|".join(
        (
            outcome_set.action_id,
            outcome_set.outcome_space_completeness.value,
            *(state.outcome_id for state in sorted(outcome_set.hypothetical_states, key=lambda item: item.outcome_id)),
        )
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]
    return f"backend-outcome-set:{outcome_set.action_id}:{digest}"


class CraftObservationRecorderFingerprint:
    @staticmethod
    def item(item: ParsedItem) -> str:
        from .observation_recorder import item_fingerprint

        return item_fingerprint(item)


def _modifier_diff(modifier: ItemModifier) -> GuidedTrialModifierDiff:
    return GuidedTrialModifierDiff(
        raw_text=modifier.raw_text,
        affix_type=modifier.affix_type.value,
        origin=modifier.origin.value,
        display_name=modifier.display_name,
        tier=modifier.tier,
    )


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
