# Valuation Model

Task 10B implements framework-independent rare-item valuation evidence contracts. Task 10C adds conservative manual listing aggregation. The valuation layer does not scrape Trade, calculate EV, or recommend actions.

## Boundary

```text
ValuationSubject
-> ComparableQuery
-> TradeProvider
-> ComparableResult[]
-> ComparableEvidenceSet
-> ValuationAggregator
```

Current parsed items and hypothetical outcome states both become `ValuationSubject`. This keeps future current-value and outcome-value workflows on the same interface.

## Contracts

Executable contracts live in `packages/shared/donniecraftshell_contracts/valuation.py`.

- `ValuationSubject`: current or hypothetical item state prepared for valuation.
- `ModifierComparableRole`: `VALUE_DRIVING`, `SUPPORTING`, `IGNORE_FOR_COMPARABLE`, `UNKNOWN`.
- `ModifierComparableRoleAssignment`: manual/provenance-carrying role assignment.
- `ModifierConstraint`: query-level modifier requirement.
- `ComparableQuery`: DonnieCraftShell query definition, not a Trade API payload.
- `ManualTradeProvider`: no-network provider for manual comparable observations.
- `StructuredComparableItem`: optional parsed Advanced Copy item state for a comparable listing.
- `ManualListingObservation`: user-entered listing observation, optionally including `StructuredComparableItem`.
- `ComparableResult`: normalized listing evidence when currency conversion is available.
- `ComparableRelevance`: deterministic structural similarity evidence between the current item and a structured comparable.
- `ComparableQualityDelta`: deterministic directional modifier-quality evidence for corresponding parsed modifiers.
- `ComparableEvidenceSet`: query plus comparable results and readiness.
- `ValuationAggregationPolicy`: configurable readiness, quantile, duplicate, stale, and outlier policy.
- `ValuationAggregator`: manual comparable aggregation using robust Decimal statistics.
- `ValuationResult`: listing-derived estimate or explicit no-estimate result.

## Readiness

`ComparableEvidenceSet.readiness` is structural, not a claim of price accuracy.

- `INSUFFICIENT_DATA`: zero usable normalized comparables.
- `PARTIAL`: some usable comparables, below configured threshold.
- `READY`: configured minimum usable evidence reached.

The minimum comparable threshold is a DonnieCraftShell policy setting, not market truth.

## Currency Normalization

Manual listing observations preserve original amount and currency. The provider reuses `EconomyRepository` to normalize currencies to Exalted economic units.

If conversion is missing, normalized value remains unavailable. Missing conversion is never zero.

## Structured Comparable Item State

Task 53 extends manual comparable evidence with optional full PoE2 Advanced Copy text for the comparable listing. The API parses that text through the canonical item parser and stores the resulting structured item state beside listing metadata.

Price-only/manual rows remain backward compatible, but they are not structurally verified comparable evidence. Notes such as "similar quiver" remain prose context only; machine-readable comparability comes from parsed item state.

Structured comparable parsing uses the same PoE2 parser as current-item analysis.
For Advanced Copy quivers, the returned comparable summary preserves supported
base metadata, implicit modifiers, explicit prefix/suffix modifiers, tiers,
tags, roll/range observations, and modifier origins such as `NATURAL`,
`CRAFTED`, `FRACTURED`, and `DESECRATED`. Item-state lines such as `Fractured
Item` are retained as special state rather than causing supported modifier
blocks to degrade into unparsed text.

Malformed comparable clipboard text is rejected during preview/save/update rather than persisted as trusted structure.

## Comparable Relevance

Task 59 adds deterministic structural relevance assessment for parsed current
items and parsed structured comparables. The relevance policy is versioned as
`comparable-relevance-policy-v1` and compares only observable item structure:
item class, rarity, item level, base type, implicit effect, explicit modifier
side, parsed semantic identity, tier, origin, tags, and roll/range observations
already retained by the parser. Item-level special states such as `FRACTURED`
are recorded as base/context differences rather than folded into modifier
identity.

The relevance band is explanatory metadata:

- `HIGH`
- `MEDIUM`
- `LOW`
- `NOT_COMPARABLE`
- `INSUFFICIENT_STATE`

