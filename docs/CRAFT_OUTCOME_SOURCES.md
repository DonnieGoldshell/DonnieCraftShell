# Craft Outcome Sources

This document records Task 8A source findings for crafting outcome semantics.

## Source Policy

Outcome mechanics require provenance. Community sources are `PROVISIONAL` unless confirmed by official GGG documentation or direct in-game text capture. Low-confidence sources remain low confidence even when they align with stronger sources.

## Findings

### Annulment

Sources: PoE2 Wiki Orb of Annulment, PoE2DB Currency, PoE2 Wiki Sinistral/Dextral Annulment pages.

Modeled fact: ordinary Annulment removes one eligible modifier; Sinistral/Dextral variants restrict removal to prefix/suffix modifiers.

Unresolved:

- Whether every special explicit origin is eligible.
- Exact probability distribution across eligible modifiers.
- Greater Annulment pairwise selection semantics.

### Exalted-Style Addition

Sources: PoE2DB Currency, PoE2 Wiki Omen of Greater Exaltation, PoE2DB/PoE2 Wiki Omen pages.

Modeled fact: Exalted-style actions add explicit modifiers to Rare items, with Omen variants constraining prefix/suffix or adding two modifiers.

Unresolved:

- Modifier weights.
- Cross-family conflict rules beyond captured source group identity.
- Pairwise Greater Exaltation behavior when two additions are possible.
- Perfect/Greater Exalted minimum modifier level downstream behavior beyond source text.

### Essence of Hysteria

Sources: PoE2DB Essence of Hysteria and supporting community essence references.

Modeled fact: Essence of Hysteria removes a random modifier from a Rare item and adds a guaranteed Quiver modifier family corresponding to increased Damage with Bow Skills.

Unresolved:

- Atomic replacement/addition capacity behavior.
- Exact eligible removed modifier set for special origins.
- Numeric probability model.

## Probability

No Task 8A source provides usable modifier weights or verified equal selection probabilities. Probability completeness therefore remains `UNKNOWN`; no equal distribution fallback is allowed.

Task 8C expands the natural explicit Quiver Base Prefix/Suffix pool but does not add weights. See [QUIVER_MODIFIER_POOL_STATUS.md](QUIVER_MODIFIER_POOL_STATUS.md).
