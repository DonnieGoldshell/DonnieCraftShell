# Affix Capacity

Task 7B introduces source-backed affix-capacity resolution for crafting applicability. This layer derives open explicit prefix/suffix slots beside `ParsedItem`; it does not mutate parser output.

## Dataset

Normalized dataset:

```text
data/normalized/crafting/affix-capacity-poe2-2026-08-12-research/capacity.json
```

Raw research register:

```text
data/raw/crafting/poe2-affix-capacity-research-2026-08-12.json
```

The current dataset is community-source-backed and therefore `PROVISIONAL`, not official.

## Current Capacity Rules

Current modeled rules:

- Normal: `0` prefixes, `0` suffixes.
- Magic: `1` prefix, `1` suffix.
- Rare: `3` prefixes, `3` suffixes.
- Unique: capacity remains unknown because unique modifier structure can be item-specific.

These rules are generic by rarity. No Quiver-specific exception is currently source-backed.

## Slot Consumption

The resolver counts normal explicit prefix/suffix slots from parsed explicit modifiers.

- Natural prefix/suffix modifiers consume the matching explicit slot.
- Crafted prefix/suffix modifiers are treated as consuming normal slots, based on source text that crafted modifiers behave like other modifiers.
- Desecrated prefix/suffix modifiers consume the matching slot when source-backed.
- Implicit modifiers and corruption enhancements do not consume normal explicit affix slots.
- Fractured slot-consumption remains `UNKNOWN` until stronger source evidence is captured.

If an unknown origin/affix combination is encountered, the resolver emits a warning and lowers confidence instead of guessing.

## Resolution Output

`AffixStateResolver` combines `ParsedItem` with `AffixCapacityDefinition` and returns `AffixStateResolution`:

- observed prefix/suffix counts
- prefix/suffix capacity
- open prefix/suffix counts
- confidence
- provenance
- warnings

If capacity is unknown, open counts remain `None`. If observed count exceeds capacity, the resolver does not clamp; it returns negative open count with a conflict warning.

## Crafting Integration

`CraftActionEngine.evaluate_action(action, item, enrichment)` can receive an `AffixStateResolution`. Open-slot preconditions then use:

- `ANY` for actions that can add either prefix or suffix.
- `PREFIX` for prefix-targeted actions.
- `SUFFIX` for suffix-targeted actions.

Without an affix resolution, open-slot applicability remains `UNKNOWN`.

## Current Quiver Fixture Results

- Quiver 1: `3/3`, full.
- Quiver 2: `3/3`, full.
- Quiver 5: `3/3`, full and corrupted, so regular crafting is also blocked.
- Quiver 6: `3/3`, full; crafted prefix and desecrated suffix consume slots under current source-backed rules.
- Quiver 7: `3/3`, full; corruption enhancements are separate and do not consume explicit slots.

## Needs Verification

- Stronger official or in-game confirmation for Magic `1/1` and Rare `3/3`.
- Fractured modifier slot-consumption in PoE2.
- Any Quiver-specific exceptions.
- Unique item affix capacity behavior.
