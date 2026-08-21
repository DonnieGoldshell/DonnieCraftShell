# Manual Valuation Evidence Workspace

Task 19B adds local persistence for operator-entered manual comparable listing evidence. The workspace stores evidence only; it does not create a valuation result, mark valuation readiness as `READY`, or submit anything to Advisor automatically.

## Subject Identity

Evidence is partitioned by canonical valuation subject:

- Current parsed/enriched item: `current`
- Hypothetical craft outcome: `outcome:{outcome_id}`

The API and repository reject mismatched subject identity. Outcome evidence must not appear in the current-item workspace, and one outcome's evidence must not leak into another outcome.

## Stored Fields

Each record preserves:

- `evidence_id`
- `subject_id`
- `subject_type`
- `outcome_id` when subject type is `HYPOTHETICAL_OUTCOME`
- `league`
- comparable `strategy`
- listing `amount`
- `currency_asset_id`
- optional `external_listing_id`
- optional `observed_at`
- optional `item_summary`
- optional `notes`
- `created_at`
- `updated_at`

Listing prices remain manual listing observations. They are not realized sale prices.

## Persistence

The default API storage path is `.dcs/manual_valuation_workspace.json`, configured by `DCS_MANUAL_VALUATION_WORKSPACE_PATH`. Set the variable to `disabled`, `memory`, `:memory:`, or an empty string to use an in-memory repository.

The file format is a versioned JSON envelope:

- `storage_version`
- `workspace_version`
- `exported_at`
- `records`

Incompatible or malformed persisted records are skipped/rejected with warnings rather than loaded into the active workspace.

File-backed writes are atomic and transactional at the repository boundary: the repository writes a temporary file and replaces the workspace file only after serialization succeeds. If persistence fails, in-memory state rolls back to the last persisted state.

## Save Semantics

Saving an identical record is idempotent. Saving the same `evidence_id` with different material content is rejected as a conflict. Explicit updates use the update endpoint and preserve the record's original `created_at`.

## API

Manual valuation workspace endpoints:

- `POST /api/v1/advisor/manual-valuation/workspace/evidence`
- `PUT /api/v1/advisor/manual-valuation/workspace/evidence/{evidence_id}`
- `GET /api/v1/advisor/manual-valuation/workspace/evidence?subject_id=...`
- `DELETE /api/v1/advisor/manual-valuation/workspace/evidence/{evidence_id}`
- `DELETE /api/v1/advisor/manual-valuation/workspace/subject?subject_id=...`

These endpoints never read arbitrary filesystem paths and never call external trade or economy sources.

## Frontend Workflow

The Manual Valuation panel can load, save, update, remove, and clear persisted evidence for the currently selected subject. Evidence is submitted to Advisor only when the user runs analysis. Persisted evidence alone is intentionally not enough to produce valuation readiness or Advisor ranking.
