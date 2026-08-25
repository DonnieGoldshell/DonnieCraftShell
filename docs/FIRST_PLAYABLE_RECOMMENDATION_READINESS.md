# First Playable Recommendation Readiness

Task 26 proves that the First Playable Primed Quiver can move from an honest evidence-starved `NO_RECOMMENDATION` state to a legitimate recommendation-ready state when every authoritative prerequisite is supplied through existing workflows.

This document describes the proof chain only. It does not add production prices, production probabilities, automated Trade access, new crafting mechanics, or frontend-side Advisor logic.

## Scope

The proof target is the real First Playable Rare Primed Quiver and the ordinary Orb of Annulment action.

Production-real components used:

- Advisor API and `CraftAdvisorOrchestrator`
- parser, modifier enrichment, affix-state resolution, action applicability, outcome enumeration
- local economy quote workspace and request-scoped economy repository composition
- manual valuation evidence contracts and aggregation path
- empirical probability dataset registry and explicit request selection
- scenario analysis, Expected Value engine, raw Advisor decision engine, and risk policy engine

Test-only evidence used:

- synthetic manual current-item comparable valuations
- synthetic manual outcome comparable valuations for every Annulment outcome
- synthetic local Orb of Annulment quote
- synthetic empirical Annulment outcome-count dataset compatible with the enumerated outcomes
- synthetic bankroll/risk context

The synthetic evidence is regression proof data, not a claim about the real Path of Exile 2 market or real Annulment probabilities.

## Readiness Chain

| Step | Evidence state | Expected result |
| --- | --- | --- |
| Initial real Quiver analysis | No current valuation, no local Annulment quote, no selected empirical probability dataset, no outcome valuations | `NO_RECOMMENDATION`; ordinary Annulment remains applicable but non-rankable; missing requirements include current valuation, economy quote, probability evidence, and outcome valuation evidence. |
| Current valuation supplied | Manual current-item comparable evidence produces a listing-derived current valuation | SELL NOW baseline becomes available, but Annulment remains blocked by missing cost, probability, and/or outcome valuations. |
| Economy quote supplied | A matching local Orb of Annulment quote is saved and the analysis is rerun | Annulment material cost becomes complete; the economy blocker clears only for the matching league/asset request. |
| Probability dataset registered and explicitly selected | Compatible empirical dataset is selected by `empirical_probability_dataset_version` | Annulment probability completeness can become `COMPLETE`; registration alone is inert and does not change Advisor readiness. |
| Every outcome valued | Manual outcome valuation evidence is supplied for every deterministic Annulment outcome ID | Outcome valuation coverage becomes complete; omitting any outcome keeps EV blocked. |
| All prerequisites supplied | Current valuation, complete cost, complete probability model, complete outcome valuations, and risk context are present | Scenario readiness becomes `EV_READY`, Expected Value is available, raw Advisor can select `CRAFT`, and risk policy can preserve that decision when configured to accept it. |

## Authoritative Blockers

Missing requirements are authoritative per action target. A blocker clears only when evidence covers the same target that produced the requirement.

Examples:

- Supplying outcome valuations for five of six Annulment outcomes leaves `OUTCOME_VALUATION_EVIDENCE_REQUIRED` for the remaining outcome.
- Registering an empirical dataset does not clear `PROBABILITY_EVIDENCE_REQUIRED`; the Advisor request must explicitly select a compatible dataset ID.
- Saving a local economy quote does not rerun analysis or fabricate recommendations; the next request composes matching quote evidence into the request-scoped economy repository.
- Non-applicable actions such as Exalted-style additions on the full Quiver do not create actionable evidence blockers and do not enter ranking.

## Recommendation-Ready Meaning

Recommendation-ready means the backend policy gates have enough compatible evidence to rank an EV-ready craft candidate against SELL NOW.

It does not mean:

- the synthetic evidence is real market evidence,
- probability was fabricated,
- the frontend calculated EV,
- scenario median or best-case value was used as EV,
- non-applicable actions were promoted.

The backend remains the authority for EV, Advisor ranking, and risk adjustment. The frontend renders returned values and does not calculate recommendation readiness.

## Proven Synthetic Result

The Task 26 regression path uses:

- current item valuation: `100 Ex`
- Orb of Annulment cost: `7.5 Ex`
- six Annulment outcomes valued at `130 Ex`
- complete compatible empirical probability evidence
- aggressive risk context with `1000 Ex` bankroll

Expected backend result:

- analysis status: `DECISION_READY`
- ordinary Annulment scenario readiness: `EV_READY`
- gross expected outcome value: `130 Ex`
- net expected value: `122.5 Ex`
- expected gain vs sell-now: `22.5 Ex`
- raw Advisor decision: `CRAFT`
- risk-adjusted decision: `CRAFT`

These numbers are intentionally synthetic and exist only to prove the vertical readiness plumbing.

## Remaining Production Work

Before a real user-facing recommendation can be considered economically meaningful, DonnieCraftShell still needs real operator-supplied or source-backed evidence for:

- current item comparable listing valuation
- every relevant outcome valuation
- crafting-material price quote with acceptable freshness and provenance
- compatible empirical or mechanical probability evidence
- risk/bankroll context when risk adjustment is requested

Until those are present, `NO_RECOMMENDATION`, `SCENARIO_ONLY`, or non-rankable action states remain the correct product behavior.
