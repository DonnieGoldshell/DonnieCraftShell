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

The Task 5B resolver uses controlled structured matching against a selected normalized dataset version:

- Item class
- Affix type / generation type
- Display name
- Tier
- Displayed allowed roll range
- Tags as supporting evidence

Do not silently fuzzy-match to a single modifier. If multiple source records remain plausible, return `AMBIGUOUS`.

Matching precedence:

1. Load candidates from the explicit `dataset_version`.
2. Filter by item class applicability when available.
3. Filter by affix type, display name, and tier when the clipboard provides them.
4. Reject candidates whose canonical roll ranges conflict with displayed clipboard ranges.
5. Treat tag overlap as supporting evidence only; tag ordering does not matter.

If exactly one candidate remains, the resolver returns `RESOLVED`. If multiple candidates remain, it returns `AMBIGUOUS` with candidate IDs and no selected canonical ID. If no candidate remains, it returns `UNRESOLVED` without fabricating an ID.

Task 5C also requires minimum structured identity evidence. A parsed modifier with neither display name nor tier is returned as `UNRESOLVED` instead of triggering a broad dataset search.

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
selected_canonical_modifier_id: dc:poe2:modifier-tier:0ab181defaafc7fe
source_record_key: 3ac5789a09e2d27363a60b889aa4dedc668f8e920fb1109617905b626ad921db
match reasons:
- affix type matched Suffix
- display name matched "of Mastery"
- tier matched 2
- roll range matched 11-13
- spawn tags include quiver
```

This example is based on the offline research fixture. It remains `NEEDS VERIFICATION`; PoE2DB is not an official GGG source, and the external hover/cache key is stored only as a source locator.

## Non-Goals

Task 5C does not implement a production scraper, modifier weights, probabilities, valuation, economy, crafting simulation, Craft Advisor logic, or meta scoring.

## Task 8B Modifier Pool Use

Task 8B uses resolved or otherwise source-backed modifier group information to filter legal Exalted-style candidate pools. If an existing parsed modifier is unresolved and lacks group data, the pool resolver warns that conflict filtering is incomplete instead of assuming the modifier conflicts with nothing.
