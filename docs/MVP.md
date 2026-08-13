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
- Scenario analysis may show descriptive outcome valuation ranges before EV is possible. Scenario median and best/worst outcomes must be labeled as descriptive and partial when valuation/probability coverage is incomplete.
- Expected Value may be calculated only from `EV_READY` scenarios. It must expose gross EV, net EV, Expected Gain vs Sell Now, ROI where valid, contribution breakdowns, and refusal reasons when unavailable.
- Current value and outcome values include estimated value, plausible range, confidence, comparable count or quality where available, and timestamp.
- Rare-item valuation should be listing-derived unless actual sale evidence exists. A generated comparable search plus manual listing observations is acceptable for MVP when automatic Trade integration is not defensibly supported.
- Task 10B uses `ManualTradeProvider` for comparable evidence capture; this is not automated Trade access.
- Task 10C can aggregate manual comparable evidence into a `LISTING_DERIVED` valuation estimate when readiness policy is satisfied. This remains listing evidence, not realized sale value or a SELL NOW recommendation.
- Task 11A can report `SCENARIO_ONLY`, `INSUFFICIENT_DATA`, `NOT_APPLICABLE`, or `EV_READY`; it must not calculate EV or recommend an action.
- Task 11B calculates EV only for complete synthetic/verified-ready inputs and keeps real actions EV-unavailable when probabilities remain unknown.
- Task 12A compares SELL NOW and craft candidates only through the Advisor candidate layer. Scenario-only actions remain visible but non-rankable, and `NO_RECOMMENDATION` is allowed.
- Task 12B applies risk and bankroll policy after raw EV ranking. Risk-adjusted decisions preserve raw economic results and never promote scenario-only actions.
- Task 13A composes the vertical Rare Quiver pipeline through `CraftAdvisorOrchestrator`. Partial analysis is a valid successful result: Quiver parsing, enrichment, action legality, costs, outcomes, probability status, valuation coverage, scenario readiness, EV availability, raw Advisor decision, and optional risk adjustment are returned together without inventing missing inputs.
- Task 13B exposes the vertical pipeline through `POST /api/v1/advisor/analyze` with Pydantic DTOs, explicit league/dataset context, manual valuation evidence inputs, structured partial responses, and OpenAPI transport schemas.
- Task 14A provides the first web Craft Advisor workbench. It posts pasted Quiver clipboard text to the Advisor API, renders partial analysis and missing requirements honestly, and relies on generated OpenAPI TypeScript types instead of duplicating backend contracts.
- Task 14B extends the web workbench with manual comparable listing observation entry for the current item and API-exposed hypothetical outcome IDs. The frontend still does not calculate valuation; it sends evidence to the backend and renders returned readiness/results.
- Task 15A adds offline empirical probability evidence ingestion for explicit outcome-count observations. This enables synthetic and future source-backed `EMPIRICAL_ESTIMATE` models, but current real actions remain `UNKNOWN` unless compatible empirical evidence is explicitly supplied. No equal-probability fallback is allowed.
- Expected value, ROI, probability of profit, downside risk, and required capital are represented in the recommendation model, even if early implementations mark inputs as `NEEDS VERIFICATION`.
- Craft session data can track item states, actions, costs, total invested, current estimated value, and unrealized profit/loss.

## Out Of Scope Until Later

Profit Finder, broad Meta & Modifiers browsing, historical economy trend analysis, realized sale tracking, and additional item classes are later milestones.
