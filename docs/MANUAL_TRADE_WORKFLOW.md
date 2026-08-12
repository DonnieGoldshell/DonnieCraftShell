# Manual Trade Workflow

Task 10B introduces `ManualTradeProvider` as the MVP-safe valuation evidence workflow. It is intentional design, not an undocumented Trade API workaround.

## Why Manual First

Official developer documentation does not provide a documented PoE2 rare-item Trade search/listing API for third-party valuation. DonnieCraftShell therefore must not automate undocumented Trade endpoint access.

Manual workflow keeps the user in control:

```text
ComparableQuery
-> human-readable search instructions
-> user opens official Trade site
-> user records listing observations
-> EconomyRepository normalizes currencies where possible
-> ComparableEvidenceSet readiness
-> ValuationAggregator
-> LISTING_DERIVED ValuationResult when evidence is sufficient
```

## Provider Capabilities

`ManualTradeProvider` reports:

- `supports_automatic_search = false`
- `supports_manual_observations = true`
- `supports_trade_url_generation = false`
- `supports_completed_sales = false`

No network calls are made.

## Manual Observations

A manual observation preserves:

- original entered amount,
- currency EconomyAsset ID,
- league,
- observed timestamp,
- optional listing ID,
- item summary,
- provenance/warnings.

Examples such as `5 Divine` or `2400 Exalted` can be normalized only when EconomyRepository has a usable quote or identity conversion. Invalid or unconvertible currency remains unavailable, not zero.

## Evidence Limits

Comparable evidence is not valuation. Listing price is not realized sale price.

Manual observations should include warnings when synthetic/test-only, stale, duplicated, unconvertible, or otherwise questionable. Task 10C aggregation may produce a listing-derived estimate from usable normalized manual observations, but it still does not infer completed-sale value or expected sale price.

Unconvertible observations remain in the evidence set and reduce readiness; they are never treated as zero.
