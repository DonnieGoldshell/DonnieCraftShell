# API Contracts

This document defines the initial contract surface for future DonnieCraftShell APIs. It does not require endpoint implementation yet.

## Contract Strategy

Use an API-schema-first workflow once FastAPI is scaffolded:

1. Backend API-layer Pydantic models define request and response transport schemas.
2. FastAPI generates OpenAPI.
3. OpenAPI is the single source of truth for frontend API contracts.
4. TypeScript client/types are generated from OpenAPI for `apps/web/`.
5. Contract tests verify generated schemas and critical transport invariants.

The temporary dependency-free contracts in `packages/shared/donniecraftshell_contracts/api.py` document the DTO shape until FastAPI/Pydantic is introduced.

OpenAPI is authoritative for transport contracts, not for the internal domain model. The core domain model remains framework-independent and should not depend on FastAPI or Pydantic.

## Initial Endpoints

```text
POST /api/v1/items/parse
POST /api/v1/items/enrich
POST /api/v1/items/analyze
GET  /api/v1/economy/current
GET  /api/v1/economy/assets
GET  /api/v1/economy/history/{asset_id}
GET  /api/v1/crafting/actions
POST /api/v1/crafting/actions/evaluate
POST /api/v1/valuation
POST /api/v1/valuation/comparables
POST /api/v1/crafts/simulate
POST /api/v1/crafts/probabilities
POST /api/v1/crafts/scenarios
POST /api/v1/crafts/expected-value
POST /api/v1/advisor
POST /api/v1/advisor/analyze
POST /api/v1/advisor/manual-valuation/preview
POST /api/v1/advisor/craft-investment/preview
POST /api/v1/advisor/economy-quotes/workspace/quotes
GET  /api/v1/advisor/economy-quotes/workspace/quotes
POST /api/v1/observations/workspace/records
GET  /api/v1/observations/workspace
POST /api/v1/observations/workspace/reviews
GET  /api/v1/observations/workspace/accepted-export
GET  /api/v1/observations/workspace/backup
POST /api/v1/observations/workspace/restore
POST /api/v1/sessions
POST /api/v1/sessions/{id}/steps
```

All endpoints are contract placeholders. They must return explicit `NOT_IMPLEMENTED` responses until real behavior exists.

Task 4 implements the first real behavior for `POST /api/v1/items/parse` only. All other endpoints remain placeholders for later tasks.

Task 5A defines the future contract for `POST /api/v1/items/enrich`: request contains a parsed item and optional game-data snapshot ID; response contains an `ItemEnrichment` or a structured error. Task 5B implements the offline domain/import/resolver pipeline, but the endpoint remains deferred until the backend has explicit Pydantic DTOs and DTO <-> domain mappings for `ParsedItem`, `ModifierResolution`, and `ItemEnrichment`.

The current FastAPI route serializes framework-independent dataclasses through a small temporary `_to_jsonable()` helper. This is accepted technical debt until the backend API layer defines proper Pydantic DTOs and explicit DTO <-> domain mappings.

Economy endpoints should accept explicit `league` and optional `asset_id`, `category`, and timestamp-range query parameters. Responses should include normalized Exalted values, source, snapshot ID, observed/retrieved timestamps, freshness, volume where available, and warnings for missing, stale, or conflicting data. Missing prices must be represented as unavailable/unknown, never zero.

Task 6B implements the framework-independent economy domain, adapter, normalizer, and repository first. `GET /api/v1/economy/current` remains deferred until API-layer Pydantic DTOs can map explicitly to `EconomyQuote` without leaking provider-specific payload fields.

When exposed later, economy DTOs should include category filters for materials and a separate cost-preview contract for known ingredient lists. That cost contract must report incomplete results when any ingredient price is missing.

