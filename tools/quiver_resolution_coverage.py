"""Report modifier-resolution coverage for PoE2 Quiver fixtures."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.shared.donniecraftshell_contracts.domain import AffixType, ModifierOrigin
from packages.shared.donniecraftshell_contracts.game_data import ResolutionStatus
from packages.shared.donniecraftshell_contracts.game_data_repository import GameDataRepository
from packages.shared.donniecraftshell_contracts.modifier_resolver import enrich_item
from packages.shared.donniecraftshell_contracts.parser import parse_clipboard_item


@dataclass(frozen=True)
class FixtureCoverage:
    fixture: str
    total: int
    resolved: int
    ambiguous: int
    unresolved: int
    explicit_total: int
    explicit_resolved: int
    unresolved_modifiers: tuple[str, ...]

    @property
    def coverage_percent(self) -> float:
        return (self.resolved / self.total * 100) if self.total else 0.0

    @property
    def explicit_coverage_percent(self) -> float:
        return (self.explicit_resolved / self.explicit_total * 100) if self.explicit_total else 0.0


def collect_coverage(
    fixture_dir: Path,
    normalized_dataset: Path,
    dataset_version: str,
) -> tuple[FixtureCoverage, ...]:
    repository = GameDataRepository.from_json_files((normalized_dataset,))
    rows: list[FixtureCoverage] = []
    for path in sorted(fixture_dir.glob("*_advanced.txt")):
        parsed = parse_clipboard_item(path.read_text(encoding="utf-8")).item
        if parsed is None:
            continue
        enrichment = enrich_item(parsed, repository, dataset_version)
        statuses = [resolution.status for resolution in enrichment.modifier_resolutions]
        unresolved = tuple(
            _modifier_label(resolution.parsed_modifier)
            for resolution in enrichment.modifier_resolutions
            if resolution.status == ResolutionStatus.UNRESOLVED
        )
        explicit_resolutions = tuple(
            resolution
            for resolution in enrichment.modifier_resolutions
            if resolution.parsed_modifier.affix_type in {AffixType.PREFIX, AffixType.SUFFIX}
            and resolution.parsed_modifier.origin != ModifierOrigin.UNIQUE
        )
        rows.append(
            FixtureCoverage(
                fixture=path.name,
                total=len(statuses),
                resolved=statuses.count(ResolutionStatus.RESOLVED),
                ambiguous=statuses.count(ResolutionStatus.AMBIGUOUS),
                unresolved=statuses.count(ResolutionStatus.UNRESOLVED),
                explicit_total=len(explicit_resolutions),
                explicit_resolved=sum(
                    1 for resolution in explicit_resolutions if resolution.status == ResolutionStatus.RESOLVED
                ),
                unresolved_modifiers=unresolved,
            )
        )
    return tuple(rows)


def format_markdown(rows: tuple[FixtureCoverage, ...]) -> str:
    lines = [
        "| Fixture | Total | Resolved | Ambiguous | Unresolved | Coverage | Explicit Coverage |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            f"| {row.fixture} | {row.total} | {row.resolved} | {row.ambiguous} | "
            f"{row.unresolved} | {row.coverage_percent:.1f}% | {row.explicit_coverage_percent:.1f}% |"
        )
    return "\n".join(lines)


def _modifier_label(modifier) -> str:
    return modifier.display_name or modifier.normalized_text or modifier.raw_text.splitlines()[0]


def main() -> None:
    parser = argparse.ArgumentParser(description="Report Quiver fixture resolver coverage.")
    parser.add_argument("normalized_dataset", type=Path)
    parser.add_argument("dataset_version")
    parser.add_argument(
        "--fixture-dir",
        type=Path,
        default=Path("tests/fixtures/poe2/quivers"),
    )
    args = parser.parse_args()

    rows = collect_coverage(args.fixture_dir, args.normalized_dataset, args.dataset_version)
    print(format_markdown(rows))
    print()
    for row in rows:
        unresolved = ", ".join(row.unresolved_modifiers) if row.unresolved_modifiers else "None"
        print(f"{row.fixture}: unresolved={unresolved}")


if __name__ == "__main__":
    main()
