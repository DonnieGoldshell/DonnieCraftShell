# Game Data Import

Task 5B implements the first offline, fixture-backed game-data pipeline. It proves modifier resolution without runtime scraping, valuation, crafting simulation, economy data, modifier weights, or meta scoring.

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

The fixture dataset contains one source-backed Quiver-applicable record:

- `of Mastery`, Suffix, Tier 2, `11-13% increased Attack Speed`

All other Quiver fixture modifiers remain unresolved until source-backed raw records are added.

## Validation

Dataset loading fails on duplicate canonical IDs, missing snapshot/dataset identity, invalid tier values, invalid required levels, `min > max` roll ranges, invalid affix/generation types, missing provenance, or applicability that references an unknown modifier.

## Future Imports

A later Task 5C can expand the raw snapshot set manually or through an offline importer. The same normalizer and repository boundaries should remain in place so the runtime application never depends on PoE2DB availability.
