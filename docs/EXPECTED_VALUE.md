# Expected Value

Task 11B implements a strict framework-independent Expected Value Engine. It calculates EV only when `ScenarioAnalysis.decision_readiness == EV_READY` and all probability, valuation, cost, and provenance prerequisites remain valid.

## Formula

For a craft action:

```text
gross_expected_outcome_value =
  sum(probability_i * outcome_listing_derived_value_i)

net_expected_value =
  gross_expected_outcome_value - craft_material_cost

expected_gain_vs_sell_now =
  net_expected_value - current_item_listing_derived_value
```

All arithmetic uses `Decimal` and normalized Exalted economic units.

## Terminology

- **Gross Expected Outcome Value**: probability-weighted listing-derived value of resulting items before craft cost.
- **Net Expected Value**: gross expected outcome value minus craft material cost.
- **Expected Gain vs Sell Now**: net expected value minus the current item listing-derived valuation.

Expected Gain vs Sell Now is not guaranteed realized profit. The current valuation is listing-derived market evidence, not a confirmed sale.

## Hard Gate

`ExpectedValueEngine` refuses calculation unless:

- scenario readiness is `EV_READY`,
- action is applicable,
- action cost is complete and normalized,
- probability model is `COMPLETE`,
- probability mass is valid,
- every probability-bearing outcome has exactly one usable valuation,
- current item valuation is usable,
- outcome IDs align exactly,
- dataset, valuation evidence, probability model, and economy snapshot references exist.

No partial EV, probability renormalization, missing valuation substitution, or zero-cost fallback is allowed.

## Contributions

Each result includes `OutcomeExpectedValueContribution`:

```text
outcome_id
probability
valuation
weighted_contribution
```

The contribution sum must match `gross_expected_outcome_value` within the existing Decimal probability tolerance.

## ROI

When craft cost is greater than zero:

```text
ROI_on_craft_cost = expected_gain_vs_sell_now / craft_material_cost
```

If craft cost is zero, ROI is unavailable rather than divided by zero.

## Bounds

If every outcome valuation includes plausible low/high values, the engine also calculates low/high net EV bands:

```text
low_net_expected_value = sum(p_i * low_i) - cost
high_net_expected_value = sum(p_i * high_i) - cost
```

Missing bounds make the EV range unavailable. Confidence is not converted into probabilistic uncertainty.

## Non-Goals

The EV Engine does not rank actions, recommend crafting, estimate probabilities, scrape markets, or run Profit Finder logic.
