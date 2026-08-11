# API Contracts

This document defines the initial contract surface for future DonnieCraftShell APIs. It does not require endpoint implementation yet.

## Contract Strategy

Use an API-schema-first workflow once FastAPI is scaffolded:

1. Backend Pydantic models define request and response schemas.
2. FastAPI generates OpenAPI.
3. TypeScript types are generated from OpenAPI for `apps/web/`.
4. Contract tests verify generated schemas and critical invariants.

The temporary dependency-free contracts in `packages/shared/donniecraftshell_contracts/api.py` document the DTO shape until FastAPI/Pydantic is introduced.

## Initial Endpoints

```text
POST /api/v1/items/parse
POST /api/v1/items/analyze
GET  /api/v1/economy/current
POST /api/v1/valuation
POST /api/v1/crafts/simulate
POST /api/v1/advisor
POST /api/v1/sessions
POST /api/v1/sessions/{id}/steps
```

All endpoints are contract placeholders. They must return explicit `NOT_IMPLEMENTED` responses until real behavior exists.

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

## SELL NOW

`SELL_NOW` is a normal `CraftAction` category and must flow through candidate actions, simulations, and recommendations without special-case architecture.
