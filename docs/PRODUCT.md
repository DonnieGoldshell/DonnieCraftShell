# Product Specification

## Primary Goal

DonnieCraftShell is a Path of Exile 2 crafting intelligence platform. Its primary goal is to help players maximize in-game currency profit by making economically optimal crafting decisions.

The product must prioritize economic decision support over generic crafting advice. An item that can theoretically improve is not automatically worth crafting.

## Non-Negotiable Principles

1. Economic decisions over generic crafting advice.
2. **SELL NOW** is always a first-class competing action.
3. Never fabricate game mechanics, currency behavior, modifier data, probabilities, APIs, or trade capabilities.
4. Never hide uncertainty.
5. Separate market value from craft quality.
6. Separate raw game data from derived intelligence.
7. Keep core engines item-class agnostic.
8. External integrations must be replaceable adapters.
9. Store provenance for important data.
10. Build the Quiver MVP vertically before expanding horizontally.

Scenario analysis may be shown before Expected Value is available, but descriptive scenario statistics must never be presented as EV, probability-weighted expectation, or a recommendation.

## Major Modules

### Craft Advisor

Answers: "I have this item. What is the economically best thing to do next?"

The Advisor analyzes a pasted item, estimates current value, compares legal next actions against **SELL NOW**, and recommends the economically optimal next step with an explanation. The user performs any craft in game, pastes the result again, and the system recalculates until selling is preferable.

Example action categories may include Orb of Annulment, Exalted Orb variants, Omen plus currency combinations, Essence-based actions, and other valid PoE2 crafting actions added later. Exact behavior is `NEEDS VERIFICATION`.

### Profit Finder

Answers: "I have X currency. What should I craft to maximize expected profit?"

Future inputs include bankroll, risk tolerance, league, and optional preferred item classes. Profit Finder is not part of MVP 0.1, but it must reuse the same Economy, crafting simulation, valuation, modifier intelligence, expected-value, and risk engines as Craft Advisor.

### Meta & Modifiers

Provides exploration of relationships such as class -> ascendancy -> build archetype or skill -> item class -> relevant modifiers. Relevance must distinguish verified game data, derived statistical data, and curated or opinion-based guidance. Curated relevance must never be presented as objective game data.

### Economy

Shared infrastructure for league-specific currency and crafting material values. All internal calculations use normalized economic units where `1 Exalted Orb = 1 economic unit` for the initial design. UI may display Exalted, Divine, or both using current exchange rates.

See [DATA_SOURCES.md](DATA_SOURCES.md) for provenance and verification requirements.

## Current MVP

MVP 0.1 is the rare Quiver Craft Advisor. It is a vertical proof of concept for parsing, modifier intelligence, economy, valuation, legal action generation, simulation, expected value, risk, and recommendation.

See [MVP.md](MVP.md) for scope and acceptance criteria.
