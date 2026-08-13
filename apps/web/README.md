# Web App

Next.js + React + TypeScript frontend for DonnieCraftShell.

The Task 14A vertical slice provides the first Craft Advisor workbench:

- Paste PoE2 Advanced Copy text for a Quiver.
- Provide explicit league and dataset context.
- Call `POST /api/v1/advisor/analyze`.
- Render parsed item summary, affix state, action candidates, costs, scenario/EV availability, Advisor decision, warnings, and missing requirements.

The frontend does not implement crafting, valuation, probability, economy, or recommendation logic. It displays the FastAPI response and keeps partial analysis, `NO_RECOMMENDATION`, and missing requirements as valid states.

## Development

Install dependencies from this directory:

```bash
npm install
```

Generate OpenAPI-derived TypeScript types from the local FastAPI app:

```bash
npm run generate:openapi
```

Run checks:

```bash
npm run typecheck
npm test
npm run build
```

Run the development server:

```bash
npm run dev
```

By default the browser app calls:

```text
http://localhost:8000/api/v1/advisor/analyze
```

Override with:

```bash
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

## API Contract

`src/api/openapi.json` and `src/api/openapi.d.ts` are generated from FastAPI OpenAPI using `openapi-typescript`. Do not hand-write duplicate frontend API contracts.
