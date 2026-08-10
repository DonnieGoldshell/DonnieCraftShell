# Decision Engine

## Purpose

The decision engine compares available crafting actions against selling the item immediately. It should produce transparent economic recommendations rather than opaque scores.

## Core Concepts

- **Parsed item**: normalized representation of pasted clipboard text.
- **Item-class module**: Quiver-specific logic for bases, modifiers, affix limits, and legal actions.
- **Economy snapshot**: current prices for relevant currencies and comparable items.
- **Crafting action**: a legal next step with cost, possible outcomes, and assumptions.
- **Expected value**: weighted outcome value minus expected crafting cost.

## Initial Quiver Flow

```text
clipboard text
-> parser
-> normalized rare quiver
-> modifier/tier classifier
-> affix-slot analyzer
-> legal action generator
-> outcome estimator
-> expected value calculator
-> recommendation
```

## Item-Class Extensibility

The engine should depend on item-class interfaces, not hardcoded Quiver logic. Future modules for bows, rings, amulets, and armour should be added by supplying new item-class definitions and rule providers.

## Verification Requirements

The following are `TODO / NEEDS VERIFICATION`:

- PoE2 clipboard text format details.
- Quiver base types and item-level requirements.
- Modifier tier data.
- Prefix/suffix limits and classification.
- Legal crafting actions for relevant currencies.
- Outcome probabilities and weighting.

## Recommendation Output

Recommendations should include action, reasoning, expected cost, expected value, risk notes, and a clear comparison to **SELL NOW**.
