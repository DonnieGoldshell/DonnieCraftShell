# Valuation Aggregation

Task 10C implements conservative aggregation over manual comparable listing evidence only. It does not call Trade endpoints, infer realized sale prices, calculate EV, or recommend actions.

## Estimate Type

All produced numeric estimates are `LISTING_DERIVED`. This means the result is derived from observed listings supplied through `ManualTradeProvider`; it is not a completed-sale value and not a known true market value.

If evidence is insufficient, `ValuationResult.estimate_type` is `NONE` and `estimated_value`, `plausible_low`, and `plausible_high` remain unavailable.

## Algorithm

`ValuationAggregator` uses a configurable `ValuationAggregationPolicy`.

Default Task 10C behavior:

- require at least 2 usable normalized comparables for any estimate,
- require at least 3 usable normalized comparables for `READY`,
- prefer `STRICT` evidence when it reaches the ready threshold,
- fall back to `STRICT + MODERATE` when strict evidence is insufficient,
- use the Decimal median as the central estimate,
- use Decimal quantiles for plausible low/high bounds,
- retain all evidence and record excluded comparable IDs plus reasons.

Arithmetic mean is not used as the primary estimator.

## Quantile Rule

Quantiles use a deterministic nearest-lower-index rule:

```text
index = floor((n - 1) * quantile)
```

Values are sorted as `Decimal`. No binary floating-point statistical library is used.

## Duplicate And Outlier Policy

Known duplicate listing IDs are not counted as independent evidence when `exclude_duplicate_listing_ids` is enabled. The duplicate observation is retained in `excluded_comparables` with reason `DUPLICATE_LISTING`.

Outlier handling is deterministic and policy-driven. The default flags/excludes values above `outlier_median_multiplier * median` when at least three usable results exist. Excluded evidence is never deleted silently.

## Readiness And Confidence

Readiness is structural:

- `INSUFFICIENT_DATA`: no defensible estimate under policy,
- `PARTIAL`: an estimate exists but evidence is below the ready threshold,
- `READY`: configured evidence threshold is met.

Confidence is separate from readiness. It records plain-language reasons from comparable count, strategy quality, price spread, stale economy conversion evidence, and exclusions.

## Liquidity

Liquidity is an evidence-based listing indicator only. It uses usable comparable count and price spread, and must not be interpreted as time-to-sale or realized demand.

## Reproducibility

`ValuationResult` retains evidence set IDs, used comparable IDs, excluded comparables, aggregation policy ID, strategy composition, economy snapshot IDs, league, timestamps, methodology, provenance, and warnings.
