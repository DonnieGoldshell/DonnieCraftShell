"""Compose crafting applicability with economy material costs.

This layer produces action candidates for UI/Advisor plumbing. It does not
rank actions, choose a winner, simulate outcomes, or calculate EV.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .affix_capacity import AffixStateResolution
from .crafting_actions import (
    CraftActionApplicability,
    CraftActionDefinition,
    CraftActionEngine,
    RequiredMaterial,
)
from .domain import ParsedItem
from .economy import FreshnessState
from .economy_costs import (
    CraftMaterialCost,
    CraftMaterialRequirement,
    calculate_craft_material_cost,
)
from .economy_repository import EconomyRepository


@dataclass(frozen=True)
class CraftActionCandidate:
    action: CraftActionDefinition
    applicability: CraftActionApplicability
    required_materials: tuple[RequiredMaterial, ...]
    material_cost: CraftMaterialCost
    cost_complete: bool
    cost_freshness: FreshnessState
    warnings: tuple[str, ...] = ()


class CraftActionCostService:
    def __init__(self, repository: EconomyRepository):
        self.repository = repository

    def cost_action(
        self,
        action: CraftActionDefinition,
        league: str,
        as_of: datetime,
    ) -> CraftMaterialCost:
        requirements = tuple(
            CraftMaterialRequirement(material.asset_id, material.quantity)
            for material in action.required_materials
        )
        return calculate_craft_material_cost(self.repository, league, requirements, as_of)


def get_action_candidates(
    item: ParsedItem,
    affix_state_resolution: AffixStateResolution | None,
    craft_action_engine: CraftActionEngine,
    economy_repository: EconomyRepository,
    league: str,
    as_of: datetime,
) -> tuple[CraftActionCandidate, ...]:
    cost_service = CraftActionCostService(economy_repository)
    candidates: list[CraftActionCandidate] = []
    for action in craft_action_engine.dataset.actions:
        applicability = craft_action_engine.evaluate_action(action, item, affix_state_resolution)
        material_cost = cost_service.cost_action(action, league, as_of)
        warnings = (*applicability.unknown_preconditions, *material_cost.warnings)
        candidates.append(
            CraftActionCandidate(
                action=action,
                applicability=applicability,
                required_materials=action.required_materials,
                material_cost=material_cost,
                cost_complete=material_cost.complete,
                cost_freshness=material_cost.freshness,
                warnings=warnings,
            )
        )
    return tuple(candidates)
