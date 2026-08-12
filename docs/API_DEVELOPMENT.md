# API Development

The FastAPI API lives under `services/api/app/`.

## Runtime

Task 13B targets:

- FastAPI `>=0.115`
- Pydantic `>=2.8`
- Uvicorn `>=0.30`
- `httpx2` for current FastAPI/Starlette TestClient support

Core domain packages under `packages/shared/` remain framework-independent and must not import FastAPI or Pydantic.

## Local Startup

Install backend dependencies:

```bash
python -m pip install -r services/api/requirements.txt
```

Run locally:

```bash
python -m uvicorn services.api.app.main:app --reload
```

Health:

```text
GET /health
GET /api/v1/health
```

OpenAPI:

```text
GET /openapi.json
GET /docs
```

## Structure

```text
services/api/app/
  main.py
  config.py
  dependencies/
  mappers/
  routes/
  schemas/
```

Routes should be thin. They validate transport input, call dependencies, invoke domain services, and map domain output to DTOs.

## Configuration

Configured defaults are explicit and returned in responses:

- game-data dataset ID/path,
- crafting-action dataset ID/path,
- affix-capacity dataset ID/path,
- economy snapshot paths,
- supported leagues,
- environment.

Do not silently use mutable `latest` datasets. No secrets or GGG credentials are required for Task 13B.

## TypeScript Generation Plan

Do not hand-write duplicate frontend contracts. Once the frontend is ready, generate TypeScript types/client from OpenAPI with a tool such as:

```bash
npx openapi-typescript http://localhost:8000/openapi.json -o apps/web/src/api/openapi.d.ts
```

The exact command may change with the selected frontend client stack.
