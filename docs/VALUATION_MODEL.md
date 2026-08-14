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
- `ManualListingObservation`: user-entered listing observation.
- `ComparableResult`: normalized listing evidence when currency conversion is available.
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
`outcome_id`.

## Listing Evidence

`ComparableResult` represents listing/observation evidence, not completed sale evidence. A listing price must not be treated as realized sale value.

Duplicate listing IDs are detected in `ComparableEvidenceSet` when supplied. Manual observations without listing IDs can remain separate but should be treated as lower-confidence evidence by future aggregation.

## Aggregation

`ValuationAggregator` consumes one or more `ComparableEvidenceSet` objects. It can produce a `LISTING_DERIVED` estimate when policy thresholds are met, or `NONE` when evidence is insufficient.

The central estimate is the Decimal median. Plausible low/high values use deterministic nearest-lower-index quantiles. Duplicate listing IDs and outlier exclusions are retained in the result with explicit reasons. Arithmetic mean is not the primary estimator.

`ValuationResult` preserves used comparable IDs, excluded comparables, strategy composition, economy snapshot IDs, policy ID, methodology, league, warnings, confidence, and listing-evidence liquidity.
