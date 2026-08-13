"""Import empirical crafting observations into raw probability datasets."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from packages.shared.donniecraftshell_contracts.empirical_observation_import import (
    aggregate_observations,
    load_empirical_observation_files,
    write_aggregated_empirical_dataset,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", help="Observation JSON/CSV files to import.")
    parser.add_argument("--output", required=True, help="Output file or directory for aggregated raw empirical dataset JSON.")
    parser.add_argument("--dataset-id-prefix", default="empirical-probability")
    parser.add_argument("--retrieved-at", default=None, help="ISO timestamp for aggregation retrieval time.")
    parser.add_argument("--overwrite", action="store_true", help="Allow overwriting existing output files.")
    args = parser.parse_args(argv)

    retrieved_at = (
        datetime.fromisoformat(args.retrieved_at.replace("Z", "+00:00"))
        if args.retrieved_at
        else datetime.now(timezone.utc)
    )
    batch = load_empirical_observation_files(tuple(args.inputs))
    result = aggregate_observations(
        batch,
        retrieved_at=retrieved_at,
        dataset_id_prefix=args.dataset_id_prefix,
    )
    output = Path(args.output)
    if len(result.datasets) != 1 and output.suffix:
        print("Multiple context partitions require --output to be a directory.", file=sys.stderr)
        return 2
    written: list[Path] = []
    for dataset in result.datasets:
        path = output / f"{dataset.dataset_id}.json" if not output.suffix else output
        written.append(write_aggregated_empirical_dataset(dataset, path, overwrite=args.overwrite))

    print(f"accepted={result.accepted_record_count}")
    print(f"duplicates={result.duplicate_record_count}")
    print(f"unclassified={result.unclassified_record_count}")
    print(f"rejected={len(result.rejected_records)}")
    print(f"datasets={len(result.datasets)}")
    for warning in result.warnings:
        print(f"warning={warning}")
    for rejected in result.rejected_records:
        print(f"rejected_record={rejected.raw_record_id or 'UNKNOWN'} reason={rejected.reason}")
    for path in written:
        print(f"wrote={path}")
    return 0 if not result.rejected_records else 1


if __name__ == "__main__":
    raise SystemExit(main())
