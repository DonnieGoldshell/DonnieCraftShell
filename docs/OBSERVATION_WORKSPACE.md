# Observation Workspace

Task 18A adds a local durable workspace for the manual craft observation flow.

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

## Identity And Conflicts

`raw_record_id` is the stable evidence identity.

Saving an identical record with the same `raw_record_id` is idempotent. Saving different content under the same `raw_record_id` is rejected and the original stored evidence is preserved. DonnieCraftShell never silently overwrites conflicting evidence.

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

These endpoints are thin transport over the workspace boundary. They do not scrape, infer outcomes, estimate probabilities, or activate empirical evidence.
