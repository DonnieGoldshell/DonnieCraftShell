# Architecture Specification

## Overview

DonnieCraftShell is a modular web platform with a Next.js frontend, FastAPI backend, PostgreSQL database, and reusable domain engines.

```text
apps/web
  -> services/api
    -> application services
      -> item parser
      -> game-data adapters
      -> modifier resolver
      -> item-class modules
      -> modifier intelligence
      -> valuation engine
      -> crafting simulator
      -> decision engine
      -> economy adapters
    -> PostgreSQL
```

## Frontend

`apps/web/` contains the Next.js, React, and TypeScript application. It should handle paste input, analysis views, recommendation explanations, uncertainty display, and crafting-session history. React components must not contain PoE2 crafting rules or valuation logic.

## Backend

`services/api/` contains the Python FastAPI service. It should expose endpoints for parsing, analysis, economy lookup, recommendation generation, and session tracking. Backend services should orchestrate domain engines rather than embedding item-class-specific logic directly in route handlers.

## Core Domain Engines

- **Decision Engine**: compares actions against **SELL NOW** using EV, ROI, risk, confidence, and bankroll context.
- **Valuation Engine**: estimates current and outcome market values with ranges, confidence, comparables, and timestamps.
- **Economy Engine**: provides league-specific normalized prices and historical snapshots.
- **Modifier Intelligence**: separates verified game data, derived statistical data, and curated relevance.
- **Game Data Enrichment**: maps parsed clipboard observations to canonical source-backed records without mutating parser output.
- **Craft Action Engine**: evaluates source-backed crafting action applicability and required materials without simulating outcomes or calculating costs.
- **Affix Capacity Resolver**: derives open explicit prefix/suffix slots from parsed modifiers and source-backed capacity definitions.
- **Craft Outcome Engine**: enumerates mechanically possible hypothetical item-state deltas without probability, valuation, or recommendations.
- **Probability Evidence Layer**: attaches exact, derived, empirical, or unknown probabilities to outcome states only when provenance supports them. Task 15A adds an offline empirical observation pipeline; current real actions remain `UNKNOWN` unless context-compatible evidence is explicitly supplied.
- **Observation Workspace**: persists raw manual craft observation records and separate review decisions locally before empirical aggregation. Storage is durable operator workspace state, not probability evidence activation.
- **Observation Review Layer**: curates manual recorder exports before empirical import. Human decisions remain separate from raw observation records; only accepted non-duplicate records proceed to Task 15C-compatible imports.
- **Curated Observation Import Layer**: builds raw empirical probability datasets from accepted review exports by delegating to Task 15C validation, deduplication, and context partitioning.
- **Scenario Analysis Layer**: composes action candidates, outcome sets, probabilities, and valuations into descriptive readiness results without EV or ranking.
- **Expected Value Engine**: calculates EV only from `EV_READY` scenarios with complete probability and valuation inputs; it does not rank or recommend.
- **Advisor Decision Engine**: compares SELL NOW with EV-ready craft candidates and may return `NO_RECOMMENDATION`; scenario-only actions remain non-rankable.
- **Risk And Bankroll Policy**: filters raw Advisor decisions by transparent bankroll/exposure gates without modifying EV.
- **Advisor Orchestration**: composes parser, enrichment, affix state, action candidates, costs, outcomes, probabilities, valuations, scenarios, EV, raw Advisor decision, and optional risk adjustment into one partial-result-aware analysis.
- **Craft Investment Ledger**: records operator-entered realized base cost and historical crafting spend, then compares complete cost basis to authoritative market valuation status without fabricating point profit from broad brackets or diagnostic medians.
- **Modifier Pool Resolver**: filters natural explicit modifier candidates by item class, side, item level, capacity, and source-backed modifier-group conflicts.
- **Craft Simulator**: models legal actions and outcomes only when mechanics are verified.

