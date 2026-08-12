# Decision Engine Specification

## Purpose

The Decision Engine compares legal crafting actions against selling immediately. It produces transparent economic recommendations, not generic crafting optimism.

## Core Rule

**SELL NOW is always a first-class action.** Continuing to craft is recommended only when the economic case beats selling after cost, risk, uncertainty, and bankroll constraints are considered.

Task 12A implements the first Advisor candidate layer. SELL NOW is a first-class candidate, EV-ready craft actions are rankable, and scenario-only actions remain informative but non-rankable. `NO_RECOMMENDATION` is valid when evidence is insufficient.

## Core Concepts

- **Parsed item**: normalized representation of pasted PoE2 clipboard text.
- **Item-class module**: Quiver-specific definitions for bases, modifiers, affix rules, and legal actions.
- **Craft quality**: how promising the crafting state is, based on modifier quality, tier quality, build relevance, affix structure, and remaining potential.
- **Market value**: estimated sale value. This is separate from craft quality.
- **Economy snapshot**: league-specific prices using normalized units where `1 Exalted Orb = 1 economic unit`.
- **Crafting action**: legal next step with cost, possible outcomes, assumptions, and provenance.
- **Expected value**: weighted outcome value minus crafting cost.
- **Confidence**: explicit uncertainty attached to valuations, probabilities, data, and recommendations.

## Expected Value

For an action with outcomes:

```text
EV = sum(probability_of_outcome * market_value_of_outcome) - crafting_cost
```

The system should eventually calculate expected net value, expected profit/loss, ROI, probability of profit, probability of significant loss, downside, upside, and required capital.

Advisor ranking must use `ExpectedValueResult` produced by the EV Engine. It must not recalculate EV or substitute scenario median/best-case values for EV.

## Risk And Bankroll

Users should eventually provide a bankroll and risk profile: conservative, balanced, or aggressive.

Risk preference must not alter the underlying expected-value calculation. It may alter the final recommendation based on bankroll exposure and variance. For example, a positive-EV craft requiring 80% of bankroll may be inappropriate for a conservative user.

## Valuation Engine

Rare item valuation is uncertain and must not be represented as falsely precise. A valuation should include estimated market value, plausible range, confidence score, comparable observation count or quality, and timestamp.

Supported comparable strategies should include strict comparables, moderate comparables, and build-equivalent comparables. Trade integrations must remain replaceable adapters. Unsupported automated trade scraping must not be implemented.

## Craft Session

The architecture should support repeated paste-and-recalculate sessions. Track item states, actions, step costs, total invested, current estimated value, and unrealized profit/loss. Future versions may track realized sale value and long-term crafting performance.

## Verification Requirements

The following are `NEEDS VERIFICATION`: PoE2 clipboard format, Quiver bases, item-level requirements, modifier tiers, prefix/suffix classification, legal crafting actions, currency behavior, Omens, Essences, outcome probabilities, and market data sources.
