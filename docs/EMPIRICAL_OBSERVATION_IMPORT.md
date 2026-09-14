# Empirical Observation Import

Task 15C adds a safe offline workflow for collecting raw crafting observations that can later feed the empirical probability pipeline.

This workflow does not create gameplay observations, scrape data, infer outcomes, or make any current real action probability known by default.

## Pipeline

```text
Guided trial confirmation or JSON/CSV observation files
-> EmpiricalCraftingObservation validation
-> duplicate raw record filtering
-> context partitioning
-> RawEmpiricalProbabilityDataset JSON
-> EmpiricalProbabilityRepository
-> EmpiricalProbabilityProvider
```

## Observation Record Schema

Each raw observation record requires:

- `raw_record_id`
- `action_id`
- `source_outcome_set_id`
- `item_class`
- `league`
- `observed_at`
- `source_id`
- `source_type`
- either `outcome_id` or `unclassified = true`

Recommended context/provenance fields:

- `game`
- `game_version`
- `crafting_dataset_version`
- `modifier_dataset_version`
- `source_uri`
- `synthetic`
- `verification_status`
- `notes`

Unclassified records must not include `outcome_id`. DonnieCraftShell never infers an outcome for them.

The guided real-trial API writes the same raw-record shape after a separate
preview and explicit operator confirmation. Guided audit fields such as
`guided_session_id`, `guided_trial_id`, before/after raw SHA-256 hashes, and
modifier diff summaries may be present; they are provenance metadata, not
probability counts. The importer still counts only accepted, valid,
deduplicated observations and preserves unclassified trials in the denominator.

For non-synthetic observations, Task #95 makes source/context provenance
mandatory rather than merely recommended. A production-shaped record must
include `source_uri`, `game_version`, `crafting_dataset_version`, and
`modifier_dataset_version`, and it must not use `source_type = INTERNAL`.
Records missing that context are rejected before aggregation so they cannot
become selectable empirical probability evidence accidentally.

## Deduplication

`raw_record_id` is the deduplication key within an import batch.

The first valid record with a given ID is accepted. Later duplicate IDs are reported and ignored so they cannot inflate counts.

## Context Partitioning

Records are partitioned by:

- action ID
- source outcome-set identity
- game
- league
- item class
- game version
- crafting dataset version
- modifier dataset version
- synthetic flag
- source type
- verification status

Different leagues, patches, actions, outcome sets, synthetic status values, source types, or verification statuses are not merged silently. They produce separate aggregated datasets.

Missing game/crafting/modifier version fields remain missing and generate warnings. They are not guessed.

For non-synthetic records these version fields are required at validation time.
The warning-only path remains for synthetic and legacy-shaped test fixtures.

## Dataset Identity

Aggregated dataset IDs are deterministic from both:

- the context partition, and
- the aggregated evidence identity.

The evidence fingerprint includes sorted accepted `raw_record_id` values and their classified outcome or explicit `UNCLASSIFIED` status. Re-importing the same records in a different order yields the same dataset ID; a different accepted record set under the same context yields a different dataset ID.

## Synthetic Policy

Synthetic/test observations can be imported, but remain marked `synthetic`.

Production/default probability dependency assembly skips synthetic empirical datasets. Synthetic data requires explicit test-only dependency injection and `allow_synthetic=True`.

Synthetic fixtures may use internal/local provenance for tests. That exception
does not apply to real empirical evidence.

## CLI

Use:

```text
python scripts/import_empirical_observations.py observations.json --output data/raw/probability/my-dataset.json --retrieved-at 2026-08-13T00:00:00+00:00
```

Multiple input files are accepted:

```text
python scripts/import_empirical_observations.py batch-a.json batch-b.csv --output data/raw/probability/imported/
```

If multiple context partitions are produced, `--output` must be a directory.

The command reports:

- accepted records
- duplicate records
- unclassified records
- rejected malformed records
- datasets written
- warnings

It refuses to overwrite existing output unless `--overwrite` is supplied.

## Output

The output is the Task 15A raw empirical probability dataset shape:

- `dataset_id`
- `action_id`
- `source_outcome_set_id`
- `game`
- `league`
- context versions
- `observations[]` with `outcome_id`, `observed_count`, and `raw_record_ids`
- `unclassified_count`
- source/provenance fields
- warnings

Importing observations does not bypass Task 15A readiness. Unclassified records remain in the denominator, and insufficient samples or missing outcome counts still block `COMPLETE` probability readiness.

## Future Recorder

A future manual or in-game-assisted recorder should emit the same record shape. It must preserve the raw record ID, context, source, timestamp, and explicit classification/unclassified status before any aggregation occurs.

Task #95 reviewed public sources for ordinary Orb of Annulment trial data and
did not find a trustworthy reproducible public dataset. See
[ANNULMENT_EMPIRICAL_PROBABILITY_EVIDENCE_2026-09-14.md](data/ANNULMENT_EMPIRICAL_PROBABILITY_EVIDENCE_2026-09-14.md).