The optional numeric score is a normalized structural-similarity score, not a
market-value weight. It must not be interpreted as a price premium, sale
probability, or valuation confidence. Modifier comparisons are split into
matched, differing, missing, and extra groups so later valuation logic can
inspect exact matches, tier differences, origin differences, and unmatched
modifiers without scraping UI prose.

Price-only observations have no fabricated relevance score. If the current
item or comparable item cannot be parsed with explicit modifier state,
relevance remains unavailable or `INSUFFICIENT_STATE`.

## Modifier Quality Delta

Task 61 adds `ComparableQualityDelta` as a separate signal from structural
relevance. Structural relevance answers whether two item states are comparable;
modifier quality delta answers, for same-side corresponding semantic modifier
identities, whether the current item, the comparable item, or neither has the
stronger observable modifier evidence.

The quality policy is versioned as
`comparable-modifier-quality-delta-policy-v1`. It may classify modifier pairs
as `CURRENT_BETTER`, `COMPARABLE_BETTER`, `ROUGHLY_EQUIVALENT`, `UNKNOWN`,
`MISSING_FROM_COMPARABLE`, or `EXTRA_ON_COMPARABLE`. Directional comparisons
use parsed tier numbers when both sides have them, where lower tier number is
stronger. For same-tier modifiers, parsed roll/value quality may be compared
only when both sides expose value plus displayed min/max ranges; otherwise the
relationship remains equivalent or unknown with reasons.

Modifier origin/state differences such as `NATURAL` versus `FRACTURED` are
preserved explicitly. They do not create an economic premium or penalty in this
layer. Missing or extra modifiers remain visible and are not falsely classified
as tier comparisons.

Quality delta counts are inspectable evidence only. They must not be used as
market-value multipliers, valuation weights, EV inputs, Advisor ranking, or
sale-price inference.

## Advisor API Preview

The Advisor API exposes a thin manual-evidence preview endpoint for the web
workflow:

```text
POST /api/v1/advisor/manual-valuation/preview
```

This endpoint is transport glue over the same valuation contracts. It builds a
manual `ComparableQuery`, converts `ManualListingObservation` rows through
`ManualTradeProvider`, creates a `ComparableEvidenceSet`, and runs
`ValuationAggregator`. Current-item evidence and hypothetical-outcome evidence
remain separate by subject ID; outcome evidence must carry the deterministic
`outcome_id`. If an observation includes `comparable_clipboard_text`, the
endpoint parses and returns a structured comparable item summary in each
`ComparableResult`. If the request also includes `subject_clipboard_text`, the
preview attaches `ComparableRelevance` and `ComparableQualityDelta` results to
each structured comparable. The preview still does not discard low-relevance
comparables or alter valuation aggregation behavior.

## Listing Evidence

`ComparableResult` represents listing/observation evidence, not completed sale evidence. A listing price must not be treated as realized sale value.

Duplicate listing IDs are detected in `ComparableEvidenceSet` when supplied. Manual observations without listing IDs can remain separate but should be treated as lower-confidence evidence by future aggregation.

## Aggregation

`ValuationAggregator` consumes one or more `ComparableEvidenceSet` objects. It can produce a `LISTING_DERIVED` estimate when policy thresholds are met, or `NONE` when evidence is insufficient.

The central estimate is the Decimal median. Plausible low/high values use deterministic nearest-lower-index quantiles. Duplicate listing IDs and outlier exclusions are retained in the result with explicit reasons. Arithmetic mean is not the primary estimator.

`ValuationResult` preserves used comparable IDs, excluded comparables, strategy composition, economy snapshot IDs, policy ID, methodology, league, warnings, confidence, and listing-evidence liquidity.

## Manual Evidence Persistence Boundary

Persisted manual valuation evidence remains comparable-listing evidence, not a valuation result. The workspace stores operator-entered observations by `current` or `outcome:{outcome_id}` subject identity so current-item and hypothetical-outcome evidence stay isolated across API/browser restarts. Preview and Advisor valuation readiness still come from the valuation evidence/aggregation path. See [MANUAL_VALUATION_WORKSPACE.md](MANUAL_VALUATION_WORKSPACE.md).
