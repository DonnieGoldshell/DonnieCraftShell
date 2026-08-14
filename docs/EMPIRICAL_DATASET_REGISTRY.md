# Empirical Dataset Registry

Task 17A adds a local, framework-independent registry boundary for empirical probability datasets.
Task 17B adds optional local JSON persistence for the same registry.

The registry exists so an operator can move through this lifecycle without automatically changing Advisor behavior:

```text
record
-> review
-> build dataset
-> register dataset
-> explicitly select dataset in Advisor request
-> existing empirical probability readiness evaluation
```

Registration does not make evidence complete, official, or mechanically true. It only makes a Task 15A-compatible empirical probability dataset available by `dataset_id` in the running application.

## Registry Rules

- Registered datasets retain their original `dataset_id`, context, source timestamps, observations, warnings, synthetic flag, and provenance.
- Duplicate registration with identical content is idempotent.
- Reusing the same `dataset_id` with different content is rejected.
- Malformed payloads are rejected and never enter provider results.
- Datasets are never auto-selected merely because they are built or registered.
- Unknown requested dataset IDs produce explicit UNKNOWN probability warnings; DonnieCraftShell does not fall back to another empirical dataset.
- Context-incompatible datasets remain UNKNOWN through the existing empirical provider compatibility gates.
- Synthetic datasets remain marked as synthetic and require explicit test-only provider configuration before they can produce empirical estimates.

The current API registry is local-operator storage. It may run in memory only,
or persist to a local JSON file for durability across API restarts. It is
intentionally not a production database.

## Local Persistence

The default API configuration stores registered datasets in:

```text
.dcs/empirical_probability_registry.json
```

`.dcs/` is ignored by git. Operators may override the path with:

```text
DCS_EMPIRICAL_REGISTRY_PATH=/path/to/empirical_probability_registry.json
```

Set `DCS_EMPIRICAL_REGISTRY_PATH=disabled`, `memory`, `:memory:`, or an empty
value to run with in-memory registry storage only.

The persisted file is a transparent JSON envelope:

```json
{
  "registry_version": "dc-empirical-dataset-registry-v1",
  "storage_version": "dc-empirical-dataset-registry-storage-v1",
  "datasets": [
    {
      "dataset_id": "...",
      "action_id": "...",
      "source_outcome_set_id": "...",
      "game": "Path of Exile 2",
      "league": "...",
      "retrieved_at": "...",
      "observations": []
    }
  ]
}
```

Each `datasets[]` entry is the same Task 15A-compatible empirical probability
dataset payload accepted by the register endpoint. DonnieCraftShell persists
only successfully registered datasets. Rejected or malformed payloads are never
written.

Writes use deterministic JSON ordering and same-directory temporary-file
replacement before replacing the registry file. This reduces the chance that an
interrupted write corrupts the whole registry.

## Startup Recovery

On startup, the API loads configured static empirical dataset paths and the
local registry file when persistence is enabled. Malformed or corrupt persisted
entries are skipped with explicit warnings while valid entries continue loading.
The registry envelope is versioned separately from each dataset payload. If
`registry_version` or `storage_version` is missing or differs from the current
DonnieCraftShell constants, all persisted entries in that file are skipped
conservatively and the file is not rewritten during startup.

If the registry file itself cannot be read, persisted entries are skipped and
the API still starts with warnings. The operator can inspect registry status
through `GET /api/v1/observations/empirical-datasets`.

Back up the registry file before manual edits or before moving evidence between
machines. The file is local evidence storage, not an authoritative game-data
source.

## API

`POST /api/v1/observations/empirical-datasets/register`

Registers one raw Task 15A-compatible empirical probability dataset payload, usually copied directly from `POST /api/v1/observations/build-empirical-datasets`.

`GET /api/v1/observations/empirical-datasets`

Lists loaded dataset summaries so the operator can copy a dataset ID into `POST /api/v1/advisor/analyze`.

The list and register responses include persistence status:

- storage mode: `FILE` or `IN_MEMORY`
- whether persistence is enabled
- loaded dataset count
- skipped corrupt/malformed persisted entry count
- load warnings

`POST /api/v1/advisor/analyze`

The optional `empirical_probability_dataset_version` field explicitly selects one registered dataset for probability evaluation. If omitted, real action probabilities remain UNKNOWN as before.

## Frontend MVP

The Observation Review panel can build empirical datasets, register the first built dataset in the running API, and list registered evidence IDs. The Advisor form has a separate optional empirical evidence dataset field. The operator must explicitly provide/select the dataset ID before Advisor analysis uses it.

This is evidence selection, not proof of mechanic truth.
