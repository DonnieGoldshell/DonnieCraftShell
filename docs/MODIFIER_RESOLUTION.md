# Modifier Resolution

Modifier resolution maps parsed clipboard modifiers to canonical game-data records.

```text
ParsedItem
-> ItemModifier observation
-> ModifierResolver
-> GameDataSnapshot
-> ModifierResolution
-> ItemEnrichment
```

## Resolver Interface

The contract is represented by `ModifierResolver` in `packages/shared/donniecraftshell_contracts/game_data.py`.

Input:

- `ParsedItem`
- `ItemModifier`
- `GameDataSnapshot`

Output:

- `RESOLVED`
- `AMBIGUOUS`
- `UNRESOLVED`

Each resolution includes confidence, match reasons, provenance, warnings, and either a selected canonical modifier ID or candidate records. Ambiguous matches must remain ambiguous and cannot select a fake winner.

## Matching Signals

A future resolver may use:

- Item class
- Affix type
- Modifier origin
- Display name
- Tier
- Tags
- Normalized stat text
- Observed value and displayed range
- Dataset version

Do not silently fuzzy-match to a single modifier. If multiple source records remain plausible, return `AMBIGUOUS`.

## Enrichment Model

Use `ItemEnrichment` and `ModifierResolution` beside `ParsedItem`. Clipboard observations remain immutable. External game-data truth is represented as linked enrichment, not copied over parser fields.

## Example

Parsed modifier from Task 4:

```text
{ Suffix Modifier "of Mastery" (Tier: 2) - Attack, Speed }
13(11-13)% increased Attack Speed
```

Possible future enrichment:

```text
status: RESOLVED
selected_canonical_modifier_id: dc:mod:<uuidv7-or-derived-internal-id>
source_record_key: poe2db:hover:3ac5789...
match reasons:
- affix type matched Suffix
- display name matched "of Mastery"
- family matched IncreasedAttackSpeed
- roll range matched 11-13
- spawn tags include quiver
```

This example is based on manually captured PoE2DB research and remains `NEEDS VERIFICATION` until a repeatable import and source review exist.

## Non-Goals

Task 5A does not implement a production resolver, scraper, modifier weights, probabilities, valuation, economy, crafting simulation, or meta scoring.
