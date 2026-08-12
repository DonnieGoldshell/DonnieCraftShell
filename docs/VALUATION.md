# Valuation Engine

Task 10A designs the rare-item Valuation Engine. Task 10B implements the first framework-independent comparable-evidence contracts and manual workflow. It does not implement trade scraping, market-value aggregation, EV, recommendations, or automated decisions.

## Core Principle

Valuation is uncertain. A listed price is not a realized sale price, and a valuation estimate is not a known true value.

Every valuation should carry an estimated value, plausible low/high range, confidence, comparable count and quality, source timestamps, market freshness, methodology, provenance, and warnings. `INSUFFICIENT_DATA` is a valid result.

## Engine Boundary

```text
Current Parsed/Enriched Item
or
HypotheticalItemState
-> ValuationSubject
-> ComparableQueryBuilder
-> TradeProvider
-> ComparableResult[]
-> ValuationAggregator
-> ValuationResult
```

The same valuation interface must accept current item observations and hypothetical outcome states. Outcome valuation later becomes:

```text
CraftOutcomeSet
+ OutcomeProbabilityModel
+ ValuationResult[]
-> EV Engine
```

The Valuation Engine must not depend on `ParsedItem` only.

See [VALUATION_MODEL.md](VALUATION_MODEL.md) for the Task 10B executable contracts.

## Readiness

Use readiness states:

- `READY`: enough comparable evidence exists for future aggregation to attempt an estimate.
- `PARTIAL`: some evidence exists, but confidence is low or conversion/query quality is incomplete.
- `INSUFFICIENT_DATA`: no defensible estimate should be produced.

## Comparable Strategies

### Strict Comparable

Use same item class/base context and the most value-driving modifiers with similar tiers or ranges. This gives the cleanest signal but may return too few listings.

### Moderate Comparable

Relax roll/tier thresholds while preserving major value-driving modifiers. This is the likely MVP default for sparse Quiver markets.

### Build-Equivalent Comparable

Compare items with similar build utility even when exact modifier text differs. This depends on future Meta/Modifier relevance and should remain provisional.

### Cost-to-Reproduce

Future supporting signal based on crafting input cost required to reach a similar state. This is not market value and must not replace listing evidence.

## Modifier Roles

A valuation query must not blindly require every modifier. Modifier roles should be supplied with provenance:

- `VALUE_DRIVING`
- `SUPPORTING`
- `IGNORE_FOR_COMPARABLE`
- `UNKNOWN`

For Task 10A these roles are architecture only. Future roles may come from manual selection, rule fixtures, or Meta/Modifier relevance. Curated roles must never be presented as objective game data.

## Comparable Query Contract

Future `ComparableQuery` fields:

- item class, base constraints, rarity, item level constraints
- included modifier constraints with role and relaxation rules
- excluded/ignored modifiers
- comparable strategy
- league
- generated_at
- provenance and warnings

Future `ComparableResult` fields:

- source/listing identity
- listing price and currency
- normalized economic value using Economy Engine
- item summary and matched constraints
- listed_at / observed_at
- source/provenance
- warnings

## TradeProvider Boundary

Implement providers behind a replaceable interface:

- `ManualTradeProvider`: user opens official Trade search, records observations manually or by paste/import.
- `FutureOfficialTradeProvider`: only if GGG documents and permits a rare-item search/listing API.
- `FutureThirdPartyProvider`: only if a legitimate provider offers rare-item listing/comparable data with acceptable terms.

No runtime code should depend on undocumented trade-site endpoints.

## MVP Workflow

Recommended MVP 0.1 valuation workflow:

1. DonnieCraftShell builds strict and moderate comparable query definitions.
2. User opens official Trade search URLs or reconstructs the filters manually.
3. User supplies listing observations.
4. Economy Engine normalizes listing currencies.
5. ComparableEvidenceSet returns `READY`, `PARTIAL`, or `INSUFFICIENT_DATA`.

This is safer than unsupported scraping and still produces reproducible evidence.

Task 10B implements this as `ManualTradeProvider`; see [MANUAL_TRADE_WORKFLOW.md](MANUAL_TRADE_WORKFLOW.md).

## Aggregation Recommendation

Do not use arithmetic mean as the primary estimator. MVP aggregation should start with:

- median or lower-middle cluster for central estimate,
- plausible low/high from robust quantiles or selected cluster spread,
- explicit outlier warnings,
- no estimate when sample size is too small or prices are unnormalized.

Future weighting may consider recency, listing density, source freshness, and liquidity, but no formula is defined in Task 10A.

## Confidence And Liquidity

Confidence inputs:

- comparable count and strategy quality,
- price spread and outliers,
- source freshness,
- economy conversion freshness,
- listing liquidity,
- modifier-role confidence,
- source reliability.

Liquidity is separate from confidence. It may use listing count, density, spread, recency, and trend snapshots. Do not fabricate time-to-sale estimates.

## Quiver 6 Conceptual Strategy

Quiver 6 has high-value-looking explicit affixes such as cold damage, projectile speed, bow skill damage, critical damage bonus, critical chance, and `+1` projectile skills. For research only:

- Strict query: Quiver, similar base context, Rare, item level bracket, include `+1 Projectile Skills`, high bow skill damage, high projectile speed, high crit suffixes.
- Moderate query: preserve `+1 Projectile Skills` plus two or three strongest offensive affixes; relax tiers/rolls and ignore low-impact/filler constraints.
- Required evidence: comparable listings, normalized prices, listing timestamps, selected modifier roles, and market spread.

No actual price is assigned.

## Hypothetical Outcome Flow

For a hypothetical state such as:

```text
existing Quiver + candidate T1 Attack Speed
```

the outcome delta and source item state should be converted into a `ValuationSubject` with the same modifier-role input used for current items. The engine then builds comparable queries for the hypothetical final state without mutating the original parsed item.

## Historical Reproducibility

Persist valuation evidence snapshots:

- query definition,
- comparable observations,
- economy snapshot IDs,
- algorithm/version,
- timestamps,
- source/provenance,
- warnings.

Future recommendations must remain explainable after market prices change.
