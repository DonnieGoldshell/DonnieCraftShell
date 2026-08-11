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
- **Craft Simulator**: models legal actions and outcomes only when mechanics are verified.

See [DECISION_ENGINE.md](DECISION_ENGINE.md) for economic behavior.

## Item-Class Modularity

Quiver logic belongs behind item-class interfaces. Future bows, rings, amulets, and armour modules should supply their own base definitions, modifier mappings, affix rules, legal action providers, and valuation features without changing the core engines.

## Data And Persistence

PostgreSQL should store item-class definitions, verified modifier metadata, provisional research data, economy snapshots, valuation comparables, analysis runs, craft sessions, and future strategy results.

Important records should include provenance fields such as `source`, `retrieved_at`, `game_version`, `league`, and `confidence`.

## Integration Boundaries

External data sources, trade data, and economy providers must be isolated behind adapters so they can be replaced, disabled, mocked, or compared. Do not implement unsupported automated Path of Exile trade scraping.

Community game-data sources such as PoE2DB must be imported through source adapters into raw snapshots and normalized records. Runtime analysis should use normalized data or database records, not live scraping.

## Architecture Adjustments Before Implementation

- Define shared API contracts before building frontend-backend flows.
- Create explicit confidence and provenance types early.
- Version game data imports and economy snapshots.
- Keep raw source data separate from normalized domain data.
- Model craft sessions from MVP 0.1, even if persistence starts minimal.
