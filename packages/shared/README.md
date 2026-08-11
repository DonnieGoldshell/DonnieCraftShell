# Shared Contracts

Shared schemas, API contracts, and domain notes belong here.

The current Python contracts in `donniecraftshell_contracts/` are dependency-free domain and DTO definitions used to establish invariants before the backend is scaffolded.

Long-term contract synchronization should be API-schema-first:

1. FastAPI owns runtime API schemas through Pydantic models.
2. FastAPI publishes OpenAPI JSON.
3. TypeScript types are generated from OpenAPI for `apps/web/`.
4. Frontend and backend do not manually maintain duplicate schemas.

See `docs/DOMAIN_MODEL.md` and `docs/API_CONTRACTS.md`.
