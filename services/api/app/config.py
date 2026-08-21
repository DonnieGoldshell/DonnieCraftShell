"""Explicit API configuration for local/offline DonnieCraftShell services."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class ApiSettings:
    environment: str
    default_game_data_dataset_id: str
    default_game_data_path: Path
    default_crafting_dataset_id: str
    default_crafting_path: Path
    default_affix_capacity_dataset_id: str
    default_affix_capacity_path: Path
    economy_snapshot_paths: tuple[Path, ...]
    empirical_probability_dataset_paths: tuple[Path, ...]
    empirical_registry_storage_path: Path | None
    observation_workspace_storage_path: Path | None
    manual_valuation_workspace_storage_path: Path | None
    supported_leagues: tuple[str, ...]
    cors_allowed_origins: tuple[str, ...]


def get_settings() -> ApiSettings:
    game_data_id = os.getenv("DCS_GAME_DATA_DATASET_ID", "poe2db-unknown-version-2026-08-12-task8c-fullx1")
    crafting_id = os.getenv("DCS_CRAFTING_DATASET_ID", "crafting-actions-poe2-quiver-2026-08-12-research")
    affix_id = os.getenv("DCS_AFFIX_CAPACITY_DATASET_ID", "affix-capacity-poe2-2026-08-12-research")
    economy_paths = (
        ROOT / "data" / "normalized" / "economy" / "economy-snapshot-019ff0f4-83a6-76a7-b304-8afe521778ff" / "economy_snapshot.json",
        ROOT / "data" / "normalized" / "economy" / "economy-snapshot-019ff11a-0000-7000-8000-000000000001" / "economy_snapshot.json",
        ROOT / "data" / "normalized" / "economy" / "economy-snapshot-019ff11a-0000-7000-8000-000000000002" / "economy_snapshot.json",
    )
    empirical_paths = tuple(
        Path(value.strip())
        for value in os.getenv("DCS_EMPIRICAL_PROBABILITY_DATASET_PATHS", "").split(os.pathsep)
        if value.strip()
    )
    registry_path_value = os.getenv("DCS_EMPIRICAL_REGISTRY_PATH", str(ROOT / ".dcs" / "empirical_probability_registry.json")).strip()
    empirical_registry_storage_path = None if registry_path_value.lower() in {"", "disabled", "memory", ":memory:"} else Path(registry_path_value)
    workspace_path_value = os.getenv("DCS_OBSERVATION_WORKSPACE_PATH", str(ROOT / ".dcs" / "observation_workspace.json")).strip()
    observation_workspace_storage_path = None if workspace_path_value.lower() in {"", "disabled", "memory", ":memory:"} else Path(workspace_path_value)
    manual_valuation_path_value = os.getenv(
        "DCS_MANUAL_VALUATION_WORKSPACE_PATH",
        str(ROOT / ".dcs" / "manual_valuation_workspace.json"),
    ).strip()
    manual_valuation_workspace_storage_path = (
        None
        if manual_valuation_path_value.lower() in {"", "disabled", "memory", ":memory:"}
        else Path(manual_valuation_path_value)
    )
    return ApiSettings(
        environment=os.getenv("DCS_ENVIRONMENT", "local-offline"),
        default_game_data_dataset_id=game_data_id,
        default_game_data_path=ROOT / "data" / "normalized" / game_data_id / "game_data.json",
        default_crafting_dataset_id=crafting_id,
        default_crafting_path=ROOT / "data" / "normalized" / "crafting" / crafting_id / "actions.json",
        default_affix_capacity_dataset_id=affix_id,
        default_affix_capacity_path=ROOT / "data" / "normalized" / "crafting" / affix_id / "capacity.json",
        economy_snapshot_paths=economy_paths,
        empirical_probability_dataset_paths=empirical_paths,
        empirical_registry_storage_path=empirical_registry_storage_path,
        observation_workspace_storage_path=observation_workspace_storage_path,
        manual_valuation_workspace_storage_path=manual_valuation_workspace_storage_path,
        supported_leagues=tuple(
            league.strip()
            for league in os.getenv("DCS_SUPPORTED_LEAGUES", "Runes of Aldur").split(",")
            if league.strip()
        ),
        cors_allowed_origins=tuple(
            origin.strip()
            for origin in os.getenv("DCS_CORS_ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
            if origin.strip()
        ),
    )
