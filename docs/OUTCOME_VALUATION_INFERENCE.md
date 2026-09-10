# Outcome Valuation Inference

Issue 91 adds a narrow outcome-valuation inference path for Craft Advisor analysis.

The purpose is to reuse existing structured manual comparable evidence against each hypothetical outcome item state. It does not add a new valuation algorithm, scrape Trade, assign probabilities, or invent prices.

## Flow

```text
CraftOutcomeSet
+ current/manual ComparableEvidenceSet
-> materialize each HypotheticalItemState
-> rescore each comparable against that materialized outcome item
-> ValuationAggregator
-> ComparableValuationModel
-> ValuationResult only when market inference supports it
```

Each outcome is evaluated independently. A comparable that is useful for one removed-modifier outcome may be insufficient for another. One inferable outcome never makes sibling outcomes valuation-ready.

## Market Authority

Comparable Valuation Model inference status controls whether an outcome has a point valuation:

- `INFERRED_MARKET_BAND`: may produce a listing-derived `ValuationResult` point estimate and band.
- `BROAD_BRACKET_ONLY`: preserves the supported range as diagnostics, but does not produce a point outcome valuation.
- `INSUFFICIENT_EVIDENCE`: produces no point outcome valuation.

Legacy aggregation medians remain internal diagnostics. They must not clear outcome valuation blockers when market inference does not support a point value.

## Manual Evidence Precedence

Explicit per-outcome manual valuation evidence remains the stronger signal for that specific outcome ID. Saved workspace evidence is still inert until submitted in an Advisor analyze request.

Outcome inference only fills gaps when current/manual comparable evidence can be defensibly rescored for the materialized hypothetical item state.

## Safety Rules

Outcome valuation inference must not:

- reuse current-item relevance without rescoring,
- copy one outcome valuation to sibling outcomes,
- use current item value as an outcome value,
- use a midpoint or upper/lower range endpoint as a point estimate,
- apply percentage haircuts,
- change probability completeness,
- clear EV readiness without complete probability and valuation evidence.

## Bramble Spike Pilot

The current Gloom Barb / Bramble Barb / Skull Quill pilot evidence supports a broad current-item bracket of roughly `45-450 Divine`.

For the six Bramble Spike Annulment outcomes, the same evidence is rescored per hypothetical state. It does not produce any `INFERRED_MARKET_BAND` point outcome valuations, so the honest result remains:

```text
Outcome valuations ready: 0 / 6
Probability: UNKNOWN
EV: unavailable
```

This is a useful result. It means the evidence is visible and reproducible, while the Advisor still refuses to fabricate outcome values or EV.
