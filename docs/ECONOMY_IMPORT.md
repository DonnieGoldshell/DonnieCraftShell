# Economy Import

Task 6B implements the first offline PoE2 Economy Engine import path using a bounded poe.show Currency response. Task 6C extends the same import path to Ritual/Omens and Essences.

## Raw Fixture

Raw fixture:

```text
data/raw/economy/poe-show-poe2-currency-runes-of-aldur-2026-08-11.json
```

Captured metadata:

- Source: `poe.show`
- Source URI: `https://poe.show/poe2/api/economy/exchange/current/overview?league=Runes%20of%20Aldur&type=Currency`
- League: `Runes of Aldur`
- Retrieved at: `2026-08-11T13:10:57.2395462Z`
- Category: `Currency`
- Source primary currency: `divine`

The bounded snapshot includes `exalted`, `divine`, `perfect-exalted-orb`, and `greater-exalted-orb`. `orb-of-annulment` was not present in the captured bounded response and is not fabricated.

Additional Task 6C fixtures:

```text
data/raw/economy/poe-show-poe2-ritual-runes-of-aldur-2026-08-11.json
data/raw/economy/poe-show-poe2-essences-runes-of-aldur-2026-08-11.json
```

Both were captured for league `Runes of Aldur` at `2026-08-11T13:26:14.9830715Z`. Their `core.primary` is `divine`, and their `primaryValue` fields are normalized through `core.rates.exalted`.

## Asset Mapping

Provider IDs are mapped explicitly:

```text
poe.show exalted -> dc:poe2:economy-asset:currency:exalted-orb
poe.show divine -> dc:poe2:economy-asset:currency:divine-orb
poe.show perfect-exalted-orb -> dc:poe2:economy-asset:currency:perfect-exalted-orb
poe.show greater-exalted-orb -> dc:poe2:economy-asset:currency:greater-exalted-orb
poe.show omen-of-catalysing-exaltation -> dc:poe2:economy-asset:ritual:omen-of-catalysing-exaltation
poe.show perfect-essence-of-battle -> dc:poe2:economy-asset:essence:perfect-essence-of-battle
```

Unknown source assets are skipped with warnings rather than guessed.

## Rate Direction

Exchange rates are directional. The Task 6B fixture has:

```text
DIVINE -> EXALTED = 338.2
```

This means `1 Divine Orb = 338.2 Exalted Orbs`.

## Normalization

When `core.primary = divine`, normalization uses:

```text
normalized_exalted_value = line.primaryValue * divine_to_exalted_rate
```

Special invariant:

```text
Exalted Orb = 1 Exalted economic unit
```

Task 6B values:

- Exalted Orb: `1`
- Divine Orb: `338.2`
- Perfect Exalted Orb: `2.63 * 338.2 = 889.466`
- Greater Exalted Orb: `0.0164 * 338.2 = 5.54648`

Task 6C examples:

- Omen of Catalysing Exaltation: `0.01767 * 337.8 = 5.968926`
- Perfect Essence of Battle: `0.01921 * 337.8 = 6.489138`

All arithmetic uses `Decimal`. Missing, zero, or negative rates do not produce normalized prices.

## Regeneration

Regenerate normalized economy data offline:

```bash
python -m packages.shared.donniecraftshell_contracts.normalize_economy data/raw/economy/poe-show-poe2-currency-runes-of-aldur-2026-08-11.json --out-root data/normalized/economy
```

Output:

```text
data/normalized/economy/economy-snapshot-019ff0f4-83a6-76a7-b304-8afe521778ff/economy_snapshot.json
```

## Repository Behavior

`EconomyRepository` loads normalized snapshots in memory. `get_current_quote()` means latest available quote at or before the requested `as_of` time for the explicit league and asset. `get_current_quotes()` returns multiple asset lookups, and `get_category_quotes()` returns latest quotes for a category. Stale quotes are returned with freshness metadata instead of being silently dropped.

## Craft Material Cost

Task 6C adds `CraftMaterialRequirement`, `CraftMaterialCostLine`, and `CraftMaterialCost`. This only prices a known ingredient list; it does not model crafting mechanics. If any ingredient quote is missing, the result is incomplete and total is unavailable.

## Future Categories

Ritual/Omens, Essences, Runes, Soul Cores, Catalysts, and other crafting materials should be added as separate raw fixtures using the same provider adapter boundary. Do not fetch them at user request time.

The future GGG Currency Exchange provider should produce the same `EconomySnapshot`, `EconomyQuote`, and `ExchangeRate` concepts from official hourly history.
