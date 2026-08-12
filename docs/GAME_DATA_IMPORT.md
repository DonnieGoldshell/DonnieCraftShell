# Game Data Import

Task 5B implemented the first offline, fixture-backed game-data pipeline. Task 5C expands it with a larger source-backed Quiver modifier fixture set. The pipeline proves modifier resolution without runtime scraping, valuation, crafting simulation, economy data, modifier weights, or meta scoring.

## Pipeline

```text
manual source snapshot
-> data/raw/
-> source adapter/importer
-> normalizer
-> data/normalized/
-> GameDataRepository
-> ModifierResolver
-> ItemEnrichment
```

Runtime code must read normalized DonnieCraftShell data, not PoE2DB-shaped raw JSON and not live community pages.

## Raw Schema

Raw PoE2DB research records live under `data/raw/poe2db/<snapshot-id>/raw_modifiers.json`. They preserve source terminology:

- `source_record_key`, `source_uri`, `retrieved_at`
- `display_name`, `family`, `domain`, `generation_type`
- `required_level`, `tier`
- `stats[]` with text, min, max, and optional scope
- `spawn_tags`, `craft_tags`, and source notes

Only factual structured fields needed for modifier resolution are stored. Copied wiki prose is not part of the dataset.

## Normalized Schema

Normalized JSON lives under `data/normalized/<dataset-version>/game_data.json` and contains:

- `GameDataSnapshot`
- `ModifierFamily`
- `ModifierTierDefinition`
- `ModifierApplicability`

Every normalized record preserves provenance back to the source URI, retrieval timestamp, and external `source_record_key` where available.

## Canonical IDs

DonnieCraftShell canonical modifier-tier IDs use a deterministic dataset-scoped semantic hash:

```text
dc:poe2:modifier-tier:<sha256-prefix>
```

The hash input includes game, domain, modifier family, generation type, tier, normalized stat template, and roll-range identity. It is not a GGG ID. PoE2DB hover/cache hashes remain external source locators only.

## Repository Behavior

`GameDataRepository` loads explicit normalized dataset versions from JSON files. Callers must request a specific `dataset_version`; there is no implicit `latest` behavior in Task 5B.

## Current Coverage

The Task 5C fixture dataset remains as a historical resolver regression set with 17 source-backed Quiver-applicable records across 12 normalized modifier families.

Task 8C adds the current natural explicit Quiver Base pool dataset:

```text
poe2db-unknown-version-2026-08-12-task8c-fullx1
```

Task 8C raw capture:

```text
data/raw/poe2db/quiver-natural-base-modifiers-2026-08-12/raw_modifiers.json
```

Regeneration command:

```bash
python -m packages.shared.donniecraftshell_contracts.normalize_game_data data/raw/poe2db/quiver-natural-base-modifiers-2026-08-12/raw_modifiers.json --out-root data/normalized
```

See [QUIVER_MODIFIER_POOL_STATUS.md](QUIVER_MODIFIER_POOL_STATUS.md) for current natural Base pool counts and completeness. See [QUIVER_DATASET_STATUS.md](QUIVER_DATASET_STATUS.md) for the earlier Task 5C fixture coverage notes.

## Regeneration

Regenerate normalized JSON from raw fixtures with:

```bash
python -m packages.shared.donniecraftshell_contracts.normalize_game_data data/raw/poe2db/quiver-modifiers-research-2026-08-11/raw_modifiers.json --out-root data/normalized
```

This command performs no network I/O.

## Validation

Dataset loading fails on duplicate canonical IDs, missing snapshot/dataset identity, invalid tier values, invalid required levels, `min > max` roll ranges, invalid affix/generation types, missing provenance, or applicability that references an unknown modifier.

Task 8C adds regression coverage that the expanded raw Quiver natural Base modifier fixture regenerates `16` normalized families and `100` tier definitions. Duplicate semantic tier records are still rejected through deterministic canonical ID collisions.

## Future Imports

A later task can expand the raw snapshot set manually or through an offline importer. The same normalizer and repository boundaries should remain in place so the runtime application never depends on PoE2DB availability.
