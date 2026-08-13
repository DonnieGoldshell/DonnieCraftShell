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
- CORS allowed origins,
- environment.

Do not silently use mutable `latest` datasets. No secrets or GGG credentials are required for Task 13B.

## CORS

The API uses a narrow configurable CORS allow-list so the local Next.js frontend can call FastAPI from the browser. The default local/offline policy allows:

```text
http://localhost:3000
http://127.0.0.1:3000
```

Override it with a comma-separated environment variable:

```bash
DCS_CORS_ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
```

Do not use unrestricted `*` origins as a production default. Add deployed frontend origins explicitly when the app is hosted.

## TypeScript Generation Plan

Do not hand-write duplicate frontend contracts. Task 14A generates TypeScript API types from the local FastAPI OpenAPI schema:

```bash
cd apps/web
npm run generate:openapi
```

The command exports `src/api/openapi.json` from the local FastAPI app and then writes `src/api/openapi.d.ts` using `openapi-typescript`. The generated TypeScript types are the frontend transport contract; domain rules remain in the backend/domain packages.

The generated files may be refreshed without network access after backend dependencies and frontend npm dependencies are installed.
