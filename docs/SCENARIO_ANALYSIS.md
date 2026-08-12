# Scenario Analysis

Task 11A adds framework-independent scenario analysis. It composes current valuation, craft action candidates, outcome sets, probability models, and hypothetical outcome valuations without calculating EV or ranking actions.

Task 11B consumes only `EV_READY` scenario analyses for strict EV calculation. See [EXPECTED_VALUE.md](EXPECTED_VALUE.md).

## Boundary

```text
Current Valuation
+ CraftActionCandidate
+ CraftOutcomeSet
+ OutcomeProbabilityModel
+ OutcomeValuation[]
-> ScenarioAnalysis
```

`ScenarioAnalysis` is descriptive. It can be useful when EV is impossible.

## What It May Calculate

Allowed scenario statistics:

- outcome count,
- valued and unvalued outcome counts,
- valuation completeness,
- probability completeness,
- best/worst among currently valuated outcomes,
- median of valuated outcomes,
- upside/downside relative to current listing-derived valuation,
- per-outcome net scenario value after action material cost.

These are not probability-weighted.

## What It Must Not Calculate

Task 11A must not produce:

- expected value,
- probability of profit/loss,
- action ranking,
- Craft Advisor recommendation,
- sell/craft decision.

Scenario median is not Expected Value. Best/worst scenario is not a probability-weighted expectation.

## Outcome Valuations

`OutcomeValuation` maps `outcome_id -> ValuationResult` beside the `CraftOutcomeSet`. It does not mutate hypothetical outcome states. Missing valuations remain explicit and count against completeness.

Best/worst/median values use only valuated outcomes. When some outcomes are unvalued, the analysis warns that these statistics are partial.

## Current Baseline

The current item valuation acts as the SELL NOW baseline conceptually, but it remains a listing-derived estimate, not a guaranteed sale value and not a recommendation to sell.

## Cost

Action material cost comes from `CraftMaterialCost`. Scenario net value is:

```text
outcome listing-derived valuation - craft material cost
```

This is a descriptive scenario value, not EV.
