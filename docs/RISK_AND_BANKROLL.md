# Risk And Bankroll Policy

Task 12B adds a framework-independent risk layer for Craft Advisor. It filters or annotates raw Advisor decisions without mutating `ExpectedValueResult`.

## Separation

```text
AdvisorDecisionEngine -> raw economic decision
AdvisorRiskPolicyEngine -> risk-adjusted decision
```

Raw EV ranking remains visible. Risk policy may reject a raw EV winner, but it must not rewrite `net_expected_value`, `expected_gain_vs_sell_now`, probabilities, or valuations.

## Risk Profiles

Built-in presets are DonnieCraftShell policy defaults, not mathematical truths:

- `CONSERVATIVE`: max bankroll exposure `20%`, partial downside produces caution.
- `BALANCED`: max bankroll exposure `50%`.
- `AGGRESSIVE`: max bankroll exposure `80%`.

All thresholds are configurable through `RiskPolicy` or `AdvisorRiskContext` overrides.

## Exposure

Bankroll exposure is:

```text
craft_material_cost / bankroll
```

Example: `200 Ex / 1000 Ex = 20%`.

Missing bankroll is not treated as infinite bankroll. If bankroll-specific policy is required, the assessment becomes `INSUFFICIENT_DATA`.

## Capital Exposure

`CapitalExposure` separates:

- craft material cost,
- current item listing-derived value,
- combined economic exposure,
- bankroll exposure,
- scenario downside where modeled.

The current item value is not assumed to be fully lost in every bad outcome.

## Downside

Downside can use `ScenarioAnalysis.downside_relative_to_current`. If valuation coverage is partial, the result is labeled as worst currently valuated scenario, not maximum possible loss.

Policy may reject on configured downside limits or warn/caution on partial downside evidence.

## Risk-Adjusted Result

`RiskAdjustedAdvisorDecision` retains:

- raw decision,
- raw winner,
- risk-adjusted winner,
- whether policy changed the outcome,
- per-candidate risk assessments,
- risk policy/version,
- advisor algorithm version.

Scenario-only candidates cannot be promoted by risk policy. SELL NOW is treated as no new craft material exposure, not absolutely risk-free market certainty.
