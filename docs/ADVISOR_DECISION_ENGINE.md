# Advisor Decision Engine

Task 12A implements the first framework-independent Advisor Decision Engine. It compares SELL NOW with craft candidates only when evidence is methodologically compatible.

## Candidate Types

`AdvisorCandidate` supports:

- `SELL_NOW`
- `CRAFT_ACTION`

SELL NOW is represented as a normal candidate with current listing-derived valuation, zero craft cost, valuation readiness, confidence, evidence references, and warnings.

Craft actions remain visible even when they cannot be ranked.

## Decision Types

- `SELL_NOW`: current listing-derived valuation is the defensible choice under policy.
- `CRAFT`: an EV-ready craft beats SELL NOW by the configured margin.
- `NO_RECOMMENDATION`: evidence is insufficient for a defensible choice.

`NO_RECOMMENDATION` is a valid product answer.

## Rankability

Craft actions enter EV ranking only when:

- action applicability is `APPLICABLE`,
- scenario readiness is `EV_READY`,
- `ExpectedValueResult` is `AVAILABLE`,
- craft cost is complete,
- current valuation is usable,
- required evidence/provenance references exist.

Scenario-only actions are returned as `NON_RANKABLE_SCENARIO`. They may show outcome coverage, scenario values, warnings, and costs, but their median, best case, or hypothetical upside must never be compared against SELL NOW.

`NOT_APPLICABLE`, `UNKNOWN`, and insufficient-data candidates are preserved for explanation but never ranked.

## Ranking Rule

Rankable craft actions are compared by `ExpectedValueResult.net_expected_value` and `expected_gain_vs_sell_now`.

The engine does not recalculate EV. `ExpectedValueEngine` remains the source of EV math.

SELL NOW wins when no EV-ready craft exceeds the current listing-derived value by the configured decision margin.

## Policy

`AdvisorPolicy` is versioned by `dc-advisor-v1` and supports:

- minimum absolute expected gain,
- minimum relative expected gain,
- whether SELL NOW may be recommended when no EV-ready craft exists,
- whether current valuation must be `READY`.

These are DonnieCraftShell policy settings, not market facts.

## No Recommendation

The engine returns `NO_RECOMMENDATION` when current valuation is insufficient, all crafts are scenario-only/non-rankable, or evidence quality prevents a defensible choice.

The engine does not automate gameplay, scrape Trade, estimate probabilities, rank Profit Finder strategies, or execute crafts.

Risk and bankroll policy is separate. See [RISK_AND_BANKROLL.md](RISK_AND_BANKROLL.md). Risk may veto or annotate an EV-positive craft, but it must preserve the raw Advisor decision and raw EV values.

Task 13A orchestration is also separate. See [ADVISOR_ORCHESTRATION.md](ADVISOR_ORCHESTRATION.md). The orchestrator feeds `AdvisorDecisionEngine` with existing `AdvisorCraftInput` objects and preserves the resulting raw decision; it does not rank actions itself or recalculate EV.

Issue 71 adds [STOP_CONTINUE_DECISION_ECONOMICS.md](STOP_CONTINUE_DECISION_ECONOMICS.md), a compact presentation layer for sell-now versus continue-crafting economics. It uses `CurrentMarketValuation.status` as the authority for whether a point sell-now baseline exists, so `SUPPORTED_RANGE_ONLY`/`BROAD_BRACKET_ONLY` evidence can show a supported range but cannot be ranked as a point market value.
