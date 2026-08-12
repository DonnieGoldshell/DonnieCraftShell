# DonnieCraftShell

DonnieCraftShell is a Path of Exile 2 crafting intelligence platform focused on helping players maximize in-game currency profit through economically optimal crafting decisions.

The long-term product is planned around four modules:

- **Craft Advisor**: analyze an existing item and recommend the economically optimal next crafting action.
- **Profit Finder**: identify crafting strategies with attractive expected profit, ROI, and risk-adjusted returns.
- **Meta & Modifiers**: organize desirable modifiers by item type, skill, class, ascendancy, and build archetype.
- **Economy**: maintain current exchange rates and crafting material prices.

The first MVP focuses only on **rare Quivers**.

## MVP Workflow

The initial milestone will eventually support:

1. Paste PoE2 Quiver clipboard text.
2. Parse item base, item level, and modifiers.
3. Identify modifier tiers.
4. Determine prefixes, suffixes, and open affix slots.
5. Obtain current economy data.
6. Generate legal crafting actions.
7. Estimate outcomes and crafting costs.
8. Calculate expected value.
9. Compare crafting against **SELL NOW**.
10. Recommend **CRAFT** or **SELL**.

Game rules, modifier tables, crafting legality, and external data APIs are not yet verified. Anything relying on PoE2-specific mechanics must be marked `NEEDS VERIFICATION` until backed by a reliable source.

## Repository Layout

```text
apps/web/          Next.js + React + TypeScript frontend
services/api/      Python + FastAPI backend
packages/shared/   Shared schemas, contracts, and domain notes
data/              Verified and provisional data sets
docs/              Product, architecture, data, MVP, and decision-engine docs
infra/             PostgreSQL and deployment infrastructure notes
tests/             Cross-service integration and acceptance tests
```

## Planned Stack

- Frontend: Next.js, React, TypeScript
- Backend: Python, FastAPI
- Database: PostgreSQL

## Current Status

The repository now contains the framework-independent DonnieCraftShell domain engines for the rare Quiver vertical slice plus a FastAPI transport layer for item parsing and Advisor analysis.

Implemented API endpoints:

- `GET /health`
- `GET /api/v1/health`
- `POST /api/v1/items/parse`
- `POST /api/v1/advisor/analyze`

The Advisor API uses local/offline datasets and request-supplied manual valuation evidence only. It does not scrape Trade, poll economy sources, fabricate probabilities, or execute gameplay actions.

## API Development

Install backend dependencies:

```bash
python -m pip install -r services/api/requirements.txt
```

Run the API:

```bash
python -m uvicorn services.api.app.main:app --reload
```

OpenAPI is available at:

```text
http://localhost:8000/openapi.json
http://localhost:8000/docs
```

See `docs/ADVISOR_API.md` and `docs/API_DEVELOPMENT.md` for the Advisor endpoint contract, local configuration, and future TypeScript generation plan.
