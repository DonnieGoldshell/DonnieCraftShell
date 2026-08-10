# Architecture

## Overview

DonnieCraftShell should be a modular web application with a TypeScript frontend, Python API, PostgreSQL database, and a reusable crafting decision engine.

```text
apps/web
  -> services/api
    -> domain services
      -> decision engine
      -> item-class modules
      -> economy adapters
    -> PostgreSQL
```

## Frontend

`apps/web/` will contain the Next.js application. It should handle item paste input, analysis views, recommendations, and user-facing explanations. Keep PoE2 crafting calculations out of React components.

## Backend

`services/api/` will contain the FastAPI service. It should expose endpoints for parsing, item analysis, economy lookup, and recommendation generation.

## Decision Engine

The decision engine should be item-class agnostic. Quiver-specific behavior belongs in a Quiver module implementing shared interfaces for base types, modifiers, affix rules, and legal actions.

## Database

PostgreSQL should store verified modifier metadata, item-class definitions, economy snapshots, analysis runs, and future strategy results.

## Architecture Adjustments Recommended

- Add a shared contract layer for API request/response schemas before frontend-backend integration.
- Treat economy providers as adapters so pricing sources can be replaced or compared.
- Keep verified game data separate from provisional research data.
- Version data imports and economy snapshots for reproducibility.
- Design all item-class logic behind interfaces from the start, even while only Quivers are implemented.
