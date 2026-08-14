# Observation Review

Task 16B adds a conservative curation step between the manual craft observation recorder and empirical probability imports.

```text
Task 16A recorder export
→ Observation review batch
→ human accept/reject/pending decision
→ accepted-only Task 15C-compatible export
→ separate review manifest
```

Review does not calculate probabilities, prove mechanics, change Advisor readiness, or mutate the original raw observation record.

## Statuses

- `PENDING`: default for every loaded observation. Pending records are retained in the manifest and excluded from accepted exports.
- `ACCEPTED`: explicitly approved for later empirical import. The accepted export contains the original observation record unchanged.
- `REJECTED`: retained in the manifest with notes/reasons and excluded from accepted exports.

Automatic recorder classification is only a classification method; it is not automatic curation acceptance. Manual classification remains visibly manual. Unclassified observations may be accepted as unclassified and must not be coerced into an outcome ID.

## Accepted Export

Accepted export uses the same `{ observations: [...] }` shape consumed by the Task 15C importer. Top-level review metadata such as `review_version`, `exported_at`, and `warnings` may be present, but review decisions stay outside observation records so they cannot become probability counts.

Each accepted observation preserves:

- `raw_record_id`
- action/outcome-set context
- source/provenance fields
- classification method and warnings
- before/after item fingerprints and raw text references when present
- synthetic flag

## Review Manifest

The review manifest is the audit trail. It records every loaded observation, including rejected, pending, and duplicate entries.

Manifest records include:

- raw record ID
- review status, note, reviewer, and timestamp
- exported/not exported flag
- duplicate flag
- classification method and unclassified status
- source IDs, source URI, observed timestamp
- crafting and modifier dataset versions
- before/after fingerprints
- warnings

## Duplicate And Context Handling

Duplicate `raw_record_id` values across loaded batches are surfaced. Duplicate records remain in the manifest, but only one accepted observation with that raw ID can be exported.

Accepted batches are checked for mixed context fields such as action ID, source outcome-set ID, league, item class, game version, crafting dataset version, modifier dataset version, and synthetic status. Mixed synthetic and non-synthetic observations produce warnings because synthetic/test evidence must not silently enter non-synthetic/community datasets.

## API And Frontend

`POST /api/v1/observations/review` accepts one or more recorder export batches plus optional review decisions and returns:

- review records for display
- accepted-only export JSON
- review manifest JSON
- warnings

The web app provides a browser-local workflow to paste a recorder export, inspect records, set `ACCEPTED` / `REJECTED` / `PENDING`, add notes, and export accepted JSON plus the manifest. No database or network source integration is required.

## Probability Boundary

Curated observations are still only evidence inputs. They do not make a probability model complete by themselves. Task 15C import, Task 15A/B probability normalization, sample-size policies, context checks, and readiness gates remain authoritative.

Task 16C continues this path with [CURATED_OBSERVATION_IMPORT.md](CURATED_OBSERVATION_IMPORT.md): accepted exports can be validated and aggregated into raw empirical probability dataset payloads, but those datasets still require explicit configuration/selection before Advisor probability models can use them.
