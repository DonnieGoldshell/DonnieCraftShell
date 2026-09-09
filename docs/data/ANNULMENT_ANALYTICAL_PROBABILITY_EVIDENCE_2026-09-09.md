# Orb of Annulment Current-Game Analytical Probability Evidence

Research date: `2026-09-09`

Issue: [#89](https://github.com/DonnieGoldshell/DonnieCraftShell/issues/89)

Prior decision: [#41 / PR #42](https://github.com/DonnieGoldshell/DonnieCraftShell/pull/42)

Decision: `INSUFFICIENT EVIDENCE — REMAINS UNKNOWN`

No production analytical probability rule was promoted.

## Research Question

Can DonnieCraftShell now verify a current-game, source-backed numerical
selection law for available Path of Exile 2 Annulment actions, especially
ordinary Orb of Annulment and the current side- or Desecrated-constrained Omen
variants?

## Sources Reviewed

| Source | Type | URI | Supports | Does not support | Verification decision |
| --- | --- | --- | --- | --- | --- |
| Grinding Gear Games developer docs | Official | https://www.pathofexile.com/developer/docs/reference | Official developer API surface; Currency Exchange history endpoint exists for PoE2 economy data. | Crafting probability endpoints, modifier-selection law, Annulment eligibility. | `VERIFIED` for API limitation only. |
| PoE2DB Currency page | Community structured/game-derived | https://poe2db.tw/us/Currency | Orb of Annulment item text says it removes a random modifier from an item. | Uniform selection, eligible modifier classes, special-origin handling. | `PROVISIONAL` mechanic evidence; insufficient for probability rule. |
| PoE2DB Omen page | Community structured/game-derived | https://poe2db.tw/us/Omen | Current Omen text for Sinistral, Dextral, and Light constraints. | Distribution inside prefix, suffix, or Desecrated-restricted pools. | `PROVISIONAL` scope evidence only. |
| PoE2 Wiki Omen of Light | Community wiki | https://www.poe2wiki.net/wiki/Omen_of_Light | Corroborates that Omen of Light constrains the next Orb of Annulment to Desecrated modifiers. | Whether selection among Desecrated modifiers is uniform; ordinary Annulment Desecrated eligibility without the Omen. | `PROVISIONAL`; useful for current-game scope only. |
| PoE2 Wiki Desecrated modifier | Community wiki | https://www.poe2wiki.net/wiki/Desecrated_modifier | Current Desecrated modifier context, including revealed/unrevealed modifier concepts and prefix/suffix slot framing. | Ordinary Annulment eligibility and numeric selection law for revealed or unrevealed Desecrated modifiers. | `PROVISIONAL`; not enough to promote. |
| PoE2 craft-planner / community code notes | Community/open-source notes | https://github.com/Ayuichi/poe2-craft-planner | Some notes assert uniform-style calculations and side restrictions. | Independent authoritative proof; production-safe current-game verification. | `LOW`; not accepted for production promotion. |
| PoE2CraftAndTrader community notes | Community/open-source notes | https://github.com/asaifuddin/PoE2CraftAndTrader | Contains implementation-like claims about Annulment behavior. | Authoritative source provenance for exact probabilities or special-origin eligibility. | `LOW`; not accepted for production promotion. |

## Current-Game Findings

The current evidence strengthens eligible-set wording but does not provide a
numeric probability law.

Supported scope facts:

- Ordinary Orb of Annulment removes one random modifier from an item.
- Omen of Sinistral Annulment restricts the next Orb of Annulment to prefix
  modifiers.
- Omen of Dextral Annulment restricts the next Orb of Annulment to suffix
  modifiers.
- Omen of Light restricts the next Orb of Annulment to Desecrated modifiers.
- Current Desecrated modifier documentation treats Desecrated modifier state as
  relevant to affix slots and Omen of Light targeting.
- Omen of Greater Annulment is not part of the current action-generation target
  for this review; issue #87 retired it from current-league actionability.

Unverified claims:

- that "random" means uniform selection across the eligible set;
- that ordinary Annulment gives each eligible explicit modifier probability
  `1 / N`;
- whether the same selection law applies after Sinistral, Dextral, or Light
  restrictions;
- whether ordinary Annulment can remove crafted modifiers in the same pool as
  natural explicit modifiers;
- whether ordinary Annulment can remove Desecrated modifiers without Omen of
  Light;
- whether revealed and unrevealed Desecrated modifiers differ for ordinary
  Annulment eligibility;
- whether fractured, locked, corruption-enhancement, or other special-origin
  modifiers are excluded or handled specially;
- current game-version scope strong enough to make a production registry rule
  historically reproducible.

## Bramble Spike Pilot Decision

The current First Playable Bramble Spike / Primed Quiver pilot contains six
explicit modifiers, including crafted and Desecrated-origin modifiers. Because
the current evidence still does not verify both:

1. the full eligible set for those origins, and
2. a numeric selection law over that set,

DonnieCraftShell must not assign `1/6` probabilities to the six enumerated
ordinary Annulment outcomes.

The probability blocker remains correct and actionable:

```text
PROBABILITY_EVIDENCE_REQUIRED
```

## Registry Decision

The production verified-mechanic registry remains:

```text
data/normalized/probability/verified-analytical-mechanics-empty-2026-08-25/registry.json
```

It stays intentionally empty. `AnalyticalProbabilityProvider` must continue to
return `UNKNOWN` for real Annulment actions unless a future `VERIFIED` rule with
`VERIFIED` provenance is added.

## Future Promotion Requirements

A future production analytical rule still requires source-backed evidence for:

- exact eligible modifier classes, including crafted, Desecrated, fractured,
  locked, corruption-enhancement, and other special-origin modifiers;
- exact revealed versus unrevealed Desecrated treatment;
- exact side-restricted and Desecrated-restricted Omen semantics;
- numerical selection law, such as uniform selection over the eligible set;
- current game/version scope;
- compatibility conditions strict enough that unsupported item states fail
  closed to `UNKNOWN`.

Until those facts are verified, possible Annulment outcomes remain enumerable,
but their probabilities remain unknown.
