"""Dependency assembly for Advisor analysis."""

from __future__ import annotations

from functools import lru_cache

from packages.shared.donniecraftshell_contracts.advisor_orchestration import CraftAdvisorOrchestrator
from packages.shared.donniecraftshell_contracts.affix_capacity import AffixStateResolver, load_affix_capacity_dataset
from packages.shared.donniecraftshell_contracts.crafting_actions import CraftActionEngine, load_crafting_dataset
from packages.shared.donniecraftshell_contracts.economy_repository import EconomyRepository
from packages.shared.donniecraftshell_contracts.empirical_probability import (
    EmpiricalProbabilityDatasetRegistry,
    EmpiricalProbabilityRegistryProvider,
    EmpiricalProbabilityRepository,
)
from packages.shared.donniecraftshell_contracts.game_data_repository import GameDataRepository
from packages.shared.donniecraftshell_contracts.poe_show_economy import load_normalized_economy_snapshot
from packages.shared.donniecraftshell_contracts.probability import ProbabilityProvider

from services.api.app.config import ApiSettings, get_settings


@lru_cache(maxsize=1)
def get_cached_settings() -> ApiSettings:
    return get_settings()


@lru_cache(maxsize=1)
def get_economy_repository() -> EconomyRepository:
    settings = get_cached_settings()
    return EconomyRepository(tuple(load_normalized_economy_snapshot(path) for path in settings.economy_snapshot_paths))


@lru_cache(maxsize=1)
def get_empirical_probability_registry() -> EmpiricalProbabilityDatasetRegistry:
    settings = get_cached_settings()
    repository = EmpiricalProbabilityRepository.from_json_files(
        settings.empirical_probability_dataset_paths,
        allow_synthetic=False,
    )
    return EmpiricalProbabilityDatasetRegistry.from_repository(repository)


@lru_cache(maxsize=1)
def get_probability_provider() -> ProbabilityProvider:
    return EmpiricalProbabilityRegistryProvider(
        get_empirical_probability_registry(),
        allow_synthetic=False,
    )


@lru_cache(maxsize=1)
def get_advisor_orchestrator() -> CraftAdvisorOrchestrator:
    settings = get_cached_settings()
    return CraftAdvisorOrchestrator(
        game_data_repository=GameDataRepository.from_json_files((settings.default_game_data_path,)),
        affix_state_resolver=AffixStateResolver(load_affix_capacity_dataset(settings.default_affix_capacity_path)),
        craft_action_engine=CraftActionEngine(load_crafting_dataset(settings.default_crafting_path)),
        economy_repository=get_economy_repository(),
        probability_provider=get_probability_provider(),
    )
