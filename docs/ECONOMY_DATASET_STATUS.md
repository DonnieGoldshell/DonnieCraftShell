# Economy Dataset Status

Task 6C extends the offline poe.show economy dataset beyond Currency into crafting-material categories.

## Captures

All captures use league `Runes of Aldur`.

| Category | Snapshot ID | Retrieved At | Quotes | Divine -> Exalted |
| --- | --- | --- | ---: | ---: |
| Currency | `economy-snapshot-019ff0f4-83a6-76a7-b304-8afe521778ff` | `2026-08-11T13:10:57.2395462Z` | 4 | `338.2` |
| Ritual | `economy-snapshot-019ff11a-0000-7000-8000-000000000001` | `2026-08-11T13:26:14.9830715Z` | 4 | `337.8` |
| Essences | `economy-snapshot-019ff11a-0000-7000-8000-000000000002` | `2026-08-11T13:26:14.9830715Z` | 4 | `337.8` |

Separate category responses remain separate snapshots. Do not pretend they were observed at the Currency timestamp.

## Captured Assets

Ritual / Omens:

- `omen-of-putrefaction`: `0.21693516` Exalted units.
- `omen-of-catalysing-exaltation`: `5.968926` Exalted units.
- `omen-of-chaotic-monsters`: `48.9810` Exalted units.
- `omen-of-light`: `3286.794` Exalted units.

Essences:

- `perfect-essence-of-battle`: `6.489138` Exalted units.
- `perfect-essence-of-alacrity`: `0.7245810` Exalted units.
- `greater-essence-of-ice`: `0.4790004` Exalted units.
- `essence-of-enhancement`: `30.000018` Exalted units.

## Semantics

For captured Ritual and Essences responses, `core.primary = divine`; `primaryValue` is interpreted as value in Divine Orb units, and `core.rates.exalted` gives the Divine -> Exalted rate. `volumePrimaryValue` is present and preserved as source volume evidence.

The line payloads provide source IDs but not separate human-readable item names in the bounded captures. DonnieCraftShell internal asset IDs are explicit mappings from those source IDs.

## Current Coverage Limits

Only the bounded captured rows above are mapped. Missing Omens, Essences, Runes, Soul Cores, and Catalysts remain unknown. Missing price never means zero.
