"""JSON-backed normalized game-data repository."""

from __future__ import annotations

from pathlib import Path

from .domain import AffixType
from .game_data import ModifierApplicability, ModifierFamily, ModifierTierDefinition
from .game_data_import import NormalizedGameDataSet, load_normalized_dataset


class GameDataRepository:
    def __init__(self, datasets: dict[str, NormalizedGameDataSet]):
        self._datasets = datasets

    @classmethod
    def from_json_files(cls, paths: tuple[Path, ...]) -> "GameDataRepository":
        datasets = {}
        for path in paths:
            dataset = load_normalized_dataset(path)
            datasets[dataset.dataset_version] = dataset
        return cls(datasets)

    def get_dataset(self, dataset_version: str) -> NormalizedGameDataSet:
        try:
            return self._datasets[dataset_version]
        except KeyError as exc:
            raise KeyError(f"unknown dataset_version: {dataset_version}") from exc

    def candidates_for_modifier(
        self,
        dataset_version: str,
        item_class: str | None,
        affix_type: AffixType,
        display_name: str | None,
        tier: str | None,
    ) -> tuple[tuple[ModifierTierDefinition, ModifierFamily, tuple[ModifierApplicability, ...]], ...]:
        dataset = self.get_dataset(dataset_version)
        families = {family.canonical_id: family for family in dataset.modifier_families}
        applicability_by_modifier: dict[str, list[ModifierApplicability]] = {}
        for applicability in dataset.modifier_applicability:
            applicability_by_modifier.setdefault(applicability.modifier_id, []).append(applicability)
        matches = []
        for modifier_tier in dataset.modifier_tiers:
            family = families[modifier_tier.modifier_family_id]
            applicability = tuple(applicability_by_modifier.get(modifier_tier.canonical_id, []))
            if display_name and modifier_tier.display_name != display_name:
                continue
            if tier and modifier_tier.tier != tier:
                continue
            if affix_type != AffixType.UNKNOWN and family.affix_type != affix_type:
                continue
            if item_class and applicability and not any(item.item_class == item_class for item in applicability):
                continue
            matches.append((modifier_tier, family, applicability))
        return tuple(matches)
