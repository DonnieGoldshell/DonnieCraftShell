# Probability Research

Task 9A determines whether DonnieCraftShell can assign defensible numeric outcome probabilities. It does not implement probability calculation.

## Core Conclusion

Complete outcome space is not complete probability. The Quiver natural Base pool is complete for the selected Task 8C PoE2DB snapshot, but modifier weights are unavailable. Therefore Exalted-style outcomes remain probability `UNKNOWN`.

Removal actions use source text such as "random modifier", but Task 9A found no strong source proving uniform selection across eligible modifiers. Random is not the same as equally likely.

## Feasibility Matrix

| Action | Outcome space | Probability status | Numeric probability possible? | Evidence | Main blocker |
| --- | --- | --- | --- | --- | --- |
| Orb of Annulment | Complete when eligible explicit modifiers are known | `UNKNOWN` | No | Removes a random modifier | Uniform selection not verified |
| Sinistral Annulment + Annulment | Complete for known prefixes | `UNKNOWN` | No | Removes only prefix modifiers | Uniform prefix selection not verified |
| Dextral Annulment + Annulment | Complete for known suffixes | `UNKNOWN` | No | Removes only suffix modifiers | Uniform suffix selection not verified |
| Greater Annulment + Annulment | Partial | `UNKNOWN` | No | Removes two modifiers | Sequential/simultaneous selection and distribution unknown |
| Exalted Orb | Complete for scoped Quiver Base pool when state/group data are complete | `UNKNOWN` | No | Adds a random modifier | Modifier weights unavailable |
| Greater Exalted Orb | Complete for filtered pool when minimum modifier level is modeled | `UNKNOWN` | No | Adds random modifier with minimum modifier level 35 | Weight semantics unavailable |
| Perfect Exalted Orb | Complete for filtered pool when minimum modifier level is modeled | `UNKNOWN` | No | Adds random modifier with minimum modifier level 50 | Weight semantics unavailable |
| Sinistral Exaltation + Exalted | Complete for prefix pool | `UNKNOWN` | No | Adds only prefix modifiers | Prefix modifier weights unavailable |
| Dextral Exaltation + Exalted | Complete for suffix pool | `UNKNOWN` | No | Adds only suffix modifiers | Suffix modifier weights unavailable |
| Catalysing Exaltation + Exalted | Partial | `UNKNOWN` | No | Increases chance of catalyst-corresponding modifier type | Catalyst quality applicability and formula unknown |
| Greater Exaltation + Exalted | Partial | `UNKNOWN` | No | Adds two random modifiers | Pairwise pool transition and weights unknown |
| Essence of Hysteria on Quiver | Partial | `PARTIALLY_KNOWN` | Only deterministic guaranteed component | Removes random modifier and adds guaranteed Quiver Bow Skill Damage modifier | Random removal distribution and atomic behavior unknown |

## Annulment Findings

The best sources establish random removal and prefix/suffix restriction through Omens. They do not establish equal probability per eligible modifier.

Do not calculate `1 / eligible_modifier_count` until a source verifies uniform selection. The future probability model may expose the eligible removal set while leaving probabilities unknown.

Greater Annulment remains weaker: it removes two modifiers, but Task 9A did not verify whether those two are selected simultaneously, sequentially without replacement, or by another rule.

## Essence Findings

Essence of Hysteria has two components:

- Random removal: probability `UNKNOWN`.
- Guaranteed Quiver addition: deterministic family component, but final item-state details remain partial until replacement/capacity semantics are fully modeled.

The guaranteed component may later be represented as probability `1` only for the guaranteed family assertion, not for the full resulting item.

## Exalted Weight Findings

PoE2DB explicitly states that modifier weight information cannot be obtained from game files on the Quivers page. Official GGG developer docs expose limited PoE2 APIs and do not provide a canonical modifier-weight catalogue.

Task 9A found no legitimate source that currently supports:

- tier/family spawn weights,
- weighting formula,
- item-class-specific weight scaling,
- tag/catalyst multipliers,
- Perfect/Greater Exalted weighting semantics after minimum-level filtering.

Therefore no Exalted-style numeric probabilities should be implemented in Task 9B.

## Empirical Estimates

Empirical probability estimates could be a future optional subsystem, separate from exact mechanics. A useful experiment would require controlled repeated crafts with the same item class, base, item level, existing modifier groups, open side, action, league/patch, and source dataset version.

Risks:

- large sample-size requirements for rare outcomes,
- biased community submissions,
- patch changes invalidating old data,
- hidden mechanics or action modifiers,
- confidence intervals often too wide for high-value recommendations.

Trade listings cannot reliably estimate crafting probabilities because listed items are filtered by player behavior, price, and survival bias.

## Probability Evidence Model

Future probability records should be provenance-first:

```text
ProbabilityEvidence
- action_id
- outcome_id or candidate_modifier_id
- probability_type: EXACT_MECHANICAL | DERIVED_MECHANICAL | EMPIRICAL_ESTIMATE | UNKNOWN
- numeric_value
- methodology
- source_uri
- retrieved_at
- game_version
- dataset_version
- confidence
- verification_status
- sample_size
- uncertainty_interval
- warnings
```

`P_i = weight_i / sum(eligible weights)` is allowed only if sources establish that weights are in one eligible pool after item-class, ilvl, side, action, modifier-group, and action-specific filters are applied.

## Task 9B Recommendation

Task 9B implements probability contracts and propagation only, not Exalted numeric probabilities. Implemented scope:

- Framework-independent `ProbabilityEvidence` / `OutcomeProbabilityModel` contracts.
- Current supported final outcome probabilities remain `UNKNOWN` except deterministic guaranteed components.
- Exalted-style candidate weights remain absent.
- Tests prove no equal distribution fallback exists.

See [PROBABILITY_MODEL.md](PROBABILITY_MODEL.md).

## Task 22B Analytical Provider Audit

Task 22B re-audited the current repository contracts and documentation before
adding any analytical rule. The audit found:

- Annulment outcome space can be complete for known eligible explicit
  modifiers, but the repository still does not contain verified evidence that
  selection is uniform across those modifiers.
- Sinistral/Dextral Annulment restrict eligible side, but uniform side-specific
  selection is still not verified.
- Greater Annulment still lacks verified simultaneous/sequential multi-removal
  semantics.
- Exalted-style outcome pools may be complete for scoped natural Quiver Base
  modifiers, but modifier weights and selection formulas remain unavailable.
- Essence of Hysteria has a deterministic guaranteed Quiver modifier component,
  while random-removal probabilities remain unknown.

Therefore Task 22B configures no production analytical probability rules. The
new analytical provider is framework support only until a verified mechanic
source can justify a specific numeric rule. Unsupported actions continue to emit
`UNKNOWN` probability models and `PROBABILITY_EVIDENCE_REQUIRED` blockers.