Crafting-action endpoints should expose versioned action definitions and applicability results from a selected crafting dataset. Responses must distinguish `APPLICABLE`, `NOT_APPLICABLE`, and `UNKNOWN`, include required material EconomyAsset IDs, and avoid outcome simulation fields. See [CRAFTING_ACTIONS.md](CRAFTING_ACTIONS.md).

Future action-candidate DTOs may include material costs, but they must keep `applicability.status` separate from `material_cost.complete`. A candidate response must not include ranking, EV, valuation, or recommendation fields until Advisor contracts are implemented.

Future probability DTOs should expose `OutcomeProbabilityModel` from [PROBABILITY_MODEL.md](PROBABILITY_MODEL.md). Unknown probability must serialize as `null`, not `0`. Responses must preserve probability completeness, total known probability mass, evidence provenance, dataset versions, deterministic operation evidence, and warnings. The endpoint must not normalize partial/unknown probabilities or divide unknown mass equally.

Advisor probability transport may include an explicit `empirical_probability_dataset_version` selector. This selects among registered/configured offline empirical datasets only; it must not trigger network access, synthetic fixture auto-loading, or automatic fallback to another dataset. Action responses expose probability evidence summaries including `EMPIRICAL_ESTIMATE` type, sample size, uncertainty intervals, evidence dataset version, and warnings when available.

Task 17A adds local/operator empirical dataset registry endpoints:

- `POST /api/v1/observations/empirical-datasets/register`
- `GET /api/v1/observations/empirical-datasets`

These endpoints accept/list Task 15A-compatible empirical probability dataset payloads produced by the curated observation build workflow. Registration is not activation; Advisor analysis uses a registered dataset only when the request names its dataset ID.

Task 17B adds local JSON persistence behind the same registry endpoints. Register/list responses include persistence status (`FILE` vs `IN_MEMORY`, enabled flag, loaded count, skipped corrupt entry count, and warnings) without exposing arbitrary filesystem contents.

Task 18A adds local/operator observation workspace endpoints:

- `POST /api/v1/observations/workspace/records`
- `GET /api/v1/observations/workspace`
- `POST /api/v1/observations/workspace/reviews`
- `GET /api/v1/observations/workspace/accepted-export`
- `GET /api/v1/observations/workspace/backup`
- `POST /api/v1/observations/workspace/restore`

These endpoints persist Task 16A raw observation records and Task 16B review decisions locally without accepting or aggregating them by storage alone. `raw_record_id` remains the evidence identity, conflicting content is rejected, persisted review state stays separate from raw evidence, and accepted exports still flow through existing Task 16B/16C validation. Backup/restore endpoints expose the same versioned workspace envelope without arbitrary filesystem paths; restore supports conservative `MERGE` and validated `REPLACE` modes and returns a structured restore summary. See [OBSERVATION_WORKSPACE.md](OBSERVATION_WORKSPACE.md).

Future valuation DTOs should expose the contracts from [VALUATION_MODEL.md](VALUATION_MODEL.md) and [VALUATION_AGGREGATION.md](VALUATION_AGGREGATION.md). Requests should accept a current or hypothetical valuation subject plus comparable strategy and modifier-role inputs. Comparable endpoints should return query definitions, manual workflow instructions, listing observations, normalized comparable evidence where available, readiness, economy conversion snapshots, provenance, and warnings. Aggregation responses must label estimates as `LISTING_DERIVED`, expose used/excluded comparable IDs, preserve policy ID and strategy composition, and allow `INSUFFICIENT_DATA` without fabricating an estimate.

Future scenario DTOs should expose [SCENARIO_ANALYSIS.md](SCENARIO_ANALYSIS.md) and [DECISION_READINESS.md](DECISION_READINESS.md) concepts. Responses must include decision readiness, outcome valuation coverage, probability completeness, EV readiness, descriptive scenario statistics, warnings, and evidence references. They must not include EV, ranking, recommendation, or probability-weighted statistics until future Advisor/EV contracts explicitly allow them.

