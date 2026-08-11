# Domain Model

This document defines the first shared DonnieCraftShell domain contracts. It extends the product rules in [PRODUCT.md](PRODUCT.md), [MVP.md](MVP.md), and [DECISION_ENGINE.md](DECISION_ENGINE.md).

## Scope

The model is item-class agnostic. MVP 0.1 targets rare Quivers, but shared core types must not contain Quiver-specific fields. Quiver behavior should later live behind item-class interfaces.

The initial executable contracts live in `packages/shared/donniecraftshell_contracts/domain.py`.

## Core Types

- `GameContext`: game, league, game version, locale, and snapshot timestamp. No current league or version is hardcoded.
- `DataProvenance`: source identity, source type, URI/reference, retrieval timestamp, game version, league, verification status, confidence, and notes.
- `Confidence`: optional 0..1 decimal score, level, reasons, and sample size.
- `EconomicValue`: decimal-safe normalized value where `1 Exalted Orb = 1 economic unit`.
- `CurrencyAmount`: native asset amount plus optional normalized economic value.
- `ParsedItem`: normalized clipboard-derived item state with raw text, game context, rarity, item class, base type, item level, flexible properties, modifiers, affix state, confidence, and provenance.
- `ItemModifier`: raw and normalized modifier text, optional canonical ID, affix type, group/family, tier, rolls, tags, confidence, and provenance.
- `AffixState`: known prefixes/suffixes, optional capacities and open counts, and uncertainty. Unknown capacity remains `None`.
- `ModifierRelevance`: relevance separated from objective modifier data, with origin as verified, derived/statistical, or curated.
- `EconomyQuote`: league-specific normalized price, native pair/rate, timestamp, volume, confidence, and provenance.
- `Valuation`: estimate, plausible low/high range, confidence, comparable count, comparable strategy, timestamp, and provenance.
- `CraftAction`: generic action candidate. `SELL_NOW` is represented by the same type as all other actions.
- `CraftOutcome`: resulting item or state delta, optional probability, probability confidence, valuation, profit/loss, and provenance.
- `SimulationResult`: action cost, outcomes, probability coverage, EV/ROI/risk fields, confidence, assumptions, warnings, and completeness.
- `AdvisorRecommendation`: current valuation, candidates, selected action when available, comparisons, risk, bankroll exposure, confidence, reasons, warnings, and timestamp. It supports `NO_RECOMMENDATION`.
- `BankrollContext` and `RiskProfile`: user risk preference and bankroll constraints, kept separate from raw EV calculations.
- `CraftSession`: session ID, game context, item states, actions/costs, total invested, current value, unrealized P/L, and timestamps.

## Unknown Data

Unknown values must be represented as `None` or explicit `NEEDS_VERIFICATION` status. Do not infer modifier tiers, probabilities, crafting legality, or source quality from display text alone.

## Boundaries

Domain models represent business concepts and invariants. Keep core domain models framework-independent where practical.

Do not migrate the entire domain model to Pydantic. Pydantic should be used primarily for API request DTOs, API response DTOs, external adapter/input validation, and FastAPI/OpenAPI schema generation.

The Decision Engine, Craft Simulator, Valuation Engine, and related business logic must operate and be tested without FastAPI or Pydantic dependencies. Explicit mapping between Pydantic DTOs and domain models is preferred over coupling the domain directly to the API framework.

Persistence entities may use different tables optimized for storage, history, snapshots, and indexing. Mapping between domain models, API DTOs, and persistence entities should be explicit.

## Identifier Strategy

- Internal application entities use application-generated UUIDv7 strings by default.
- Use UUIDv7 for analysis IDs, craft session IDs, session step IDs, valuation IDs, simulation IDs, advisor recommendation IDs, and economy snapshot IDs.
- UUIDv7 is preferred because it is globally unique, sortable by creation time, suitable for session/history data, and can be created before persistence.
- External source IDs are stored separately from internal IDs.
- Canonical PoE game-data IDs must use stable source-backed identifiers where available rather than generated replacements.
- Display names are never stable identifiers.
