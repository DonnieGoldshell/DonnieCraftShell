# MVP 0.1: Quiver Craft Advisor

## Scope

MVP 0.1 supports only rare Quivers in Path of Exile 2. It is a vertical proof of concept for the whole product, not a broad item database.

The domain architecture must remain item-class agnostic so bows, rings, amulets, armour, and other item classes can be added later without changing the core decision engine.

## Workflow

```text
PASTE QUIVER
-> PARSE ITEM
-> IDENTIFY MODIFIERS
-> IDENTIFY TIERS
-> DETERMINE AFFIX STATE
-> ESTIMATE CURRENT VALUE
-> GENERATE VALID NEXT ACTIONS
-> GET CURRENT CRAFT COSTS
-> SIMULATE OUTCOMES
-> VALUE OUTCOMES
-> CALCULATE EV / ROI / RISK
-> COMPARE WITH SELL NOW
-> RECOMMEND CRAFT OR SELL
-> EXPLAIN RECOMMENDATION
-> PASTE RESULTING ITEM
-> REPEAT
```

## Required Behavior

- **SELL NOW** must always be included as a candidate action.
- The Advisor must never recommend crafting only because improvement is possible.
- Recommendations must include the economic reason, uncertainty, and comparison against selling.
- Any unverified PoE2 rule or data point must be marked `NEEDS VERIFICATION`.
- The MVP parser should prefer PoE2 Advanced Copy because it exposes modifier metadata. Normal Copy may parse with lower confidence and incomplete modifier metadata.
- Craft action generation must distinguish legal, illegal, and unknown applicability before any simulation or EV work. See [CRAFTING_ACTIONS.md](CRAFTING_ACTIONS.md).

## MVP Boundaries

- Rare Quivers only.
- No Profit Finder UI or strategy search.
- No automated trade execution.
- No unsupported automated Path of Exile trade scraping.
- No account integration.
- No invented currency, Omen, Essence, modifier, or crafting behavior.

## Acceptance Criteria

- Parsed item state, modifier intelligence, economy data, action generation, valuation, and recommendation logic are separable.
- MVP action candidates can be generated from a versioned crafting-action dataset, but actions requiring unknown open affix capacity must remain `UNKNOWN`.
- Action candidates may include current material costs when economy quotes exist. Missing material prices make cost incomplete but do not change crafting applicability.
- Outcome enumeration may produce hypothetical item states, but MVP recommendations must still wait for verified probability, valuation, EV, and SELL NOW comparison.
- Complete outcome enumeration is not enough for EV. Probability evidence must be explicit; no MVP recommendation may use equal-probability fallback for random crafting outcomes.
- Probability readiness for EV requires `OutcomeProbabilityModel` completeness, numeric final-outcome probabilities, and total probability mass of `1`. Deterministic operation evidence alone is insufficient.
- Current value and outcome values include estimated value, plausible range, confidence, comparable count or quality where available, and timestamp.
- Expected value, ROI, probability of profit, downside risk, and required capital are represented in the recommendation model, even if early implementations mark inputs as `NEEDS VERIFICATION`.
- Craft session data can track item states, actions, costs, total invested, current estimated value, and unrealized profit/loss.

## Out Of Scope Until Later

Profit Finder, broad Meta & Modifiers browsing, historical economy trend analysis, realized sale tracking, and additional item classes are later milestones.
