# Data Sources

## Required Data Categories

- Item bases and item levels.
- Modifier names, tiers, weights, tags, and prefix/suffix classification.
- Crafting currency behavior and legality.
- Current economy prices for crafting materials.
- Market value estimates for comparable finished items.

## Verification Status

All PoE2-specific sources are currently `TODO / NEEDS VERIFICATION`.

## Candidate Source Types

- Official Grinding Gear Games sources: `TODO / NEEDS VERIFICATION`.
- Public trade or economy APIs: `TODO / NEEDS VERIFICATION`.
- Community-maintained databases: `TODO / NEEDS VERIFICATION`.
- Manual curated data files: allowed only with source notes and verification dates.

## Data Handling Guidelines

Store raw imported data separately from normalized application data. Preserve source name, retrieval time, and transformation version for each import.

Avoid mixing estimated prices with verified rules data. Economy values should include timestamp, currency unit, source, and confidence level.

## Open Questions

- Which PoE2 APIs are available and permitted for this use case?
- Which sources provide reliable Quiver modifier tiers?
- How should comparable item prices be estimated?
- What rate limits, terms, or attribution requirements apply?
