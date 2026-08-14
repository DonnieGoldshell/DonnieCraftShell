# Curated Observation Import

Task 16C connects reviewed observation exports to the existing Task 15C empirical observation importer.

```text
record
→ review
→ accepted export
→ validated import
→ context partition
→ raw empirical probability dataset
→ optional explicit Advisor probability context
```

The build workflow does not calculate probabilities, activate evidence for Advisor requests, change EV readiness, or rank actions. It only creates Task 15A-compatible raw empirical probability datasets from accepted review exports.

## Input

The builder consumes a Task 16B accepted export:

```json
{
  "review_version": "dc-observation-review-v1",
  "observations": [
    {
      "raw_record_id": "manual-craft-observation-...",
      "action_id": "dc:poe2:craft-action:orb-of-annulment",
      "source_outcome_set_id": "backend-outcome-set:...",
      "item_class": "Quivers",
      "league": "Runes of Aldur",
      "observed_at": "2026-08-14T07:45:00+00:00",
      "source_id": "browser-manual-recorder-session",
      "source_type": "MANUAL_RESEARCH",
      "outcome_id": "outcome-...",
      "unclassified": false,
      "synthetic": false
    }
  ]
}
```

Rejected, pending, duplicate, malformed, and otherwise non-exported review records are not part of this input. The build service still validates every supplied record defensively through the Task 15C `EmpiricalCraftingObservation` contract.

## Output

`CuratedObservationBuildResult` reports:

- source record count
- successfully imported record count
- post-deduplication accepted count
- duplicate count
- unclassified count
- invalid/rejected count
- generated dataset IDs
- Task 15A-compatible raw empirical probability dataset payloads
- validation warnings and rejected-record reasons

Unclassified observations remain unclassified and retain Task 15C/15A denominator semantics. Duplicate raw IDs are not double-counted. Incompatible contexts remain partitioned by the existing Task 15C context key, including league, action ID, source outcome-set ID, dataset versions, synthetic flag, source type, and verification status.

## API And Frontend

`POST /api/v1/observations/build-empirical-datasets` accepts:

- `accepted_export`
- optional `dataset_id_prefix`

The web workbench can submit the accepted export from Observation Review and display build counts, warnings, and generated dataset IDs. This is a local/operator workflow; it does not persist datasets to a production repository or silently select them for Advisor analysis.

## Probability Boundary

Dataset creation alone is not probability readiness. A future Advisor request must explicitly select a configured/imported empirical probability dataset, and Task 15A/15B readiness gates must still validate context compatibility, sample size, completeness, and synthetic-data policy.
