# Data Sources And Provenance

## Verification Policy

Path of Exile 2 changes frequently. All game rules, modifier data, crafting mechanics, API capabilities, and economy sources are `NEEDS VERIFICATION` until confirmed from reliable references.

Do not present unverified or curated data as objective game truth.

## Required Data Categories

- Item bases, item levels, rarity, and clipboard text format.
- Modifier names, tiers, roll ranges, weights, tags, groups, and prefix/suffix classification.
- Crafting currency, Omen, Essence, Rune, and other crafting material behavior.
- Legal crafting actions and outcome probabilities.
- League-specific currency exchange rates and crafting material prices.
- Comparable rare item market observations.
- Build/meta relevance for modifiers.

## Economy Records

Economy data is shared infrastructure. Each record should include league, item or currency identifier, normalized price, exchange rate, timestamp, source, trading volume where available, and confidence or data quality where appropriate.

Initial normalized unit:

```text
1 Exalted Orb = 1 economic unit
```

UI may display Exalted, Divine, or both using current exchange rates.

Historical snapshots should be retained for trend analysis and reproducibility.

## Data Provenance

External or derived records should include fields such as:

- `source`
- `retrieved_at`
- `game_version`
- `league`
- `confidence`

Store raw imported data separately from normalized application data. Keep derived statistical data separate from curated or opinion-based relevance.

## Candidate Source Types

- Official Grinding Gear Games sources: `NEEDS VERIFICATION`.
- Public trade or economy APIs: `NEEDS VERIFICATION`.
- Community-maintained databases: `NEEDS VERIFICATION`.
- Manual curated data files: permitted only with source notes, verification dates, and clear labeling.

## Open Questions

- Which PoE2 APIs are available, stable, and permitted for this use case?
- Which sources reliably provide Quiver modifier tiers and affix classification?
- Which sources can support comparable item valuation?
- What rate limits, terms, or attribution requirements apply?
- How should confidence be calculated for sparse comparable data?
