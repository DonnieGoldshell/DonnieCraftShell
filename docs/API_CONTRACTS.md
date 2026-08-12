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

Future valuation DTOs should expose the contracts from [VALUATION_MODEL.md](VALUATION_MODEL.md) and [VALUATION_AGGREGATION.md](VALUATION_AGGREGATION.md). Requests should accept a current or hypothetical valuation subject plus comparable strategy and modifier-role inputs. Comparable endpoints should return query definitions, manual workflow instructions, listing observations, normalized comparable evidence where available, readiness, economy conversion snapshots, provenance, and warnings. Aggregation responses must label estimates as `LISTING_DERIVED`, expose used/excluded comparable IDs, preserve policy ID and strategy composition, and allow `INSUFFICIENT_DATA` without fabricating an estimate.

Future scenario DTOs should expose [SCENARIO_ANALYSIS.md](SCENARIO_ANALYSIS.md) and [DECISION_READINESS.md](DECISION_READINESS.md) concepts. Responses must include decision readiness, outcome valuation coverage, probability completeness, EV readiness, descriptive scenario statistics, warnings, and evidence references. They must not include EV, ranking, recommendation, or probability-weighted statistics until future Advisor/EV contracts explicitly allow them.

Future expected-value DTOs should expose [EXPECTED_VALUE.md](EXPECTED_VALUE.md) concepts. Responses must return either `AVAILABLE` with gross expected outcome value, net expected value, expected gain vs sell-now, ROI where valid, contribution breakdowns, EV bounds where complete, evidence references, and algorithm version, or `NOT_AVAILABLE` with structured readiness reasons. They must not include action ranking or recommendations.

Future Advisor DTOs should expose [ADVISOR_DECISION_ENGINE.md](ADVISOR_DECISION_ENGINE.md). Responses must include SELL NOW candidate, craft candidates, rankable/non-rankable status, selected decision type, selected candidate when any, policy/version, decision reasons, evidence references, and warnings. Scenario-only candidates must not serialize as ranked EV candidates.

Advisor request DTOs may later include risk fields from [RISK_AND_BANKROLL.md](RISK_AND_BANKROLL.md): bankroll, risk profile, maximum bankroll exposure, maximum acceptable loss, and minimum reserve. Responses should expose raw Advisor decision and risk-adjusted decision separately, including risk policy version and triggered rules.

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
