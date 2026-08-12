# Crafting Actions

Task 7A defines the first Craft Action Engine contract for Quiver MVP legality checks. It covers applicability and required materials only. It does not simulate outcomes, assign probabilities, calculate cost, value items, or make recommendations.

## Flow

```text
ParsedItem
+ optional ItemEnrichment
+ CraftingDatasetSnapshot
-> CraftActionEngine
-> CraftActionApplicability
```

`CraftActionEngine` returns `APPLICABLE`, `NOT_APPLICABLE`, or `UNKNOWN`. `UNKNOWN` is a valid result and must not be collapsed into `NOT_APPLICABLE`.

## Implemented Contracts

Executable contracts live in `packages/shared/donniecraftshell_contracts/crafting_actions.py`.

- `CraftingDatasetSnapshot`: explicit versioned action dataset.
- `CraftActionDefinition`: action ID, source-backed summary, preconditions, required materials, provenance, and `simulation_supported=false`.
- `CraftActionPrecondition`: rarity, corruption/state, explicit modifier, open affix slot, and item-class checks.
- `RequiredMaterial`: references EconomyAsset IDs, not action IDs.
- `CraftActionApplicability`: status, reasons, failed preconditions, unknown preconditions, materials, confidence, and provenance.

## Current Dataset

Normalized dataset:

```text
data/normalized/crafting/crafting-actions-poe2-quiver-2026-08-12-research/actions.json
```

Source-backed action definitions currently include:

- Orb of Annulment
- Exalted Orb
- Greater Exalted Orb
- Perfect Exalted Orb
- Exalted Orb + Omen of Catalysing Exaltation
- Exalted Orb + Omen of Greater Exaltation
- Exalted Orb + Omen of Sinistral Exaltation
- Exalted Orb + Omen of Dextral Exaltation
- Orb of Annulment + Omen of Greater Annulment
- Orb of Annulment + Omen of Sinistral Annulment
- Orb of Annulment + Omen of Dextral Annulment
- Essence of Hysteria

These are `PROVISIONAL` because sources are community references, not official GGG mechanics documentation.

## Applicability Rules

Verified modeled preconditions include rarity restrictions, non-corrupted item state for regular crafting, explicit-modifier presence for removal actions, and Quiver item-class applicability for Essence of Hysteria.

Task 7B adds the affix-capacity layer described in [AFFIX_CAPACITY.md](AFFIX_CAPACITY.md). Exalted-style actions that add a modifier still return `UNKNOWN` when evaluated with only parser output, but can become `APPLICABLE` or `NOT_APPLICABLE` when a source-backed `AffixStateResolution` is supplied.

Open-slot scopes:

- no precondition value: any explicit prefix or suffix slot
- `PREFIX`: prefix-specific actions such as Sinistral Exaltation
- `SUFFIX`: suffix-specific actions such as Dextral Exaltation

## Economy Boundary

Crafting actions expose required materials only. Cost calculation passes `RequiredMaterial` entries to the Economy cost service from [ECONOMY.md](ECONOMY.md). The Craft Action Engine must not fetch prices or calculate market cost.

Task 7C adds `CraftActionCandidate` and `CraftActionCostService`. Candidate enumeration composes `CraftActionApplicability` with `CraftMaterialCost`, but does not rank actions or recommend a winner. See [CRAFT_ACTION_COSTS.md](CRAFT_ACTION_COSTS.md).

## Limitations

Outcome-space behavior is modeled separately in [CRAFT_OUTCOMES.md](CRAFT_OUTCOMES.md). Crafting actions still do not contain prices, probabilities, valuation, EV, or recommendations.
