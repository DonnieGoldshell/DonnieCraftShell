# Decision Readiness

Task 11A introduces strict readiness gates for future EV and Advisor work.

## Statuses

- `NOT_APPLICABLE`: the action cannot be performed under current applicability evidence.
- `INSUFFICIENT_DATA`: there is too little outcome valuation data for useful scenario analysis.
- `SCENARIO_ONLY`: descriptive scenario analysis is available, but EV prerequisites are not complete.
- `EV_READY`: all probability, valuation, applicability, and cost prerequisites are complete enough for a future EV engine.

`EV_READY` does not calculate EV in Task 11A.

## EV Readiness Requirements

All of these must be true:

- action applicability is `APPLICABLE`,
- action material cost is complete,
- outcome set exists for the action,
- probability model is `COMPLETE`,
- probability mass is valid through `can_calculate_expected_value(...)`,
- every probability-model outcome has a usable valuation,
- current item valuation is usable,
- currency normalization is usable.

If any requirement fails, EV is not ready.

## Scenario-Only Value

`SCENARIO_ONLY` is intentionally useful. For example, Quiver 6 Annulment can expose six possible removal outcomes and synthetic valuations for some outcomes while probability remains `UNKNOWN`. DonnieCraftShell may show descriptive ranges, but it must not imply expected value.

## Explainability

Readiness results retain reasons such as:

- valuation coverage `4/6`,
- probability model is not EV-ready,
- action material cost is incomplete,
- current valuation is unavailable,
- action is not applicable.

These reasons will later feed Advisor explanations without weakening uncertainty rules.
