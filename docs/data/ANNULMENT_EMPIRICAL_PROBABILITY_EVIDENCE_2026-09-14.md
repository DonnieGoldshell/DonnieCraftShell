# Orb of Annulment Empirical Probability Evidence Path

Research date: `2026-09-14`

Issue: [#95](https://github.com/DonnieGoldshell/DonnieCraftShell/issues/95)

Prior analytical decisions:

- [#41 / PR #42](https://github.com/DonnieGoldshell/DonnieCraftShell/pull/42)
- [#89 / PR #90](https://github.com/DonnieGoldshell/DonnieCraftShell/pull/90)

Decision: `NO TRUSTWORTHY PUBLIC EMPIRICAL DATASET FOUND — REMAINS UNKNOWN`

No production empirical probability dataset was added.

## Research Question

Does a trustworthy, reproducible public Path of Exile 2 dataset exist today
that contains actual observed Orb of Annulment random-removal trials with enough
context to satisfy DonnieCraftShell's empirical probability contracts?

## Sources Evaluated

| Source | Type | URI | Finding | Decision |
| --- | --- | --- | --- | --- |
| Prior analytical review | Project evidence decision | https://github.com/DonnieGoldshell/DonnieCraftShell/pull/42 | Reviewed mechanic text and concluded that `random` did not verify a uniform selection law or special-origin eligibility. | Retained as authoritative prior decision. |
| Current-game analytical recheck | Project evidence decision | https://github.com/DonnieGoldshell/DonnieCraftShell/pull/90 | Rechecked current Annulment, side-restricted Omens, and Desecrated context; still no numeric selection law. | Retained as authoritative prior decision. |
| PoE2DB Orb of Annulment page | Community structured/game-derived | https://poe2db.tw/us/Orb_of_Annulment | Provides item/currency facts and economy rows. It does not publish observed Annulment outcome trials. | Rejected as empirical probability source. |
| PoE2 Wiki Trial of Chaos page | Community wiki | https://www.poe2wiki.net/wiki/The_Trial_of_Chaos | Contains the item wording that Orb of Annulment removes a random modifier from a magic or rare item. It does not provide observed trial records. | Mechanic wording only; not empirical probability evidence. |
| PoE2 Craft Planner | Community simulator/tool | https://yacinebedd.github.io/PoE-Craft/ | Describes simulator assumptions/calculated odds for Annulment and related mechanics. It is not a reproducible raw real-trial dataset for DonnieCraftShell import. | Rejected as empirical production evidence. |
| Ayuichi PoE2 craft-planner notes | Community/open-source notes | https://github.com/Ayuichi/poe2-craft-planner/blob/main/crafting-knowledge-base.md | Lists crafting effects and assumptions. It does not provide raw observed Annulment trials. | Rejected as empirical production evidence. |
| Public web/GitHub search | Discovery sweep | Search queries for PoE2 Annulment observations, trials, sample size, and datasets | Returned economy pages, mechanic explanations, simulators, and unrelated market/material data rather than reproducible outcome observations. | No accepted dataset found. |

## Accepted Evidence

None.

No source found in this pass provided all of:

- real observed Orb of Annulment applications;
- before/after item or outcome identity;
- action identity and item class;
- league and game/patch context;
- source provenance and retrieval context;
- enough records to build a reproducible denominator;
- licensing/terms clarity suitable for DonnieCraftShell production use.

## Implementation Decision

The existing empirical pipeline remains the correct path:

```text
real manual/exported observations
-> empirical observation import
-> raw empirical probability dataset
-> explicit registry registration
-> explicit Advisor dataset selection
-> EmpiricalProbabilityProvider
```

Issue #95 tightens that path for production-shaped observations. Non-synthetic
empirical observation records now require:

- `source_uri`;
- `game_version`;
- `crafting_dataset_version`;
- `modifier_dataset_version`;
- non-`INTERNAL` source type.

This prevents a real-looking batch with insufficient provenance or context from
being pooled into a selectable probability dataset. Synthetic fixtures remain
allowed for tests, but production/default providers continue to skip them.

## Bramble Spike Result

The First Playable Bramble Spike / Primed Quiver ordinary Annulment state still
has no selected compatible real empirical dataset.

```text
Ordinary Orb of Annulment probability: UNKNOWN
Accepted real empirical observations: 0
Selected compatible empirical dataset: none
Analytical fallback: UNKNOWN
Outcome valuation status: unchanged and independent
```

No `1/6` probability is reported. The six mechanically possible removal
outcomes remain possible outcomes only, not equally likely outcomes.

## What Would Unblock Probability

To move from `UNKNOWN` to usable empirical probability, DonnieCraftShell needs a
real observation batch or public dataset that can be imported with:

- stable unique raw record IDs;
- exact action ID and source outcome-set identity;
- league and game/patch version;
- crafting and modifier dataset versions used to identify outcomes;
- explicit outcome ID or explicit unclassified status per trial;
- source URI/source identifier and collection methodology;
- enough accepted classified observations to satisfy the configured empirical
readiness policy.

Small samples may produce `PARTIAL` empirical models but must not clear EV
readiness until the existing policy gates are satisfied.
