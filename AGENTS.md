# Repository Guidelines

## Project Structure & Module Organization

This repository is currently a clean workspace with no source tree committed yet. Keep the root focused on project metadata and documentation. As the project grows, use predictable top-level directories:

- `src/` for application or library code.
- `tests/` for automated tests that mirror `src/` structure.
- `assets/` for static images, icons, sample data, or other non-code resources.
- `docs/` for longer design notes, runbooks, and contributor-facing references.

Avoid placing generated build output or local environment files in version control.

## Build, Test, and Development Commands

No build system is defined yet. When one is added, document the canonical commands here and keep them runnable from the repository root. Prefer standard names such as:

- `npm run dev` for a local development server.
- `npm run build` for production builds.
- `npm test` for the full test suite.
- `npm run lint` or `npm run format` for code quality checks.

If the project uses another toolchain, replace these examples with the actual commands.

## Coding Style & Naming Conventions

Follow the conventions of the chosen language and framework once introduced. Keep indentation consistent within each file, prefer descriptive names, and avoid abbreviations that obscure intent. Use `camelCase` for JavaScript/TypeScript variables and functions, `PascalCase` for components or classes, and `kebab-case` for file names unless the framework expects another pattern.

Add formatting and linting configuration before the codebase becomes large, and treat formatter output as authoritative.

## Testing Guidelines

Place tests under `tests/` or next to implementation files using the ecosystem’s standard pattern, such as `*.test.ts`, `*.spec.ts`, or `test_*.py`. New behavior should include focused tests for expected paths and important edge cases. Keep fixtures small and commit only deterministic test data.

## Commit & Pull Request Guidelines

This folder is not currently a Git repository, so no historical commit convention is available. Use clear, imperative commit messages such as `Add login form validation` or `Document setup workflow`.

Pull requests should include a short summary, testing notes, and screenshots or recordings for user-facing UI changes. Link related issues when available and call out configuration, migration, or deployment steps explicitly.

## Agent-Specific Instructions

Before editing, inspect the repository for existing conventions and preserve user changes. Keep changes scoped, avoid unrelated refactors, and update this guide whenever project structure or commands change.
