# Crafting Sources

This document records Task 7A crafting-mechanic research policy and findings. It complements [DATA_SOURCES.md](DATA_SOURCES.md).

## Source Policy

Preferred sources are official GGG documentation and in-game item text. Where official mechanics pages are unavailable, community sources may be used as `PROVISIONAL` evidence with provenance. Do not copy wiki prose into datasets.

Every normalized action definition must preserve:

- source identifier
- source URI
- retrieval timestamp
- verification status
- short factual mechanic summary
- notes for ambiguity

## Sources Used

- PoE2DB Currency pages: currency tooltip-style facts for Exalted Orb, Greater Exalted Orb, Perfect Exalted Orb, and Orb of Annulment.
- PoE2DB Omen pages: Omen text for Exaltation and Annulment modifiers.
- PoE2DB Essence of Hysteria page: rare-item essence behavior and Quiver listed guaranteed modifier.
- PoE2 Wiki Orb of Annulment page: magic/rare targeting text and related Omen references.
- PoE2 Wiki Corrupted page: regular crafting cannot modify corrupted items.

These sources are community sources and remain `PROVISIONAL` until verified against official or in-game evidence.

## Research Findings

- Orb of Annulment: source-backed as removing a random modifier; applicability modeled for Magic/Rare, non-corrupted items with an explicit modifier.
- Exalted Orb variants: source-backed as augmenting Rare items with a new random modifier. Applicability remains `UNKNOWN` without verified open affix capacity.
- Greater/Perfect Exalted Orb: source-backed minimum modifier level text is captured, but its exact downstream outcome meaning is not implemented.
- Omens: Sinistral/Dextral Annulment and Catalysing Exaltation are captured as modifier actions. Their effects are not simulated.
- Essence of Hysteria: source-backed for Rare items and Quivers in PoE2DB. Applicability is separate from its future guaranteed outcome simulation.

## Needs Verification

- Quiver prefix/suffix capacity and reliable open-slot calculation.
- Whether all regular crafting restrictions for corrupted and twice-corrupted items are fully covered by the current source set.
- Full Omen set relevant to Quiver crafting.
- Full Essence set and exact item-class applicability.
- Official GGG source for action mechanics, if available.