See [DECISION_ENGINE.md](DECISION_ENGINE.md) for economic behavior.
See [ECONOMY.md](ECONOMY.md) and [ECONOMY_SOURCES.md](ECONOMY_SOURCES.md) for provider architecture, source precedence, freshness, and normalized pricing rules.
See [VALUATION.md](VALUATION.md) and [VALUATION_SOURCES.md](VALUATION_SOURCES.md) for comparable rare-item valuation architecture and TradeProvider boundaries.
See [PROBABILITY_MODEL.md](PROBABILITY_MODEL.md) and [EMPIRICAL_PROBABILITY.md](EMPIRICAL_PROBABILITY.md) for probability evidence contracts, empirical observation ingestion, and the no-equal-fallback policy.

Task 15B wires empirical probability providers into Advisor orchestration and
API dependency assembly. Production/default assembly uses only explicitly
configured offline empirical dataset paths and skips synthetic fixtures; tests
may inject synthetic datasets explicitly.

Task 15C adds an offline empirical observation import workflow. Observation
JSON/CSV batches are validated, deduplicated, partitioned by context, and
aggregated into the raw empirical probability dataset shape. This still performs
no scraping and does not make real actions numeric without compatible evidence.

Task 16A adds a manual craft observation recorder before the import workflow.
The recorder captures before/after clipboard text, item fingerprints,
classification method, and Task 15C-compatible raw records. It is evidence
collection only; probability, EV, valuation, and Advisor readiness remain owned
by their existing engines.

Task 16B adds [OBSERVATION_REVIEW.md](OBSERVATION_REVIEW.md). Recorder exports
load as pending review records; accepted/rejected/pending decisions are audited
in a manifest, and only accepted non-duplicate observations are exported in the
original importer-compatible shape. Automatic classification still requires
human acceptance, unclassified observations can remain unclassified, and mixed
synthetic/context batches surface warnings.

Task 16C adds [CURATED_OBSERVATION_IMPORT.md](CURATED_OBSERVATION_IMPORT.md).
Accepted review exports can be submitted to a controlled builder that validates
records through Task 15C, partitions incompatible evidence contexts, and returns
Task 15A-compatible raw empirical probability datasets. Building these datasets
does not silently configure them for Advisor probability use.

Task 17A adds [EMPIRICAL_DATASET_REGISTRY.md](EMPIRICAL_DATASET_REGISTRY.md).
Built empirical datasets may be registered into the local running API and listed
for operator selection. Registration is inert: Advisor probability evaluation
uses a dataset only when `empirical_probability_dataset_version` explicitly
names that registered dataset, and unknown/incompatible selections remain
UNKNOWN rather than falling back to another empirical dataset.

Task 17B keeps that safety model and adds optional local JSON persistence for
registered empirical datasets. API startup reloads valid persisted datasets and
surfaces corrupt-entry warnings while skipping malformed evidence. No persisted
dataset is auto-activated for Advisor analysis.

Task 22B adds verified analytical probability provider support. Production
provider precedence is analytical verified mechanics, explicitly selected
empirical datasets, then current research UNKNOWN fallback. The current
configured analytical rule set is empty because existing mechanics do not verify
uniform Annulment selection or Exalted weights. Providers are never averaged or
merged; lower-precedence numeric conflicts are surfaced as warnings.

Task 22C adds [ANALYTICAL_PROBABILITY_REGISTRY.md](ANALYTICAL_PROBABILITY_REGISTRY.md).
Production analytical rules now load from a versioned local registry fixture.
The committed fixture is intentionally empty; only `VERIFIED` records with
`VERIFIED` provenance can become `AnalyticalProbabilityRule` objects, and
duplicates or malformed records are skipped with warnings.

Task 18A adds [OBSERVATION_WORKSPACE.md](OBSERVATION_WORKSPACE.md). Raw Task
16A recorder records and Task 16B review decisions persist to local JSON before
aggregation. Review metadata remains separate from raw evidence, conflicting
`raw_record_id` content is rejected, version-incompatible workspace files are
skipped without startup rewrites, and only accepted records flow into Task 16C
dataset builds.

Task 18B extends the same workspace boundary with backup/export and
restore/import. Backups use the supported versioned workspace envelope, API
restore never accepts arbitrary filesystem paths, `MERGE` and `REPLACE` modes
validate conservatively before mutation, and persistence failures roll back the
restore rather than leaving memory ahead of durable evidence.

