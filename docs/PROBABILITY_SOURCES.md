# Probability Sources

Task 9A source review date: `2026-08-12`.

## Source Quality Policy

Probability claims need stronger evidence than outcome-space claims. Community item text can establish "random" or "only prefix", but it does not automatically establish uniform probability or modifier weights.

## Sources Reviewed

| Source | Type | Establishes | Does not establish | Status |
| --- | --- | --- | --- | --- |
| [GGG Developer Docs](https://www.pathofexile.com/developer/docs/reference) | Official | PoE2 APIs are limited; available APIs include items, leagues, characters, and currency exchange history | Modifier catalogue, modifier weights, crafting outcome probabilities | `VERIFIED` for API surface |
| [PoE2DB Quivers](https://poe2db.tw/us/Quivers) | Community structured/game-derived | Quiver bases, natural modifier families/tiers/ranges, and statement that modifier weight information cannot be obtained from game files | Exact spawn probabilities | `NEEDS_VERIFICATION` |
| [PoE2 Wiki Orb of Annulment](https://www.poe2wiki.net/wiki/Orb_of_Annulment) | Community wiki | Orb removes a random modifier from magic/rare items; related Annulment Omens restrict side | Uniform selection among eligible modifiers | `PROVISIONAL` |
| [PoE2DB Omen](https://poe2db.tw/us/Omen) | Community structured | Omen text for Sinistral/Dextral Exaltation, Catalysing Exaltation, and other Omen effects | Numeric probability multipliers or weighting formula | `PROVISIONAL` |
| [PoE2DB Omen of Sinistral Annulment](https://poe2db.tw/us/Omen_of_Sinistral_Annulment) | Community structured | Source identity and item metadata for prefix-only Annulment Omen | Distribution within prefix candidates | `PROVISIONAL` |
| [PoE2 Wiki Omen of Greater Annulment](https://www.poe2wiki.net/wiki/Omen_of_Greater_Annulment) | Community wiki | Greater Annulment removes two modifiers; item later drop-disabled | Simultaneous vs sequential selection; distribution | `PROVISIONAL` |
| [PoE2DB Minimum Modifier Level](https://poe2db.tw/us/Minimum_Modifier_Level) | Community structured | Added random modifiers are at least the minimum level and item level must meet the minimum | Weighting after filtering | `PROVISIONAL` |
| [PoE2DB Rarity](https://poe2db.tw/us/Rarity) | Community structured | Exalted/Chaos/Essence item text; Essence of Hysteria Quiver guaranteed modifier | Random-removal distribution; full atomic replacement semantics | `PROVISIONAL` |
| [Mobalytics Omen Guide](https://mobalytics.gg/poe-2/guides/omen-crafting) | Community guide | Cross-checks Omen side restrictions and add/remove summaries | Independent mechanical proof or numeric probabilities | `LOW` supporting only |

## Annulment Evidence

The phrase "random modifier" is supported by community item text. Task 9A did not find official or game-derived text saying "uniform", "equally likely", or equivalent. DonnieCraftShell must not infer equal chance for each modifier.

Side-specific Omens restrict the eligible set to prefix or suffix, but no reviewed source proves equal probability within that restricted set.

Greater Annulment source text says two modifiers are removed, but not how the pair is selected.

Task 23 repeated the evidence pass on `2026-08-25` for issue #41. It found no
stronger source that verifies ordinary Orb of Annulment uniformity or the
crafted/desecrated/special-origin eligibility semantics needed to clear the
First Playable probability blocker. The detailed artifact is
[ANNULMENT_ANALYTICAL_PROBABILITY_EVIDENCE_2026-08-25.md](data/ANNULMENT_ANALYTICAL_PROBABILITY_EVIDENCE_2026-08-25.md).

## Exalted Weight Evidence

The Task 8C Quiver pool has source-backed legal candidates, not weights. PoE2DB's Quiver page explicitly notes that modifier weight information cannot be obtained from game files. The official GGG developer docs do not expose PoE2 modifier weights.

Task 9A did not identify a source suitable for exact Exalted-style probabilities.

## Catalyst / Catalysing Exaltation Evidence

Catalysing Exaltation says the next Exalted Orb consumes Catalyst Quality to increase the chance of the corresponding modifier type. Reviewed sources do not define:

- whether Quivers can have relevant Catalyst Quality,
- which modifier types correspond for Quivers,
- the numeric multiplier,
- whether it modifies family weights, tag weights, or pool selection.

This action remains probability `UNKNOWN`.

## Empirical Evidence

No public empirical dataset was accepted as authoritative in Task 9A. Empirical estimates should be modeled as `EMPIRICAL_ESTIMATE` with sample size, confidence interval, patch/version, and methodology. They must never be presented as exact mechanics.

Task 15A adds a synthetic offline fixture only to prove the empirical pipeline.
It is marked `synthetic` and `test-only`, carries local provenance, and is not a
real PoE2 probability source. No real public empirical probability dataset was
ingested in Task 15A.