Future expected-value DTOs should expose [EXPECTED_VALUE.md](EXPECTED_VALUE.md) concepts. Responses must return either `AVAILABLE` with gross expected outcome value, net expected value, expected gain vs sell-now, ROI where valid, contribution breakdowns, EV bounds where complete, evidence references, and algorithm version, or `NOT_AVAILABLE` with structured readiness reasons. They must not include action ranking or recommendations.

Future Advisor DTOs should expose [ADVISOR_DECISION_ENGINE.md](ADVISOR_DECISION_ENGINE.md). Responses must include SELL NOW candidate, craft candidates, rankable/non-rankable status, selected decision type, selected candidate when any, policy/version, decision reasons, evidence references, and warnings. Scenario-only candidates must not serialize as ranked EV candidates.

Advisor request DTOs may later include risk fields from [RISK_AND_BANKROLL.md](RISK_AND_BANKROLL.md): bankroll, risk profile, maximum bankroll exposure, maximum acceptable loss, and minimum reserve. Responses should expose raw Advisor decision and risk-adjusted decision separately, including risk policy version and triggered rules.

Task 13B implements `POST /api/v1/advisor/analyze`. See [ADVISOR_API.md](ADVISOR_API.md). Requests include clipboard text, explicit league, selected dataset versions, optional manual current valuation evidence, optional manual outcome valuation evidence keyed by deterministic outcome ID, and optional risk context. Responses preserve partial results per action, missing requirements, raw Advisor decision, optional risk-adjusted decision, and all relevant evidence references. The endpoint does not fetch external data at request time or fabricate valuations/probabilities.

Task 21 adds an `evidence_readiness` response object to
`POST /api/v1/advisor/analyze`. It groups existing analysis blockers into
current-item valuation, economy/crafting-cost, probability, outcome valuation,
and verified-mechanic readiness. Each item exposes a status, summary,
diagnostic missing requirements, and actionable targets such as missing economy
asset IDs, action IDs without probability evidence, outcome IDs without
valuation coverage, and unverified mechanics. This object is explanatory only:
it must not weaken fail-closed Advisor behavior, imply that checklist
completion guarantees a recommendation, or replace the underlying missing
requirements and per-action diagnostics.

Task 19A implements `POST /api/v1/advisor/manual-valuation/preview` for the
user-facing manual valuation workflow. The request contains an explicit league,
subject identity (`CURRENT_ITEM` or `HYPOTHETICAL_OUTCOME`), optional
`outcome_id`, comparable strategy, and manual listing observations with Decimal
amount strings. The response returns normalized comparable rows where economy
conversion is available, readiness, listing-derived estimate/range when policy
allows it, confidence, liquidity, economy snapshot IDs, and warnings. Missing
conversion remains unavailable, never zero. The endpoint performs no Trade or
economy network calls and does not bypass `ValuationAggregator`.

Task 53 extends manual listing observations with optional
`comparable_clipboard_text`. When present, API preview and workspace save/update
parse that text through the canonical item parser and return/store a
`comparable_item` structured state. Price-only observations remain valid for
backward compatibility, but they are explicitly not structurally verified.
Malformed comparable clipboard text is a validation error. Listing evidence
remains an asking-price observation, not a realized sale.

Task 59 extends manual valuation preview with optional `subject_clipboard_text`
and `comparable_relevance` on preview rows. When the current subject and a
comparable both have parsed structured item state, the backend returns a
versioned structural relevance assessment with band, optional score, base
similarity reasons, matched/differing/missing/extra modifier groups, and
warnings. This is explainability metadata only; the endpoint does not use it to
rank comparables, alter valuation aggregation, infer market premiums, or
fabricate relevance for price-only evidence.