## Item-Class Modularity

Quiver logic belongs behind item-class interfaces. Future bows, rings, amulets, and armour modules should supply their own base definitions, modifier mappings, affix rules, legal action providers, and valuation features without changing the core engines.

## Data And Persistence

PostgreSQL should store item-class definitions, verified modifier metadata, provisional research data, economy snapshots, valuation comparables, analysis runs, craft sessions, and future strategy results.

Important records should include provenance fields such as `source`, `retrieved_at`, `game_version`, `league`, and `confidence`.

## Integration Boundaries

External data sources, trade data, and economy providers must be isolated behind adapters so they can be replaced, disabled, mocked, or compared. Do not implement unsupported automated Path of Exile trade scraping.

Economy providers must ingest in the backend through replaceable adapters. Runtime application logic should consume normalized `EconomySnapshot`, `EconomyQuote`, and `ExchangeRate` records instead of poe.show/poe.ninja-shaped or GGG-shaped payloads.

Task 6B proves this boundary with an offline poe.show Currency fixture and local normalized JSON. No runtime network polling or background scheduling is implemented.

Task 6C adds offline Ritual and Essences fixtures using the same provider boundary, and introduces craft-material cost calculation as a pure economy service, not Craft Advisor logic.

Crafting action definitions follow the same offline snapshot pattern:

- raw research in `data/raw/crafting/`
- normalized versioned action datasets in `data/normalized/crafting/`
- framework-independent applicability checks in `CraftActionEngine`

See [CRAFTING_ACTIONS.md](CRAFTING_ACTIONS.md) and [CRAFTING_SOURCES.md](CRAFTING_SOURCES.md). The Craft Action Engine returns `APPLICABLE`, `NOT_APPLICABLE`, or `UNKNOWN`; it does not estimate outcomes, EV, or prices.

Task 7B adds [AFFIX_CAPACITY.md](AFFIX_CAPACITY.md). Parser output remains immutable; open-slot state is supplied to action evaluation as derived enrichment.

Task 7C adds [CRAFT_ACTION_COSTS.md](CRAFT_ACTION_COSTS.md). Candidate enumeration composes Craft Action Engine output with Economy cost output while keeping mechanics and market data separate.

Task 8A adds [CRAFT_OUTCOMES.md](CRAFT_OUTCOMES.md). Outcome possibility and outcome probability are separate architecture layers; probability/EV belongs to later tasks.

Task 8C updates [QUIVER_MODIFIER_POOL_STATUS.md](QUIVER_MODIFIER_POOL_STATUS.md). Legal modifier-pool filtering now uses the expanded natural Quiver Base Prefix/Suffix dataset, but completeness remains scoped and probability remains separate.

Task 9B adds [PROBABILITY_MODEL.md](PROBABILITY_MODEL.md). Outcome-space completeness must not be converted into equal probability; `ProbabilityProvider` attaches probability evidence beside `CraftOutcomeSet` so later EV logic can require complete probability mass.

Task 10B adds [VALUATION_MODEL.md](VALUATION_MODEL.md) and [MANUAL_TRADE_WORKFLOW.md](MANUAL_TRADE_WORKFLOW.md). Current and hypothetical item states share `ValuationSubject`, and manual comparable evidence flows through `ManualTradeProvider` with no network calls or undocumented Trade access.

Task 10C adds [VALUATION_AGGREGATION.md](VALUATION_AGGREGATION.md). `ValuationAggregator` turns manual normalized comparable evidence into listing-derived valuation results using Decimal median/quantile policy, strict/moderate precedence, explicit readiness, confidence, liquidity, and retained evidence provenance.

Issue 63 extends the manual valuation preview with Comparable Valuation Model v1. The model consumes structured comparable item state, relevance, quality delta, and normalized listing prices to produce inspectable lower/upper/equivalent anchors and a conservative bracket when evidence is sufficient. It does not automate Trade access, alter Advisor/EV readiness, or convert price-only observations into adjusted values.

