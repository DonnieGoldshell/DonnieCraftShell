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
POST /api/v1/valuation
POST /api/v1/crafts/simulate
POST /api/v1/advisor
POST /api/v1/sessions
POST /api/v1/sessions/{id}/steps
```

All endpoints are contract placeholders. They must return explicit `NOT_IMPLEMENTED` responses until real behavior exists.

Task 4 implements the first real behavior for `POST /api/v1/items/parse` only. All other endpoints remain placeholders for later tasks.

Task 5A defines the future contract for `POST /api/v1/items/enrich`: request contains a parsed item and optional game-data snapshot ID; response contains an `ItemEnrichment` or a structured error. The endpoint is not implemented yet.

The current FastAPI route serializes framework-independent dataclasses through a small temporary `_to_jsonable()` helper. This is accepted technical debt until the backend API layer defines proper Pydantic DTOs and explicit DTO <-> domain mappings.

## Error Model

Common API errors use:

- `code`
- `message`
- `recoverable`
- `reliable_no_result`
- optional `details`

Required error codes include validation error, unsupported item, parse failure, insufficient verified data, external data unavailable, simulation unavailable, valuation unavailable, and not implemented.

`reliable_no_result=true` means the system correctly cannot produce a trustworthy result. This is distinct from a system failure.

## DTO Boundaries

API DTOs should not be database rows. Persistence can split or denormalize data for history, snapshots, and indexing. Domain models should not know table names, migration details, or storage-specific keys.

Explicit mappings between Pydantic DTOs and domain models are preferred. Do not manually maintain duplicated API interfaces in Python and TypeScript; generate TypeScript types from OpenAPI instead.

## Identifier Strategy

Use application-generated UUIDv7 strings for internal transport identifiers such as analysis IDs, craft session IDs, session step IDs, valuation IDs, simulation IDs, advisor recommendation IDs, and economy snapshot IDs.

Do not use display names as identifiers. Keep external source IDs and canonical game-data IDs in separate fields. Canonical PoE game-data identifiers should use stable source-backed IDs where available.

## SELL NOW

`SELL_NOW` is a normal `CraftAction` category and must flow through candidate actions, simulations, and recommendations without special-case architecture.
