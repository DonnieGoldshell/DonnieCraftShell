# Repository Guidelines

## Project Structure & Module Organization

This repository is the foundation for DonnieCraftShell, a Path of Exile 2 crafting intelligence web application. Keep the root focused on project metadata and documentation. Use these top-level directories:

- `apps/web/` for the Next.js, React, and TypeScript frontend.
- `services/api/` for the Python FastAPI backend.
- `packages/shared/` for shared contracts and domain schemas.
- `data/` for verified and provisional data sets.
- `infra/` for PostgreSQL and deployment infrastructure notes.
- `docs/` for product, architecture, data source, MVP, and decision-engine docs.
- `tests/` for cross-service integration and acceptance tests.

Avoid placing generated build output or local environment files in version control.

## Build, Test, and Development Commands

No build system is defined yet. When one is added, document the canonical commands here and keep them runnable from the repository root. Prefer standard names such as:

- `npm run dev` for a local development server.
- `npm run build` for production builds.
- `npm test` for the full test suite.
- `npm run lint` or `npm run format` for code quality checks.

For backend work, add Python commands such as `pytest`, `ruff check`, and `uvicorn app.main:app --reload` once FastAPI is scaffolded.

## Coding Style & Naming Conventions

Follow the conventions of each stack. Use `camelCase` for TypeScript variables and functions, `PascalCase` for React components, `kebab-case` for frontend file names, and `snake_case` for Python modules, functions, and variables.

Add formatting and linting configuration before the codebase becomes large, and treat formatter output as authoritative.

## Testing Guidelines

Place frontend tests beside implementation as `*.test.ts` or `*.spec.ts`. Place backend tests as `test_*.py`. Use `tests/` for cross-service flows such as parsing a rare Quiver and producing a recommendation. Keep fixtures small and mark unverified PoE2 assumptions clearly.

## Commit & Pull Request Guidelines

Use clear, imperative commit messages such as `Add quiver parser contract` or `Document MVP workflow`.

Pull requests should include a short summary, testing notes, and screenshots or recordings for user-facing UI changes. Link related issues when available and call out configuration, migration, or deployment steps explicitly.

## Agent-Specific Instructions

Before editing, inspect the repository for existing conventions and preserve user changes. Do not invent PoE2 crafting rules, modifier data, probabilities, API capabilities, or trade integrations. Mark unverified game logic and data sources as `NEEDS VERIFICATION`.

Product principles are non-negotiable: optimize economic decisions, treat **SELL NOW** as a first-class competing action, separate market value from craft quality, expose uncertainty and confidence, keep engines item-class agnostic, isolate external integrations behind adapters, and store provenance for important data. Do not implement application functionality when the user asks only for product specification or documentation.
