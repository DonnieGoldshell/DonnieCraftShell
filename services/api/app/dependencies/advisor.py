"""Dependency assembly for Advisor analysis."""

from __future__ import annotations

from functools import lru_cache

from packages.shared.donniecraftshell_contracts.advisor_orchestration import CraftAdvisorOrchestrator
from packages.shared.donniecraftshell_contracts.affix_capacity import AffixStateResolver, load_affix_capacity_dataset
from packages.shared.donniecraftshell_contracts.analytical_probability_registry import AnalyticalMechanicRegistry
from packages.shared.donniecraftshell_contracts.crafting_actions import CraftActionEngine, load_crafting_dataset
from packages.shared.donniecraftshell_contracts.economy_repository import EconomyRepository
from packages.shared.donniecraftshell_contracts.economy_quote_workspace import (
    EconomyQuoteWorkspaceRepository,
    FileBackedEconomyQuoteWorkspaceRepository,
)
from packages.shared.donniecraftshell_contracts.empirical_probability import (
    EmpiricalProbabilityDatasetRegistry,
    EmpiricalProbabilityRegistryProvider,
    EmpiricalProbabilityRepository,
    FileBackedEmpiricalProbabilityDatasetRegistry,
)
from packages.shared.donniecraftshell_contracts.game_data_repository import GameDataRepository
from packages.shared.donniecraftshell_contracts.manual_valuation_workspace import (
    FileBackedManualValuationWorkspaceRepository,
    ManualValuationWorkspaceRepository,
)
from packages.shared.donniecraftshell_contracts.observation_workspace import (
    FileBackedObservationWorkspaceRepository,
    ObservationWorkspaceRepository,
)
from packages.shared.donniecraftshell_contracts.poe_show_economy import load_normalized_economy_snapshot
from packages.shared.donniecraftshell_contracts.probability import (
    AnalyticalProbabilityProvider,
    CompositeProbabilityProvider,
    ProbabilityProvider,
)

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
    if settings.empirical_registry_storage_path is not None:
        return FileBackedEmpiricalProbabilityDatasetRegistry.from_repository(
            repository,
            settings.empirical_registry_storage_path,
        )
    return EmpiricalProbabilityDatasetRegistry.from_repository(repository)


@lru_cache(maxsize=1)
def get_analytical_mechanic_registry() -> AnalyticalMechanicRegistry:
    settings = get_cached_settings()
    return AnalyticalMechanicRegistry.from_json_files(settings.analytical_mechanic_registry_paths)


@lru_cache(maxsize=1)
def get_observation_workspace() -> ObservationWorkspaceRepository:
    settings = get_cached_settings()
    if settings.observation_workspace_storage_path is not None:
        return FileBackedObservationWorkspaceRepository(settings.observation_workspace_storage_path)
    return ObservationWorkspaceRepository()


@lru_cache(maxsize=1)
def get_manual_valuation_workspace() -> ManualValuationWorkspaceRepository:
    settings = get_cached_settings()
    if settings.manual_valuation_workspace_storage_path is not None:
        return FileBackedManualValuationWorkspaceRepository(settings.manual_valuation_workspace_storage_path)
    return ManualValuationWorkspaceRepository()


@lru_cache(maxsize=1)
def get_economy_quote_workspace() -> EconomyQuoteWorkspaceRepository:
    settings = get_cached_settings()
    if settings.economy_quote_workspace_storage_path is not None:
        return FileBackedEconomyQuoteWorkspaceRepository(settings.economy_quote_workspace_storage_path)
    return EconomyQuoteWorkspaceRepository()


@lru_cache(maxsize=1)
def get_probability_provider() -> ProbabilityProvider:
    analytical_registry = get_analytical_mechanic_registry()
    empirical_provider = EmpiricalProbabilityRegistryProvider(
        get_empirical_probability_registry(),
        allow_synthetic=False,
    )
    return CompositeProbabilityProvider(
        (
            AnalyticalProbabilityProvider(
                analytical_registry.rules,
                load_warnings=analytical_registry.warnings,
            ),
            empirical_provider,
        )
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