Task 63 adds optional `comparable_valuation_estimate` to the same preview
response. It exposes Comparable Valuation Model v1: structured comparable
anchors, anchor roles (`LOWER_ANCHOR`, `UPPER_ANCHOR`, `EQUIVALENT_ANCHOR`,
`UNINTERPRETED`), a conservative listing-derived bracket when sufficient
anchors exist, confidence, policy ID, included/excluded observation IDs, and
warnings. This preview field does not replace the existing aggregation result,
does not multiply price by relevance or quality, and does not feed Advisor/EV
ranking.

Issue 65 extends `comparable_valuation_estimate` with market inference v1
fields: `inference_status`, optional `inferred_market_central/low/high`,
`usefulness_assessments`, `influential_observation_ids`, and
`methodology_summary`. Clients must display `BROAD_BRACKET_ONLY` separately
from `INFERRED_MARKET_BAND`; a distant lower/upper anchor bracket is not a
high-confidence market estimate. Usefulness diagnostics are evidence
explainability only and must not be interpreted as game-economy premiums.

Issue 67 adds `market_valuation` to manual valuation preview responses. This
is the headline presentation contract. It exposes status
`INSUFFICIENT_MARKET_EVIDENCE`, `SUPPORTED_RANGE_ONLY`, or
`ESTIMATED_MARKET_VALUE`, optional inferred/structured market values, optional
player-readable display strings, inference confidence, and
`legacy_statistical_median` for diagnostics. Clients must use
`market_valuation.estimated_value` for headline estimated market value and must
not fall back to preview `estimated_value` when `market_valuation.status` is
not `ESTIMATED_MARKET_VALUE`.

Issue 69 adds craft investment transport contracts. Ledger preview accepts
operator-entered realized cost entries plus the current `market_valuation`
object and returns cost basis and current profit-position status. Point
unrealized profit is serialized only for `ESTIMATED_MARKET_VALUE`; range-only
valuation serializes supported profit low/high only; insufficient market
evidence returns no fabricated profit. Local workspace endpoints persist ledger
entries under `.dcs/` and do not submit, infer, or recommend actions by
themselves.

Task 15B extends the same endpoint with optional empirical probability dataset selection and serialized probability evidence details. Default production assembly skips synthetic empirical fixtures and keeps real actions `UNKNOWN` without compatible evidence.

Task 15C adds an offline operator workflow rather than a public HTTP endpoint:
`scripts/import_empirical_observations.py` reads JSON/CSV observation batches and
writes Task 15A-compatible raw empirical probability datasets. Future API
collection endpoints must preserve the same raw record identity, provenance,
context partitioning, unclassified handling, and no-fabrication policy.
Aggregated dataset IDs must include both context and accepted observation
content so independent batches cannot collide under the same context.

Task 16A implements `POST /api/v1/observations/record` and
`POST /api/v1/observations/export` for the manual empirical craft observation
recorder. See [CRAFT_OBSERVATION_RECORDER.md](CRAFT_OBSERVATION_RECORDER.md).
The endpoints map before/after clipboard observations into stable raw record
IDs and Task 15C-compatible export records. They do not persist a database
session, calculate probabilities, or alter Advisor readiness. Automatic
classification must use backend-derived outcome enumeration; request-supplied
candidate data is not trusted as evidence for `AUTOMATIC` results. Exported
source outcome-set and dataset-version provenance must be backend-derived or
strictly validated against configured backend datasets.

Task 16B implements `POST /api/v1/observations/review` for the review and
curation gate documented in [OBSERVATION_REVIEW.md](OBSERVATION_REVIEW.md).
The endpoint loads one or more recorder export batches, returns every record as
`PENDING` unless an explicit review decision is supplied, and emits both an
accepted-only Task 15C-compatible export and a separate review manifest. Review
metadata is not injected into accepted observation records, rejected/pending
records are not exported for empirical counts, duplicates are surfaced and not
exported twice, and mixed synthetic/non-synthetic or context-mismatched batches
produce warnings instead of silent probability evidence.

