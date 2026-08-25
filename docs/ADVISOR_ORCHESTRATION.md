# Advisor Orchestration

Task 13A adds the framework-independent vertical Craft Advisor orchestration layer.

The orchestrator coordinates existing engines. It does not own parser rules, modifier resolution, affix capacity, economy conversion, craft mechanics, outcome enumeration, probability math, valuation aggregation, EV math, Advisor ranking, or risk policy.

## Pipeline

```text
Clipboard
-> parse clipboard item
-> enrich modifiers from selected game-data dataset
-> resolve affix state from selected capacity dataset
-> enumerate craft action candidates from selected crafting dataset
-> price required materials from EconomyRepository
-> enumerate craft outcomes
-> attach probability model
-> attach supplied valuation evidence
-> run scenario analysis
-> calculate EV only when ScenarioAnalysis is EV_READY
-> run raw AdvisorDecisionEngine
-> optionally run RiskPolicyEngine
```

All external data must already be present in local repositories or supplied as input. The orchestrator performs no network calls.

## Request Contract

`AdvisorAnalysisRequest` requires:

- raw clipboard text,
- explicit league,
- selected game-data dataset version,
- selected crafting-action dataset version,
- selected affix-capacity dataset version,
- optional selected empirical probability evidence dataset version,
- optional game context,
- optional current item `ValuationResult`,
- optional mapping of `outcome_id -> ValuationResult`,
- optional `AdvisorRiskContext`,
- optional `as_of` timestamp.

No current league, latest dataset, or mutable global snapshot is selected silently.

## Result Contract

`AdvisorAnalysisResult` preserves component outputs:

- `ParseResult` and `ParsedItem`,
- `ItemEnrichment`,
- `AffixStateResolution`,
- per-action `CraftActionCandidate`,
- per-action `CraftOutcomeSet`,
- per-action `OutcomeProbabilityModel`,
- per-action `ScenarioAnalysis`,
- per-action `ExpectedValueResult`,
- raw `AdvisorDecision`,
- optional `RiskAdjustedAdvisorDecision`.

It also carries analysis UUIDv7, status, warnings, missing requirements, league, dataset versions, economy snapshot IDs, probability model references, valuation evidence IDs, timestamp, and provenance.

## Statuses

- `PARSE_FAILED`: clipboard text could not produce a parsed item.
- `UNSUPPORTED_ITEM`: parser succeeded, but the Craft Advisor MVP does not support the item for full analysis.
- `ANALYSIS_PARTIAL`: parsing, enrichment, actions, or outcomes are available, but valuation/probability/cost inputs block scenario or decision readiness.
- `SCENARIO_READY`: at least one action has descriptive scenario analysis with valuation evidence, but EV/ranking remains unavailable.
- `EV_READY`: at least one action has an available EV result, but no raw Advisor decision selected SELL NOW or CRAFT.
- `DECISION_READY`: raw Advisor decision selected SELL NOW or CRAFT under the current policy.

Status describes pipeline progress, not gameplay advice.

## Missing Requirements

Missing inputs are explicit so the future UI can explain how to improve the analysis:

- `CURRENT_VALUATION_EVIDENCE_REQUIRED`,
- `OUTCOME_VALUATION_EVIDENCE_REQUIRED`,
- `PROBABILITY_EVIDENCE_REQUIRED`,
- `ECONOMY_QUOTE_REQUIRED`,
- `VERIFIED_MECHANIC_REQUIRED`.

Missing data never becomes zero cost, zero probability, or a negative recommendation.

## Evidence Readiness

Task 21 adds an `evidence_readiness` summary beside the raw missing
requirements. This is a player-facing checklist derived from existing
orchestration evidence; it does not fabricate recommendation confidence or make
any non-rankable action rankable.

Readiness is grouped into:

- current-item valuation readiness,
- economy/crafting-cost readiness,
- probability readiness,
- outcome valuation readiness,
- verified mechanic readiness.

Each readiness item has a status (`READY`, `PARTIAL`, `MISSING`, or `UNKNOWN`),
a short summary, optional diagnostics copied from the underlying missing
requirements, and actionable targets such as missing EconomyAsset IDs, actions
or outcomes lacking probability evidence, outcomes lacking valuation coverage,
and mechanics that still need verification. The UI may link these targets to
manual valuation, observation review/import, economy import, or mechanic
research tools, but those tools remain separate workflows and must not be
auto-submitted or trusted as evidence merely because the checklist was opened.

Completing every checklist item is not a guarantee that Advisor will recommend
a craft. The normal gates still apply: probability, valuation, cost, mechanics,
EV readiness, risk policy, and Advisor decision policy remain authoritative.

## Failure Isolation

Action analysis is isolated per candidate. A failure in one action is surfaced as that action's warning and missing requirement; other actions continue through the pipeline.

Unexpected failures are not silently ignored: the action result includes the failure message and remains non-rankable.

## MVP Support

The current vertical pipeline supports Rare Quivers. Normal, Magic, Unique, and non-Quiver parsed items return `UNSUPPORTED_ITEM` with parser output retained and no Craft Advisor recommendation.

## Valuation And Probability

The orchestrator never invents valuation evidence. If current valuation or outcome valuations are missing, the item can still be parsed, enriched, priced, and have outcomes enumerated, but scenario/EV/Advisor readiness reflects the missing input.

The orchestrator uses the injected probability provider. Probability context
includes league, game version when supplied, crafting dataset version, modifier
dataset version, and optional empirical evidence dataset version.

The default provider path is a composite:

1. verified analytical mechanic rules,
2. explicitly selected empirical evidence,
3. current research `UNKNOWN` fallback.

Task 22B configures no production analytical rules because current source
evidence does not verify uniform Annulment selection or Exalted modifier
weights. If a future verified rule is configured, it may clear
`PROBABILITY_EVIDENCE_REQUIRED` for that action only. Empirical providers may
return `EMPIRICAL_ESTIMATE` evidence only when a compatible offline dataset is
explicitly configured/injected and selected. Missing, partial, synthetic-disabled,
or context-incompatible evidence is surfaced as `PROBABILITY_EVIDENCE_REQUIRED`
and does not unlock EV readiness.

Provider outputs are never averaged. If multiple providers can return numeric
evidence, explicit precedence decides the selected model and lower-precedence
numeric disagreement is surfaced as a warning.

Task 17A inserts an empirical dataset registry between curated dataset builds
and Advisor selection. Registering a dataset only loads it into the running
application; the request must still set `empirical_probability_dataset_version`.
If no dataset ID is supplied, registered evidence is ignored and current real
actions keep their UNKNOWN probability models.

## Risk

Risk adjustment is optional. When a request supplies `AdvisorRiskContext`, the orchestrator runs the risk policy engine after the raw Advisor decision. Raw economic decision and risk-adjusted decision remain separate.

Risk policy does not mutate EV.
