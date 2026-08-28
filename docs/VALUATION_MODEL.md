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
- `ComparableValuationPolicy`: versioned policy for the conservative comparable-anchor valuation model.
- `ComparableValuationAnchor`: one structured comparable listing interpreted as lower, upper, equivalent, or uninterpreted anchor evidence.
- `ComparableValuationUsefulness`: deterministic usefulness assessment for one structured comparable, derived from relevance, quality similarity, freshness, and observable item-state differences.
- `ComparableMarketInferenceStatus`: `INSUFFICIENT_EVIDENCE`, `BROAD_BRACKET_ONLY`, or `INFERRED_MARKET_BAND`.
- `ComparableValuationEstimate`: bracket-style listing-derived estimate from structured anchors, or an explicit insufficient-data result.
- `ComparableValuationModel`: conservative v1 model over manual structured comparables.
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

## Comparable Valuation Model v1

Issue 63 adds `ComparableValuationModel` as a conservative preview model over
manual structured comparable listings. It does not replace
`ValuationAggregator`; it adds an inspectable bracket beside the existing
median/range output.

The v1 model requires structured evidence for each usable anchor:

- normalized listing price in Exalted economic units
- parsed comparable item state
- structural `ComparableRelevance`
- directional `ComparableQualityDelta`

Price-only evidence is retained but receives `UNINTERPRETED` anchor status. The
model does not fabricate a relevance score, quality delta, or price adjustment.

Anchor roles are assigned from quality delta, not from listing price:

- `LOWER_ANCHOR`: the current item is structurally stronger on more matched
  modifiers than the comparable, so the comparable listing can only support a
  lower-style anchor.
- `UPPER_ANCHOR`: the comparable item is structurally stronger on more matched
  modifiers, so the comparable listing can only support an upper-style anchor.
- `EQUIVALENT_ANCHOR`: matched modifier quality is roughly equivalent.
- `UNINTERPRETED`: missing normalized price, insufficient relevance, missing
  quality delta, or no directional quality evidence.

Default policy `comparable-valuation-model-v1` requires at least two
interpretable structured anchors, a high-relevance score of at least `0.75`,
and both lower/equivalent and upper/equivalent bracket evidence before emitting
a broad bracket center. The bracket center preserves backward-compatible
preview behavior from Issue 63, but market inference v1 marks it explicitly as
`BROAD_BRACKET_ONLY`; it is a descriptive listing-derived bracket center, not a
market estimate, realized sale price, EV input, or recommendation.

Issue 65 adds scoped market inference on top of those anchors. Each structured
comparable receives a `ComparableValuationUsefulness` assessment. Usefulness is
deterministic and explainable:

- structural relevance score,
- modifier quality similarity from `ComparableQualityDelta`,
- evidence freshness,
- reductions for base-type differences, special-state differences, origin
  differences, and unmatched modifiers.

Usefulness is not a price multiplier and does not change whether the current
item is better or worse than a comparable. Listing price remains separate from
structural relevance and quality direction.

An `INFERRED_MARKET_BAND` may be emitted only when enough high-usefulness
comparables form a tight enough cluster under the configured policy. The v1
central inferred value uses a Decimal weighted median over those close
comparables, and the inferred band uses deterministic Decimal quantiles. The
model never treats a distant lower anchor and distant upper anchor as a
high-confidence midpoint market estimate.

Wide anchor spreads are preserved and warned on rather than hidden. A small
two-anchor pilot can produce `PARTIAL` with low confidence even when a bracket
exists. If anchor directions conflict with observed listing prices, the model
fails closed with `INSUFFICIENT_DATA` rather than reversing the quality-derived
anchor roles. If evidence is contradictory, stale, distant, or too sparse, the
inference status remains `INSUFFICIENT_EVIDENCE` or `BROAD_BRACKET_ONLY`.

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
each structured comparable and returns an optional `comparable_valuation_estimate`
summary. The preview still does not discard low-relevance comparables or alter
the existing valuation aggregation behavior.

Issue 65 extends the preview summary with market-inference diagnostics:
`inference_status`, optional `inferred_market_central/low/high`,
`usefulness_assessments`, `influential_observation_ids`, and a methodology
summary. The UI should show these fields as diagnostics beside the manual
listing evidence. They are not Advisor decisions and they do not bypass EV or
probability readiness gates.

Issue 67 adds a separate preview-level `market_valuation` presentation contract
so player-facing headline valuation follows the market-inference state:

- `INSUFFICIENT_EVIDENCE`: no headline point estimate; communicate
  insufficient market evidence.
- `BROAD_BRACKET_ONLY`: no headline point estimate; show the supported market
  range only.
- `INFERRED_MARKET_BAND`: the inferred central value and inferred band may be
  used as the headline estimated market value.

The legacy manual evidence median remains available as
`legacy_statistical_median` diagnostics, but it must not masquerade as
estimated market value when the structured inference model does not support a
point estimate.

## Listing Evidence

`ComparableResult` represents listing/observation evidence, not completed sale evidence. A listing price must not be treated as realized sale value.

Duplicate listing IDs are detected in `ComparableEvidenceSet` when supplied. Manual observations without listing IDs can remain separate but should be treated as lower-confidence evidence by future aggregation.

## Aggregation

`ValuationAggregator` consumes one or more `ComparableEvidenceSet` objects. It can produce a `LISTING_DERIVED` estimate when policy thresholds are met, or `NONE` when evidence is insufficient.

The central estimate is the Decimal median. Plausible low/high values use deterministic nearest-lower-index quantiles. Duplicate listing IDs and outlier exclusions are retained in the result with explicit reasons. Arithmetic mean is not the primary estimator.

`ValuationResult` preserves used comparable IDs, excluded comparables, strategy composition, economy snapshot IDs, policy ID, methodology, league, warnings, confidence, and listing-evidence liquidity.

## Manual Evidence Persistence Boundary

Persisted manual valuation evidence remains comparable-listing evidence, not a valuation result. The workspace stores operator-entered observations by `current` or `outcome:{outcome_id}` subject identity so current-item and hypothetical-outcome evidence stay isolated across API/browser restarts. Preview and Advisor valuation readiness still come from the valuation evidence/aggregation path. See [MANUAL_VALUATION_WORKSPACE.md](MANUAL_VALUATION_WORKSPACE.md).
