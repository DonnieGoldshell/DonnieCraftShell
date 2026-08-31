# Stop/Continue Decision Economics

Issue 71 adds a narrow sell-now versus continue-crafting economic presentation layer. It does not add new valuation, probability, EV, ranking, Trade access, or crafting mechanics.

## Purpose

The layer answers whether DonnieCraftShell has enough compatible evidence to present a player-facing comparison between:

- selling the current item now, and
- continuing with the best EV-ready craft candidate selected by the existing Advisor decision engine.

It reuses existing results. It does not recalculate Expected Value and it does not rank scenario-only actions.

## Current Market Valuation Authority

`CurrentMarketValuation.status` is authoritative for the sell-now baseline:

- `ESTIMATED_MARKET_VALUE`: may provide a point sell-now baseline.
- `SUPPORTED_RANGE_ONLY`: may show the supported range, but must not provide a point sell-now baseline.
- `INSUFFICIENT_MARKET_EVIDENCE`: no point sell-now baseline.

`BROAD_BRACKET_ONLY` from the Comparable Valuation Model maps to `SUPPORTED_RANGE_ONLY`. A bracket such as `45-450 Divine` must not be converted to a midpoint, median, upper bound, or expected sale value.

The legacy/manual evidence median can remain available for diagnostics, but it must not masquerade as market valuation when the market inference state does not support a point estimate.

## Continue-Crafting Side

The continue side may be compared only when the existing Advisor pipeline has an EV-ready craft candidate with:

- `ScenarioAnalysis` readiness `EV_READY`,
- an available `ExpectedValueResult`,
- complete normalized prospective craft material cost,
- complete probability and outcome valuation inputs already accepted by the EV gate.

Historical craft investment spend is cost-basis context. It is not added again as a marginal prospective craft cost. Incomplete historical cost basis can block profit-position claims, but it does not by itself block a complete forward sell-now versus continue-crafting comparison.

## Result Contract

`StopContinueDecisionEconomics` exposes:

- decision type: `SELL_NOW`, `CRAFT`, or `NO_RECOMMENDATION`,
- readiness such as `READY`, `NO_POINT_SELL_BASELINE`, `NO_EV_READY_CONTINUATION`, or `INCOMPLETE_PROSPECTIVE_COST`,
- sell-now value only when an authoritative point market estimate exists,
- best continue action and EV values only from existing EV results,
- expected incremental craft cost,
- gain/loss versus sell now when comparison is valid,
- blockers, warnings, algorithm version, and decision-margin source.

The decision-margin source remains `AdvisorDecisionEngine`; this layer does not reapply margin or risk policy.

## UI Semantics

For `SUPPORTED_RANGE_ONLY`, the player-facing UI should show:

- estimated market value: insufficient precision,
- supported market range: the inferred bracket, for example `45-450 Divine`,
- confidence from the market inference model.

It must not show the legacy median as "Estimated Value".
