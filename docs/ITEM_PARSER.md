# Item Parser

The item parser converts Path of Exile 2 clipboard text into the shared `ParsedItem` domain model. It is loss-aware: unknown or unsupported lines should be preserved and warned about rather than silently discarded.

## Supported Formats

- **Advanced Copy**: recommended for MVP 0.1 because it exposes modifier placement, origin, display name, tier, tags, and roll ranges.
- **Normal Copy**: accepted where practical, but modifier tier, affix type, origin, and tags usually remain unknown.
- **Unknown**: rejected when required PoE item markers such as `Item Class:` and `Rarity:` are missing.

## Parser Stages

The implementation in `packages/shared/donniecraftshell_contracts/parser.py` is split into:

1. Clipboard normalization.
2. Section detection.
3. Header parsing.
4. Property parsing.
5. Modifier block parsing.
6. Special-state parsing.
7. `ParsedItem` assembly.

Regex is used only for well-defined line formats such as advanced modifier headers and displayed numeric roll values.

## Current Behavior

The parser extracts item class, rarity, item name, base type, required level, item level, implicit modifiers, explicit prefixes/suffixes, modifier names, tiers, tags, observed values, displayed roll ranges, crafted/desecrated origins, corrupted/twice-corrupted states, corruption enhancements, granted skill text, trade notes, equipment restrictions, raw sections, unparsed lines, and warnings.

Modifier placement and modifier origin are separate concepts. For example, a crafted prefix has `affix_type=PREFIX` and `origin=CRAFTED`.

## Limits

The parser does not enrich from game data, infer tiers, infer open affix slots, calculate prefix/suffix capacity, validate crafting legality, estimate prices, or simulate outcomes.

The following remain `NEEDS VERIFICATION`: exact PoE2 clipboard guarantees, all modifier semantics, item-state mechanics, Quiver affix capacity, trade-note semantics, and whether all advanced-copy header variants are represented in the fixture set.
