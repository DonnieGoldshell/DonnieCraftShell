# Observation Workspace

Task 18A adds a local durable workspace for the manual craft observation flow.
Task 18B adds backup/export and restore/import workflow for moving or archiving that workspace without manual file
editing.

The lifecycle remains:

```text
record
-> persist raw evidence
-> review/audit
-> accepted export
-> build empirical dataset
-> register dataset
-> explicitly select dataset in Advisor
```

Persistence does not mean acceptance, probability readiness, EV readiness, or Advisor activation.

## Stored Data

The workspace stores two separate concepts:

- raw recorder export records from Task 16A
- review decisions from Task 16B

The raw record is keyed by `raw_record_id` and is preserved unchanged. Review state is stored separately as audit metadata:

- `PENDING`
- `ACCEPTED`
- `REJECTED`
- reviewer
- note
- review timestamp

Accepted records still flow through `review_observation_batches` and `build_empirical_datasets_from_curated_export`. Pending and rejected records are retained for audit but excluded from accepted exports and empirical counts.

## Local Persistence

The API stores the workspace in local JSON by default:

```text
.dcs/observation_workspace.json
```

`.dcs/` is ignored by git. Override the path with:

```text
DCS_OBSERVATION_WORKSPACE_PATH=/path/to/observation_workspace.json
```

Set `DCS_OBSERVATION_WORKSPACE_PATH=disabled`, `memory`, `:memory:`, or an empty value to use in-memory storage only.

The JSON envelope is transparent and versioned:

```json
{
  "workspace_version": "dc-observation-workspace-v1",
  "storage_version": "dc-observation-workspace-storage-v1",
  "records": [],
  "decisions": []
}
```

Writes use deterministic JSON ordering and same-directory temporary-file replacement before replacing the workspace file.
Record and review-decision saves are transactional at the repository boundary: if persistence fails, the in-memory
mutation is rolled back, the existing workspace file is preserved, and the save returns `REJECTED` with an explicit
warning rather than reporting `SAVED`.

## Identity And Conflicts

`raw_record_id` is the stable evidence identity.

Saving an identical record with the same `raw_record_id` is idempotent. Saving different content under the same `raw_record_id` is rejected and the original stored evidence is preserved. DonnieCraftShell never silently overwrites conflicting evidence.

## Backup And Restore

Workspace backup exports use the same supported versioned envelope as local persistence:

```json
{
  "workspace_version": "dc-observation-workspace-v1",
  "storage_version": "dc-observation-workspace-storage-v1",
  "records": [],
  "decisions": []
}
```

The backup contains raw recorder records and separate review decisions only. Exporting or restoring a backup does not
accept evidence into probability counts, build empirical datasets, register datasets, select Advisor evidence, calculate
probabilities, change valuations, or affect EV readiness.

Restore modes:

- `MERGE`: imports new records into the current workspace. Identical existing records are idempotent. Conflicting content
  under an existing `raw_record_id` rejects the restore and preserves the current workspace.
- `REPLACE`: validates the entire supplied backup first, then replaces the live workspace. Invalid records, incompatible
  versions, duplicate IDs, or decisions that reference absent records reject the restore and preserve current evidence.

Restore is transactional. Validation happens before mutation; file-backed persistence failures roll back memory and keep
the previous workspace file. The API returns a restore summary with received/imported/already-present/conflicting/invalid
record counts, imported/invalid decision counts, warnings, mode, and resulting workspace counts.

Recommended operator workflow:

1. Export a workspace backup before moving machines, clearing `.dcs/`, or testing destructive replace.
2. Prefer `MERGE` when combining evidence from another local workspace.
3. Use `REPLACE` only when intentionally restoring a known-good full backup; the frontend asks for confirmation first.
4. After restore, review records again and export accepted observations through the normal curation/build/registry gates.

## Startup Recovery

On startup, malformed individual records or decisions are skipped with warnings while valid evidence still loads.

If `workspace_version` or `storage_version` is missing or incompatible, the file is skipped conservatively and is not rewritten during startup. The operator can inspect status through:

```text
GET /api/v1/observations/workspace
```

Back up the workspace file before manual edits or before moving evidence between machines.

## API

Local operator endpoints:

- `POST /api/v1/observations/workspace/records`
- `GET /api/v1/observations/workspace`
- `POST /api/v1/observations/workspace/reviews`
- `GET /api/v1/observations/workspace/accepted-export`
- `GET /api/v1/observations/workspace/backup`
- `POST /api/v1/observations/workspace/restore`

These endpoints are thin transport over the workspace boundary. They do not scrape, infer outcomes, estimate probabilities, or activate empirical evidence.