Task 16C implements `POST /api/v1/observations/build-empirical-datasets`.
See [CURATED_OBSERVATION_IMPORT.md](CURATED_OBSERVATION_IMPORT.md). The
endpoint accepts a Task 16B accepted export, validates each record through the
existing Task 15C empirical observation contract, aggregates through the Task
15C context-partitioning path, and returns raw Task 15A-compatible empirical
probability dataset payloads plus build counts and warnings. It does not write
production datasets, activate probability evidence, or alter Advisor/EV
readiness by itself.

See [API_DEVELOPMENT.md](API_DEVELOPMENT.md) for FastAPI/Pydantic version assumptions, local startup, configuration, and future OpenAPI-to-TypeScript generation.

Task 14A adds the first frontend consumer for `POST /api/v1/advisor/analyze`. The web app uses generated OpenAPI TypeScript types under `apps/web/src/api/` and must not manually duplicate response DTOs or reimplement Advisor logic. The UI treats partial analysis, unsupported items, and `NO_RECOMMENDATION` as successful transport states rather than HTTP failures.

## Error Model

Common API errors use:

- `code`
- `message`
- `recoverable`
- `reliable_no_result`
- optional `details`

Required error codes include validation error, unsupported item, parse failure, insufficient verified data, external data unavailable, simulation unavailable, valuation unavailable, and not implemented.

Crafting-action evaluation should use `insufficient verified data` when applicability is intentionally `UNKNOWN` because a required rule, such as open affix capacity, is not verified.

`reliable_no_result=true` means the system correctly cannot produce a trustworthy result. This is distinct from a system failure.

## DTO Boundaries

API DTOs should not be database rows. Persistence can split or denormalize data for history, snapshots, and indexing. Domain models should not know table names, migration details, or storage-specific keys.

Explicit mappings between Pydantic DTOs and domain models are preferred. Do not manually maintain duplicated API interfaces in Python and TypeScript; generate TypeScript types from OpenAPI instead.

## Identifier Strategy

Use application-generated UUIDv7 strings for internal transport identifiers such as analysis IDs, craft session IDs, session step IDs, valuation IDs, simulation IDs, advisor recommendation IDs, and economy snapshot IDs.

Do not use display names as identifiers. Keep external source IDs and canonical game-data IDs in separate fields. Canonical PoE game-data identifiers should use stable source-backed IDs where available.

## SELL NOW

`SELL_NOW` is a normal `CraftAction` category and must flow through candidate actions, simulations, and recommendations without special-case architecture.

## Manual Valuation Workspace

Task 19B adds local persistence endpoints for manual valuation evidence under `/api/v1/advisor/manual-valuation/workspace/*`. Records are stored by canonical subject identity (`current` or `outcome:{outcome_id}`), and persisted evidence is not automatically submitted to Advisor or converted into valuation readiness. See [MANUAL_VALUATION_WORKSPACE.md](MANUAL_VALUATION_WORKSPACE.md) for the storage envelope, save/update/delete behavior, and frontend workflow.

## Local Economy Quote Workspace

Task 22A adds local persistence endpoints for operator-supplied economy quote evidence under `/api/v1/advisor/economy-quotes/workspace/*`. Records are stored by exact league, economy asset ID, and Exalted-unit quote currency. Advisor analysis composes matching local quotes into a request-scoped economy repository only when analysis is run; saving a quote alone does not fabricate probability evidence, valuation evidence, or a recommendation. See [LOCAL_ECONOMY_QUOTES.md](LOCAL_ECONOMY_QUOTES.md).

## Comparable Quality Delta Preview

Manual valuation preview responses may include `comparable_quality_delta` next
to `comparable_relevance` when both the current subject clipboard text and a
structured comparable Advanced Copy text are supplied. The delta DTO exposes
directional modifier comparisons, aggregate counts, reasons, origin
differences, and the versioned policy ID. It is transport evidence only: API
clients must not treat it as a market-value multiplier, valuation weight,
Advisor ranking input, or completed-sale signal. Price-only observations return
no fabricated quality delta.
