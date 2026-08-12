# Craft Action Costs

Task 7C connects crafting action applicability to the Economy cost layer without introducing recommendations.

## Core Distinction

Applicability answers:

```text
Can this action be performed on this item?
```

Cost completeness answers:

```text
Do we know the current market cost of the required materials?
```

These are independent. An action may be `APPLICABLE` while cost is incomplete because a required Omen or Essence quote is missing. Missing price is never zero.

## Flow

```text
CraftActionDefinition.required_materials
-> CraftActionCostService
-> EconomyRepository
-> CraftMaterialCost
```

`CraftActionDefinition` stores only EconomyAsset IDs and quantities. It never stores prices.

## Candidate Model

`CraftActionCandidate` is a derived helper:

- action definition
- applicability
- required materials
- material cost
- cost completeness
- cost freshness
- warnings

It is not a recommendation and does not include ranking, EV, valuation, or selected action.

## Mixed Snapshots

Actions can require materials from multiple economy categories. For example:

```text
Exalted Orb from Currency snapshot
+ Omen of Catalysing Exaltation from Ritual snapshot
```

The resulting `CraftMaterialCost` preserves each line's quote/snapshot and exposes oldest/newest source timestamps plus least-fresh freshness. Separate API captures must not be treated as simultaneous observations.

## Current Offline Coverage

The current captured economy fixtures include prices for:

- Exalted Orb
- Greater Exalted Orb
- Perfect Exalted Orb
- Omen of Catalysing Exaltation
- Essence category examples from Task 6C, but not Essence of Hysteria

They do not currently include prices for Orb of Annulment, Greater/Sinistral/Dextral Exaltation Omens, or Greater/Sinistral/Dextral Annulment Omens. These actions can still be applicable, but their cost is incomplete.