Issue 65 layers scoped market inference v1 onto that preview model. It scores comparable usefulness from structural relevance, modifier quality similarity, freshness, and observable item-state differences, then emits `INFERRED_MARKET_BAND` only for sufficiently close high-usefulness evidence clusters. Broad lower/upper anchor brackets stay visible as `BROAD_BRACKET_ONLY` and are not promoted into confident market estimates.

Issue 67 adds a headline valuation presentation boundary to the Advisor manual valuation preview. API clients should use `market_valuation` for player-facing estimated market value semantics and treat the raw aggregation median as diagnostics unless structured inference reaches `INFERRED_MARKET_BAND`.

Task 11A adds [SCENARIO_ANALYSIS.md](SCENARIO_ANALYSIS.md) and [DECISION_READINESS.md](DECISION_READINESS.md). Scenario analysis is allowed when EV is not; `EV_READY` is a strict gate for future EV work and does not calculate EV.

Task 11B adds [EXPECTED_VALUE.md](EXPECTED_VALUE.md). EV results retain contribution breakdowns, evidence references, economy snapshots, dataset versions, and algorithm version `dc-ev-v1`, but still produce no Advisor recommendation.

Task 12A adds [ADVISOR_DECISION_ENGINE.md](ADVISOR_DECISION_ENGINE.md). The Advisor candidate layer keeps SELL NOW first-class, reuses `ExpectedValueResult` without recalculating EV, and excludes scenario-only actions from economic ranking.

Task 12B adds [RISK_AND_BANKROLL.md](RISK_AND_BANKROLL.md). Raw economic decisions remain visible; risk-adjusted decisions can veto high-exposure crafts or select the next surviving EV-ready craft.

Task 13A adds [ADVISOR_ORCHESTRATION.md](ADVISOR_ORCHESTRATION.md). `CraftAdvisorOrchestrator` is a coordination layer only: it invokes existing engines in order, preserves component evidence, surfaces missing requirements, isolates per-action failures, and produces a single framework-independent Advisor analysis result for future API/UI use.

Task 13B adds [ADVISOR_API.md](ADVISOR_API.md) and [API_DEVELOPMENT.md](API_DEVELOPMENT.md). FastAPI route handlers use Pydantic DTOs and explicit mappers; they do not reimplement Advisor business logic. OpenAPI is the transport source of truth for future generated TypeScript contracts.

Community game-data sources such as PoE2DB must be imported through source adapters into raw snapshots and normalized records. Runtime analysis should use normalized data or database records, not live scraping.

Task 5B implements this boundary with local JSON fixtures:

- `game_data_import.py` loads raw research snapshots and writes normalized datasets.
- `game_data_repository.py` loads explicit dataset versions.
- `modifier_resolver.py` resolves parsed modifiers into `ItemEnrichment` without mutating `ParsedItem`.

See [GAME_DATA_IMPORT.md](GAME_DATA_IMPORT.md) and [MODIFIER_RESOLUTION.md](MODIFIER_RESOLUTION.md).

## Architecture Adjustments Before Implementation

- Define shared API contracts before building frontend-backend flows.
- Create explicit confidence and provenance types early.
- Version game data imports and economy snapshots.
- Keep raw source data separate from normalized domain data.
- Model craft sessions from MVP 0.1, even if persistence starts minimal.

## Manual Valuation Workspace

The API includes a framework-independent manual valuation evidence workspace used by the Manual Valuation panel. It persists operator-entered listing observations locally, enforces canonical subject identity, and keeps persistence separate from valuation preview, Advisor analysis, and EV readiness. See [MANUAL_VALUATION_WORKSPACE.md](MANUAL_VALUATION_WORKSPACE.md).

## Craft Investment Workspace

Issue 69 adds [CRAFT_INVESTMENT_LEDGER.md](CRAFT_INVESTMENT_LEDGER.md). The
craft investment workspace persists realized operator-entered ledger entries
locally under `.dcs/craft_investment_workspace.json` by default. It is an
accounting input for current profit position only; it does not infer spend,
scrape prices, recommend SELL/CONTINUE/STOP, or alter Advisor EV math.
