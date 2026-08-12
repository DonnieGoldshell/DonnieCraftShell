# Valuation Model

Task 10B implements framework-independent rare-item valuation evidence contracts. It does not estimate market value, scrape Trade, calculate EV, or recommend actions.

## Boundary

```text
ValuationSubject
-> ComparableQuery
-> TradeProvider
-> ComparableResult[]
-> ComparableEvidenceSet
-> future ValuationAggregator
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
- `ValuationResult`: future aggregation output shape.

## Readiness

`ComparableEvidenceSet.readiness` is structural, not a claim of price accuracy.

- `INSUFFICIENT_DATA`: zero usable normalized comparables.
- `PARTIAL`: some usable comparables, below configured threshold.
- `READY`: configured minimum usable evidence reached.

The minimum comparable threshold is a DonnieCraftShell policy setting, not market truth.

## Currency Normalization

Manual listing observations preserve original amount and currency. The provider reuses `EconomyRepository` to normalize currencies to Exalted economic units.

If conversion is missing, normalized value remains unavailable. Missing conversion is never zero.

## Listing Evidence

`ComparableResult` represents listing/observation evidence, not completed sale evidence. A listing price must not be treated as realized sale value.

Duplicate listing IDs are detected in `ComparableEvidenceSet` when supplied. Manual observations without listing IDs can remain separate but should be treated as lower-confidence evidence by future aggregation.

## Aggregation Boundary

`ValuationAggregator` is a stub boundary in Task 10B. It returns readiness and evidence IDs but no market estimate. Future Task 10C may implement robust aggregation from `ComparableEvidenceSet`.
