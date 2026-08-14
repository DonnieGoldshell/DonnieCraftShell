# Empirical Dataset Registry

Task 17A adds a local, framework-independent registry boundary for empirical probability datasets.

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

The current API registry is in-memory/local-operator storage. It is intentionally not a persistent production database.

## API

`POST /api/v1/observations/empirical-datasets/register`

Registers one raw Task 15A-compatible empirical probability dataset payload, usually copied directly from `POST /api/v1/observations/build-empirical-datasets`.

`GET /api/v1/observations/empirical-datasets`

Lists loaded dataset summaries so the operator can copy a dataset ID into `POST /api/v1/advisor/analyze`.

`POST /api/v1/advisor/analyze`

The optional `empirical_probability_dataset_version` field explicitly selects one registered dataset for probability evaluation. If omitted, real action probabilities remain UNKNOWN as before.

## Frontend MVP

The Observation Review panel can build empirical datasets, register the first built dataset in the running API, and list registered evidence IDs. The Advisor form has a separate optional empirical evidence dataset field. The operator must explicitly provide/select the dataset ID before Advisor analysis uses it.

This is evidence selection, not proof of mechanic truth.
