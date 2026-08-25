# Analytical Probability Registry

Task 22C adds a local, versioned registry for verified crafting-mechanic
evidence that can be promoted into analytical probability rules.

## Boundary

The registry is offline and source-backed. It performs no scraping and does not
create probabilities by itself. It only converts accepted `VERIFIED` records
into `AnalyticalProbabilityRule` objects for the probability provider.

Production currently uses:

```text
data/normalized/probability/verified-analytical-mechanics-empty-2026-08-25/registry.json
```

That dataset is intentionally empty. No real PoE2 Annulment, Omen, Essence
random-removal, or Exalted-style probability rule is enabled.

Task 23 re-reviewed ordinary Orb of Annulment as the first possible production
mechanic promotion. The evidence remained insufficient to verify uniform
selection or special-origin eligibility, so no rule was promoted. See
[ANNULMENT_ANALYTICAL_PROBABILITY_EVIDENCE_2026-08-25.md](data/ANNULMENT_ANALYTICAL_PROBABILITY_EVIDENCE_2026-08-25.md).

## Registry Envelope

```json
{
  "dataset_id": "verified-analytical-mechanics-empty-2026-08-25",
  "registry_version": "dc-analytical-mechanic-registry-v1",
  "rules": []
}
```

Each rule record may include:

- `rule_id`
- `action_id`
- `rule_type`
- `methodology`
- `verification_status`
- `provenance`
- `required_selection_rule`
- `required_outcome_space_completeness`
- `expected_source_outcome_set_id`
- `expected_outcome_ids`
- `game_version`
- `crafting_dataset_version`
- `modifier_dataset_version`
- `evidence_dataset_version`
- `warnings`

## Verification Gate

Only `VERIFIED` rule records with `VERIFIED` provenance can load as analytical
probability rules.

These statuses cannot be promoted:

- `CURATED`
- `PROVISIONAL`
- `NEEDS_VERIFICATION`
- `DERIVED`

Malformed records, unsupported enum values, non-verified records,
non-verified provenance, duplicate rule IDs, and duplicate action scopes are
skipped with explicit warnings. They do not poison Advisor startup or clear
probability blockers.

## Provider Precedence

API dependency assembly uses:

```text
verified analytical registry
-> AnalyticalProbabilityProvider
-> explicitly selected empirical probability provider
-> current research UNKNOWN fallback
```

Providers are not averaged. If a verified analytical rule produces a complete
model, it takes precedence. If no compatible analytical rule exists, empirical
selection can still be used. Otherwise the result remains `UNKNOWN`.

## Promotion Workflow

1. Research and verify the crafting mechanic through a separate evidence task.
2. Capture source URI, retrieval timestamp, source type, and verification notes.
3. Add a `VERIFIED` registry record with `VERIFIED` provenance.
4. Load and validate the registry locally.
5. The analytical provider applies the rule only when the concrete outcome set
   matches the declared action, selection rule, completeness, and optional
   outcome-set identity/outcome IDs.
6. Any mismatch fails closed to `UNKNOWN`.

Possible outcome space is still not probability evidence. A registry rule must
state the verified selection law explicitly.
