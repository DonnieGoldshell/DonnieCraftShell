"""CLI for regenerating normalized offline game-data fixtures."""

from __future__ import annotations

import argparse
from pathlib import Path

from .game_data_import import normalize_poe2db_snapshot, write_normalized_dataset


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize offline DonnieCraftShell game data.")
    parser.add_argument("raw_snapshot", type=Path, help="Path to raw source snapshot JSON.")
    parser.add_argument(
        "--out-root",
        type=Path,
        default=Path("data/normalized"),
        help="Directory where <dataset-version>/game_data.json will be written.",
    )
    args = parser.parse_args()

    dataset = normalize_poe2db_snapshot(args.raw_snapshot)
    output_path = args.out_root / dataset.dataset_version / "game_data.json"
    write_normalized_dataset(dataset, output_path)
    print(f"Wrote {output_path}")
    print(f"dataset_version={dataset.dataset_version}")
    print(f"modifier_families={len(dataset.modifier_families)}")
    print(f"modifier_tiers={len(dataset.modifier_tiers)}")
    print(f"modifier_applicability={len(dataset.modifier_applicability)}")


if __name__ == "__main__":
    main()
