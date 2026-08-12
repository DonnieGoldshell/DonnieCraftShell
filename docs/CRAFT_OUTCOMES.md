# Craft Outcomes

Task 8A models outcome space for existing Quiver crafting actions. It does not model probability, valuation, EV, ranking, or recommendations.

## Core Distinction

Outcome possibility answers:

```text
What mechanically different item states could result?
```

Outcome probability answers:

```text
How likely is each resulting state?
```

Task 8A only models outcome possibility. Probability remains `UNKNOWN` unless source-backed probability data exists. Never assign equal probabilities simply because multiple outcomes exist.

## Contracts

Executable contracts live in `packages/shared/donniecraftshell_contracts/craft_outcomes.py`.

- `CraftOutcomeDefinition`: action-level mechanics, operation type, selection rule, count added/removed, guaranteed family, provenance, and warnings.
- `ItemStateDelta`: hypothetical add/remove/guarantee component.
- `HypotheticalItemState`: deterministic outcome identity plus deltas.
- `CraftOutcomeSet`: action identity, source item identity, outcome states, outcome-space completeness, probability completeness, warnings, provenance, and dataset versions.

## Modeled Actions

- Annulment actions enumerate explicit modifier-removal states.
- Sinistral/Dextral Annulment restrict removal states to prefix/suffix modifiers.
- Greater Annulment is `PARTIAL`; it records two-modifier removal semantics but pairwise state enumeration is deferred.
- Exalted-style actions enumerate source-backed candidate modifier additions from the current natural Quiver Base modifier pool when applicable.
- Sinistral/Dextral Exaltation restrict candidate additions to prefix/suffix pools.
- Greater Exaltation records two-modifier addition semantics, but candidate pair enumeration is deferred.
- Essence of Hysteria represents random removal and guaranteed Quiver modifier as separate deltas.

## Completeness

Annulment on a parsed item can be `COMPLETE` for outcome space when the eligible explicit modifier set is known. Probability remains `UNKNOWN`.

Exalted-style additions may be `COMPLETE` for outcome space when action semantics are modeled, the relevant open side is known, existing modifier groups are source-backed, and the natural Quiver Base pool is complete for the selected dataset snapshot.

Task 8C expands the natural Quiver Base pool to `100` source-backed tiers for the selected PoE2DB snapshot. See [QUIVER_MODIFIER_POOL_STATUS.md](QUIVER_MODIFIER_POOL_STATUS.md) for scoped completeness, counts, and exclusions.

Probability completeness remains `UNKNOWN` for Exalted-style additions because modifier weights/probabilities are not captured and equal weighting is never inferred.

Essence of Hysteria is `PARTIAL` because the guaranteed family is represented, but atomic replacement/addition behavior and full pool interactions still need stronger source backing.

## Deterministic Outcome IDs

Outcome IDs are derived from:

- source item analysis ID
- action ID
- item-state delta payload

They do not depend on ranking or valuation and are intended to remain stable for later valuation/probability/EV layers.
