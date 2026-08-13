# Empirical Probability Evidence

Task 15A adds an offline, framework-independent pipeline for empirical crafting outcome observations.

It does not make any current Path of Exile 2 action probability numerically known by default. Real actions still use `UNKNOWN` probabilities unless a context-compatible empirical dataset is explicitly supplied.

## Pipeline

```text
RawProbabilityObservations
-> validator/normalizer
-> EmpiricalProbabilityDataset
-> EmpiricalProbabilityProvider
-> OutcomeProbabilityModel
```

The provider attaches `ProbabilityEvidence` beside an existing `CraftOutcomeSet`. It does not mutate outcome data, calculate EV, value items, or rank advisor actions.

## Raw Dataset Format

Raw datasets live under `data/raw/probability/`.

Required fields:

- `dataset_id`
- `action_id`
- `source_outcome_set_id`
- `game`
- `league`
- `retrieved_at`
- `observations`

Important optional/context fields:

- `item_class`
- `game_version`
- `crafting_dataset_version`
- `modifier_dataset_version`
- `source_uri`
- `source_type`
- `verification_status`
- `methodology`
- `unclassified_count`
- `warnings`

Each observation records:

- `outcome_id`
- `observed_count`
- optional `raw_record_ids`
- optional `warnings`

Missing or unclassified observations must remain explicit. They are not silently dropped and are never treated as zero-probability outcomes.

## Statistical Method

`dc-empirical-probability-v1` uses:

- point estimate: `observed_count / denominator`
- denominator: classified observations plus unclassified/unmapped observations
- interval: Wilson score one-vs-rest interval for each outcome bucket
- arithmetic: Python `Decimal`; binary floating point is not allowed

This is a conservative MVP method for bounded empirical evidence. The interval is not official game mechanics and does not prove future patch stability.

## Readiness

`dc-empirical-readiness-policy-v1` currently requires:

- every outcome in the `CraftOutcomeSet` has an explicit empirical count
- no unclassified observations
- no observations mapped outside the selected outcome set
- sample size is at least the configured threshold
- action, outcome-set identity, league, game/crafting/modifier dataset context are compatible where provided

If any requirement fails, the probability model is `PARTIAL` or `UNKNOWN`. It must not pass EV probability readiness.

## Synthetic Fixture

`data/raw/probability/synthetic_empirical_annulment_outcomes.json` is deliberately synthetic and test-only.

It proves the ingestion and normalization plumbing, but it is not PoE2 gameplay evidence and must not be loaded as production probability data.

## Current Real Actions

Current supported real actions remain numerically `UNKNOWN` without explicit empirical evidence:

- Orb of Annulment and Omen variants
- Exalted Orb and Omen variants
- Greater/Perfect Exalted variants
- Essence of Hysteria final outcomes

Essence of Hysteria may still carry deterministic operation evidence for the guaranteed component while final outcome probability remains unknown.

## Future Real Evidence

Before any real empirical probability dataset is accepted, it must document:

- exact action and item context
- patch/game version where known
- league
- outcome identification method
- raw denominator and unclassified count handling
- sample-size limitations
- source/provenance
- methodology and known biases

Empirical evidence is not official mechanical probability. It remains patch-sensitive and must not be presented as exact unless the methodology and source justify that status.
