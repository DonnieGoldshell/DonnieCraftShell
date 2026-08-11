# Game Data

Game data is the external reference layer that turns parsed clipboard observations into source-backed canonical records. It must remain separate from parser output and from derived economic intelligence.

## Purpose

The parser records what the user pasted. The game-data layer records what an external dataset says about bases, modifier families, tiers, roll ranges, required levels, tags, and applicability.

Never overwrite a `ParsedItem` or `ItemModifier` with external data. Add enrichment records beside the parsed observation.

## Models

Executable contracts live in `packages/shared/donniecraftshell_contracts/game_data.py`.

- `GameDataSnapshot`: immutable source snapshot metadata, source URI, retrieval time, checksum, game context, verification status, and provenance.
- `ItemBaseDefinition`: source-backed base record with item class, base name, required level, implicit modifier IDs, provenance, and dataset version.
- `ModifierFamily`: conceptual/stat family with normalized template, affix type, tags, group/family, and provenance.
- `ModifierTierDefinition`: a tier within a family, with display name, tier label, required item level, multiple roll ranges, provenance, and dataset version.
- `ModifierApplicability`: item-class/base/tag conditions where a modifier may appear.
- `ModifierWeight`: future-only model for weight/probability data. Missing weight is unknown, not zero.

Canonical IDs must be source-backed and namespaced. Display names such as `of Mastery` are not stable identifiers.

External source keys and DonnieCraftShell canonical IDs are separate concepts. A hash-like PoE2DB hover/cache key may be stored as `source_record_key` or `source_locator`, but must not be treated as a permanently stable canonical game-data ID until verified.

For the Task 5B fixture dataset, modifier-tier canonical IDs use deterministic DonnieCraftShell semantic hashes with the form `dc:poe2:modifier-tier:<hash-prefix>`. The hash input includes game, domain, modifier family, generation type, tier, normalized stat template, and roll-range identity. This is a DonnieCraftShell dataset identity, not an official GGG identifier.

## Storage Layout

Use this structure until database import is implemented:

```text
data/raw/<source>/<snapshot-id>/
data/normalized/<dataset-version>/
data/research/
```

Raw source snapshots should be immutable where practical. Normalized data should be generated from raw snapshots. Runtime code should read normalized data or database records, not scrape community pages per user request.

Task 5B implements the first offline JSON-backed version of this flow, and Task 5C expands the Quiver modifier fixture set. See [GAME_DATA_IMPORT.md](GAME_DATA_IMPORT.md) for the raw schema, normalized schema, validation rules, canonical ID strategy, and current fixture coverage. See [QUIVER_DATASET_STATUS.md](QUIVER_DATASET_STATUS.md) for measured resolver coverage.

## Versioning

Every normalized record should include dataset version and provenance. Historical craft sessions should store the snapshot or dataset version used so later imports do not silently change old conclusions.

Recommended dataset version shape:

```text
<source>-<game-version-or-unknown>-<retrieved-date>-<content-hash-prefix>
```

## PoE2DB Research Summary

PoE2DB appears to expose useful research fields including modifier display name, family, domain, generation type/prefix-suffix, required level, stat min/max, spawn tags, craft tags, Quiver base names, and implicit stats. Treat this as community-source data, not official data.

PoE2DB's Quiver page includes a statement that modifier weight information cannot be obtained from game files. Therefore modifier weights/probabilities must remain a separate optional data category with its own source, confidence, and methodology.

PoE2DB pages state that wiki content is available under CC BY-NC-SA 3.0 unless otherwise noted and acknowledge Grinding Gear Games' copyright/trademark rights over Path of Exile material. This does not automatically make extracted/cache game data safe for bulk normalized storage. Bulk storage, redistribution, and commercial use are `NEEDS REVIEW / NEEDS VERIFICATION`; CC BY-NC-SA also includes a NonCommercial restriction. DonnieCraftShell should avoid copied prose/wiki articles in datasets, prefer factual structured fields needed for modifier resolution, and preserve attribution, source URI, and retrieval timestamp.

Official Path of Exile developer docs state that current APIs expose limited PoE2 game information. They document item fields such as rarity, item level, implicit mods, explicit mods, crafted mods, fractured mods, desecrated mods, granted skills, corrupted, double-corrupted, and sanctified flags, but this is not a complete canonical modifier catalogue.

See [DATA_SOURCES.md](DATA_SOURCES.md) for source authority and provenance rules.
