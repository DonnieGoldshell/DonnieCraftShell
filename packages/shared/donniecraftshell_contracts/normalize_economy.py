"""CLI for regenerating normalized offline economy fixtures."""

from __future__ import annotations

import argparse
from pathlib import Path

from .poe_show_economy import normalize_poe_show_currency_snapshot, write_normalized_economy_snapshot


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize offline DonnieCraftShell economy data.")
    parser.add_argument("raw_snapshot", type=Path)
    parser.add_argument("--out-root", type=Path, default=Path("data/normalized/economy"))
    args = parser.parse_args()

    snapshot = normalize_poe_show_currency_snapshot(args.raw_snapshot)
    output_path = args.out_root / snapshot.snapshot_id / "economy_snapshot.json"
    write_normalized_economy_snapshot(snapshot, output_path)
    print(f"Wrote {output_path}")
    print(f"snapshot_id={snapshot.snapshot_id}")
    print(f"league={snapshot.league}")
    print(f"quotes={len(snapshot.quotes)}")
    print(f"exchange_rates={len(snapshot.exchange_rates)}")


if __name__ == "__main__":
    main()
