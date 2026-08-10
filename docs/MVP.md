# MVP

## Scope

The first MVP focuses only on rare Quivers in Path of Exile 2. The goal is to evaluate one pasted item and recommend whether the player should continue crafting or sell the item now.

## Target Workflow

1. Paste PoE2 Quiver clipboard text.
2. Parse item base, item level, rarity, and modifiers.
3. Identify modifier tiers.
4. Determine prefixes, suffixes, and open affix slots.
5. Obtain current economy data.
6. Generate legal crafting actions.
7. Estimate outcomes and crafting costs.
8. Calculate expected value.
9. Compare against **SELL NOW**.
10. Recommend **CRAFT** or **SELL**.

## MVP Boundaries

- Rare Quivers only.
- No support for other item classes yet.
- No unverified crafting rules.
- No automated trade execution.
- No account integration.

## Acceptance Criteria

- The system clearly separates parsed item data, economy data, crafting actions, and recommendation logic.
- Every PoE2 rule used by the system is linked to a verified source or marked `TODO / NEEDS VERIFICATION`.
- The recommendation includes expected value, cost estimate, and sell-now comparison.

## Risks

- Reliable economy data may be difficult to source.
- Modifier tier and crafting legality data must be verified before recommendations can be trusted.
- Expected value calculations require explicit assumptions and confidence levels.
