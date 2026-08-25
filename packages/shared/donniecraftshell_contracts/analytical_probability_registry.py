"""Offline verified-mechanic registry for analytical probability rules.

This module loads curated local JSON evidence into AnalyticalProbabilityRule
objects. It never scrapes sources and never promotes non-VERIFIED evidence.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .craft_outcomes import OutcomeSelectionRule, OutcomeSpaceCompleteness
from .domain import DataProvenance, SourceType, VerificationStatus
from .probability import AnalyticalProbabilityRule, AnalyticalProbabilityRuleType, ProbabilityType


ANALYTICAL_MECHANIC_REGISTRY_VERSION = "dc-analytical-mechanic-registry-v1"


@dataclass(frozen=True)
class AnalyticalMechanicRegistry:
    dataset_id: str
    rules: tuple[AnalyticalProbabilityRule, ...]
    skipped_rule_ids: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    @classmethod
    def empty(cls, dataset_id: str = "analytical-mechanic-registry-empty") -> "AnalyticalMechanicRegistry":
        return cls(dataset_id=dataset_id, rules=())

    @classmethod
    def from_json_files(cls, paths: tuple[str | Path, ...]) -> "AnalyticalMechanicRegistry":
        if not paths:
            return cls.empty()
        rules: list[AnalyticalProbabilityRule] = []
        skipped: list[str] = []
        warnings: list[str] = []
        dataset_ids: list[str] = []
        for path in paths:
            try:
                payload = json.loads(Path(path).read_text(encoding="utf-8"))
            except Exception as exc:
                dataset_ids.append(str(path))
                warnings.append(f"Analytical mechanic registry could not be read and was skipped: {exc}")
                continue
            dataset_id, loaded_rules, loaded_skipped, loaded_warnings = _rules_from_payload(
                payload,
                source_path=Path(path),
            )
            dataset_ids.append(dataset_id)
            rules.extend(loaded_rules)
            skipped.extend(loaded_skipped)
            warnings.extend(loaded_warnings)
        unique_rules, duplicate_skipped, duplicate_warnings = _dedupe_rules(tuple(rules))
        return cls(
            dataset_id="+".join(dataset_ids),
            rules=unique_rules,
            skipped_rule_ids=tuple((*skipped, *duplicate_skipped)),
            warnings=tuple((*warnings, *duplicate_warnings)),
        )


def load_analytical_mechanic_registry(path: str | Path) -> AnalyticalMechanicRegistry:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception as exc:
        return AnalyticalMechanicRegistry(
            dataset_id=str(path),
            rules=(),
            warnings=(f"Analytical mechanic registry could not be read and was skipped: {exc}",),
        )
    return analytical_mechanic_registry_from_dict(payload, source_path=Path(path))


def analytical_mechanic_registry_from_dict(
    payload: dict[str, Any],
    source_path: Path | None = None,
) -> AnalyticalMechanicRegistry:
    dataset_id, rules, skipped, warnings = _rules_from_payload(payload, source_path=source_path)
    unique_rules, duplicate_skipped, duplicate_warnings = _dedupe_rules(tuple(rules))
    return AnalyticalMechanicRegistry(
        dataset_id=dataset_id,
        rules=unique_rules,
        skipped_rule_ids=tuple((*skipped, *duplicate_skipped)),
        warnings=tuple((*warnings, *duplicate_warnings)),
    )


def _rules_from_payload(
    payload: dict[str, Any],
    source_path: Path | None = None,
) -> tuple[str, tuple[AnalyticalProbabilityRule, ...], tuple[str, ...], tuple[str, ...]]:
    if not isinstance(payload, dict):
        return (
            str(source_path or "unknown"),
            (),
            (),
            ("Analytical mechanic registry root must be an object; registry was skipped.",),
        )
    dataset_id = str(payload.get("dataset_id") or source_path or "unknown-analytical-mechanic-registry")
    if payload.get("registry_version") != ANALYTICAL_MECHANIC_REGISTRY_VERSION:
        return (
            dataset_id,
            (),
            (),
            ("Analytical mechanic registry_version is missing or incompatible; registry was skipped.",),
        )
    records = payload.get("rules", ())
    if not isinstance(records, list):
        return (
            dataset_id,
            (),
            (),
            ("Analytical mechanic registry rules must be a list; registry was skipped.",),
        )
    rules: list[AnalyticalProbabilityRule] = []
    skipped: list[str] = []
    warnings: list[str] = []
    for index, record in enumerate(records, start=1):
        rule_id = _record_rule_id(record, index)
        try:
            rule = analytical_probability_rule_from_record(record, default_dataset_id=dataset_id)
        except Exception as exc:
            skipped.append(rule_id)
            warnings.append(f"Analytical mechanic rule {rule_id} was skipped: {exc}")
            continue
        rules.append(rule)
    return dataset_id, tuple(rules), tuple(skipped), tuple(warnings)


def analytical_probability_rule_from_record(
    record: dict[str, Any],
    default_dataset_id: str | None = None,
) -> AnalyticalProbabilityRule:
    if not isinstance(record, dict):
        raise ValueError("rule record must be an object")
    provenance = tuple(_provenance(item) for item in record.get("provenance", ()))
    return AnalyticalProbabilityRule(
        rule_id=str(record["rule_id"]),
        action_id=str(record["action_id"]),
        rule_type=AnalyticalProbabilityRuleType(str(record["rule_type"])),
        methodology=str(record["methodology"]),
        provenance=provenance,
        probability_type=ProbabilityType(record.get("probability_type", ProbabilityType.EXACT_MECHANICAL.value)),
        required_selection_rule=(
            OutcomeSelectionRule(record["required_selection_rule"])
            if record.get("required_selection_rule") is not None
            else None
        ),
        required_outcome_space_completeness=OutcomeSpaceCompleteness(
            record.get("required_outcome_space_completeness", OutcomeSpaceCompleteness.COMPLETE.value)
        ),
        expected_source_outcome_set_id=record.get("expected_source_outcome_set_id"),
        expected_outcome_ids=(
            tuple(str(value) for value in record["expected_outcome_ids"])
            if record.get("expected_outcome_ids") is not None
            else None
        ),
        game_version=record.get("game_version"),
        crafting_dataset_version=record.get("crafting_dataset_version"),
        modifier_dataset_version=record.get("modifier_dataset_version"),
        evidence_dataset_version=record.get("evidence_dataset_version") or default_dataset_id,
        verification_status=VerificationStatus(record.get("verification_status", VerificationStatus.NEEDS_VERIFICATION.value)),
        warnings=tuple(str(value) for value in record.get("warnings", ())),
    )


def _provenance(record: dict[str, Any]) -> DataProvenance:
    if not isinstance(record, dict):
        raise ValueError("provenance entry must be an object")
    return DataProvenance(
        source_id=str(record["source_id"]),
        source_type=SourceType(record["source_type"]),
        source_uri=record.get("source_uri"),
        retrieved_at=_datetime(record.get("retrieved_at")),
        game_version=record.get("game_version"),
        league=record.get("league"),
        verification_status=VerificationStatus(record.get("verification_status", VerificationStatus.NEEDS_VERIFICATION.value)),
        notes=record.get("notes"),
    )


def _dedupe_rules(rules: tuple[AnalyticalProbabilityRule, ...]) -> tuple[tuple[AnalyticalProbabilityRule, ...], tuple[str, ...], tuple[str, ...]]:
    duplicate_rule_ids = {rule.rule_id for rule in rules if sum(1 for item in rules if item.rule_id == rule.rule_id) > 1}
    duplicate_action_ids = {rule.action_id for rule in rules if sum(1 for item in rules if item.action_id == rule.action_id) > 1}
    skipped = tuple(rule.rule_id for rule in rules if rule.rule_id in duplicate_rule_ids or rule.action_id in duplicate_action_ids)
    warnings: list[str] = []
    if duplicate_rule_ids:
        warnings.append(f"Duplicate analytical mechanic rule IDs were skipped: {', '.join(sorted(duplicate_rule_ids))}.")
    if duplicate_action_ids:
        warnings.append(f"Duplicate analytical mechanic action scopes were skipped: {', '.join(sorted(duplicate_action_ids))}.")
    accepted = tuple(rule for rule in rules if rule.rule_id not in duplicate_rule_ids and rule.action_id not in duplicate_action_ids)
    return accepted, skipped, tuple(warnings)


def _record_rule_id(record: Any, index: int) -> str:
    if isinstance(record, dict) and record.get("rule_id"):
        return str(record["rule_id"])
    return f"#{index}"


def _datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
