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

## Source Register

### Official Path of Exile Developer API

- Source type: official API.
- Authority level: highest for fields it actually returns.
- Intended use: account/item API fields, league/currency endpoints where permitted, official Currency Exchange hourly history, and source comparison.
- Refresh expectation: follow API changelog and rate-limit guidance.
- Provenance requirements: endpoint, retrieved_at, game version or realm metadata where present, league, and response checksum for imports.
- Known limitations: official docs currently describe limited PoE2 game-information APIs and do not provide a complete canonical modifier catalogue. Currency Exchange requires `service:cxapi` confidential-client credentials and returns historical hourly data, not the current in-progress hour.

### poe.show / poe.ninja Economy API

- Source type: community public economy API.
- Authority level: non-official current-market convenience source.
- Intended use: MVP 0.1 current PoE2 economy overview for currencies and crafting materials including Essences, Omens, Runes, Soul Cores, Catalysts, and related categories.
- Refresh expectation: backend ingestion with HTTP cache/ETag handling; PoE2 source data refreshes roughly hourly, so do not poll per user.
- Provenance requirements: endpoint, league ID/name, category, source line ID, observed/retrieved timestamps, cache metadata where available, source values, volume fields, and confidence/freshness.
- Known limitations: no SLA or versioning guarantee, community source, may block excessive use, and must not be called directly from frontend or end-user machines.

### PoE2DB

- Source type: community-maintained database / game-file presentation site.
- Authority level: non-official; use as provisional or derived until validated.
- Intended use: candidate source for item bases, modifier families, prefix/suffix classification, modifier names, tiers, roll ranges, required item levels, tags, and item-class applicability.
- Refresh expectation: snapshot per PoE2 patch or when source content changes; never scrape per user request at runtime.
- Provenance requirements: source URI, retrieved_at, locale, game version if available, checksum, source-specific IDs/URLs, confidence, and verification status.
- Licensing and source policy: PoE2DB pages state that wiki content is available under CC BY-NC-SA 3.0 unless otherwise noted, and also acknowledge Grinding Gear Games' copyright/trademark rights over Path of Exile material. Do not document extracted/cache game data as unquestionably licensed under CC BY-NC-SA. Bulk normalized PoE2DB game-data storage is `NEEDS REVIEW / NEEDS VERIFICATION`, and commercial use may require additional review because CC BY-NC-SA includes a NonCommercial restriction.
- Reuse policy: require attribution for any content intentionally reused under CC BY-NC-SA. Do not add copied prose/wiki articles to DonnieCraftShell datasets. Prefer factual structured fields needed for modifier resolution, and preserve source URI plus retrieval timestamp for imported records.
- Identifier policy: hash-like PoE2DB hover/cache keys may be stored as `source_record_key` or `source_locator`, but must not be treated as permanently stable canonical game-data IDs until verified. DonnieCraftShell canonical IDs and external source keys remain separate concepts.
- Known limitations: community data is not official, page structure may change, licensing/terms need review, stable IDs may need to be derived from source-backed locators or verified game-file identifiers, and modifier weight information is explicitly not available from game files according to the Quivers page.

Task 5C uses manually captured PoE2DB hover/cache records for 17 Quiver-applicable modifier tiers as an offline research fixture. It validates import and resolver coverage improvements, but it is not a complete Quiver catalogue and must not be treated as production coverage.

## Open Questions

- Which PoE2 APIs are available, stable, and permitted for this use case?
- Which sources reliably provide Quiver modifier tiers and affix classification?
- Which sources can support comparable item valuation?
- What rate limits, terms, or attribution requirements apply?
- How should confidence be calculated for sparse comparable data?
- What stable source-backed identifiers should be used for PoE2DB records when no explicit game-data ID is exposed?
