# Orb of Annulment Analytical Probability Evidence

Research date: `2026-08-25`

Issue: [#41](https://github.com/DonnieGoldshell/DonnieCraftShell/issues/41)

Decision: `INSUFFICIENT EVIDENCE — REMAINS UNKNOWN`

No production analytical probability rule was promoted.

## Research Question

Can DonnieCraftShell verify a source-backed numerical selection law for ordinary
Path of Exile 2 Orb of Annulment outcomes, such as uniform selection across all
eligible explicit modifiers?

## Sources Reviewed

| Source | Type | URI | Supports | Does not support | Verification decision |
| --- | --- | --- | --- | --- | --- |
| Grinding Gear Games developer docs | Official | https://www.pathofexile.com/developer/docs/reference | Official PoE2 API surface is limited; no modifier-probability or crafting-probability endpoint is documented. | Orb of Annulment eligibility, uniform selection, crafted/desecrated/special modifier treatment. | `VERIFIED` for API limitation only. |
| PoE2DB Currency page | Community structured/game-derived | https://poe2db.tw/us/Currency | Orb of Annulment item text: it removes a random modifier from an item. | Uniform selection, explicit-only eligibility, crafted/desecrated/special modifier handling. | `PROVISIONAL` mechanic evidence; insufficient for probability rule. |
| PoE2DB Modifiers page | Community structured/game-derived | https://poe2db.tw/us/Modifiers | Omen text for Greater/Sinistral/Dextral Annulment and Omen of Light restrictions. | Distribution within restricted prefix/suffix/desecrated pools; ordinary Annulment uniformity. | `PROVISIONAL` supporting scope evidence only. |
| PoE2 Wiki Orb of Annulment | Community wiki | https://www.poe2wiki.net/wiki/Orb_of_Annulment | Repeats item text and states magic/rare usability; lists related Annulment Omens. | Equal probability per eligible modifier; exact eligibility exclusions for crafted/desecrated/fractured/special modifiers in PoE2. | `PROVISIONAL`; not enough to promote. |
| PoE2 Wiki Crafting | Community wiki | https://www.poe2wiki.net/wiki/Crafting | Describes Annulment as removing an explicit modifier without affecting rarity. | Numerical selection law and special-origin edge cases. | `PROVISIONAL`; useful for outcome-space wording only. |
| PoE2 craft-planner community notes | Community/open-source notes | https://github.com/Ayuichi/poe2-craft-planner/blob/main/crafting-knowledge-base.md | Repeats the one-random-mod summary and Omen side targeting. | Independent authoritative evidence for uniform probability. | `LOW`; not accepted for production registry promotion. |

## Findings

The strongest current sources reviewed establish the following safe facts:

- Ordinary Orb of Annulment removes one random modifier from an item.
- Community/wiki wording indicates magic and rare items are valid targets.
- Omen of Sinistral Annulment restricts the next Orb of Annulment to prefix
  modifiers.
- Omen of Dextral Annulment restricts the next Orb of Annulment to suffix
  modifiers.
- Omen of Greater Annulment removes two modifiers, but this does not establish
  simultaneous versus sequential selection semantics.
- Omen of Light restricts the next Orb of Annulment to Desecrated modifiers.

The sources reviewed do not establish:

- that "random" means uniform selection across eligible modifiers;
- that each eligible explicit modifier has probability `1 / N`;
- whether ordinary Annulment eligibility includes or excludes crafted,
  desecrated, fractured, corruption-enhancement, or other special-origin
  modifiers in every relevant item state;
- whether side-restricted Annulment Omens are uniform within the restricted
  side;
- how Greater Annulment selects two modifiers;
- whether the current First Playable Primed Quiver's crafted and desecrated
  explicit modifiers are safely covered by any uniform ordinary-Annulment rule.

## Registry Decision

The existing analytical registry contract requires a `VERIFIED` source-backed
selection law before a production rule can emit numeric probabilities. The
available evidence supports outcome-space enumeration, but not numeric
probability assignment.

Therefore DonnieCraftShell keeps:

```text
data/normalized/probability/verified-analytical-mechanics-empty-2026-08-25/registry.json
```

empty for production. Orb of Annulment remains probability `UNKNOWN`, and the
Advisor probability blocker remains valid.

## First Playable Compatibility

The First Playable Primed Quiver can enumerate ordinary Annulment removal
outcomes, but it includes crafted/desecrated explicit modifiers. Because source
evidence does not verify that these modifier origins are included in the same
uniform removal pool as ordinary explicit modifiers, no production analytical
rule can safely clear its probability blocker.

## Future Promotion Requirements

A future task may promote an ordinary Annulment analytical rule only if a source
verifies all required conditions for the intended scope:

- eligible modifier set, including explicit handling of crafted, desecrated,
  fractured, corruption-enhancement, and other special-origin modifiers;
- numerical selection law, such as uniform selection over the eligible set;
- game/version scope;
- whether side-restricted Omens inherit the same selection law inside the
  restricted set;
- whether the verified scope covers the concrete `CraftOutcomeSet` identity or
  a broader class of outcome sets without weakening fail-closed behavior.

Until then, possible outcome does not imply equally likely outcome.
