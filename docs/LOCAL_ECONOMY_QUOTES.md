# Local Economy Quotes

Task 22A adds a local operator workflow for crafting-material price evidence that is missing from committed offline economy snapshots.

## Purpose

Local economy quote evidence lets an operator record a specific material price for a specific league and economy asset, then re-run Advisor analysis so craft material costs can use that explicit evidence.

This is not a live economy provider and does not scrape or poll any external source.

## Storage

The API stores local quotes in an ignored `.dcs/` workspace by default:

```text
.dcs/economy_quote_workspace.json
```

The storage envelope is versioned:

```json
{
  "workspace_version": "dc-economy-quote-workspace-v1",
  "storage_version": "dc-economy-quote-workspace-storage-v1",
  "records": []
}
```

Writes are atomic. A failed write rolls back in-memory state so the API does not report evidence that was not persisted.

Set `DCS_ECONOMY_QUOTE_WORKSPACE_PATH=disabled` or `:memory:` to use process-local memory only.

## Quote Record

Each record contains:

- `evidence_id`
- `league`
- `asset_id`
- `amount`
- `currency_asset_id`
- `observed_at`
- `source_type`
- optional `source_reference`
- optional `notes`
- `created_at`
- `updated_at`

For Task 22A, `amount` is recorded in Exalted economic units and `currency_asset_id` must be:

```text
dc:poe2:economy-asset:currency:exalted-orb
```

This avoids unsupported ad hoc conversion in the workspace layer. Future source adapters can add verified conversion paths without changing the evidence identity model.

## Scope And Matching

Local quotes are exact evidence only:

- A quote for one league is not reused in another league.
- A quote for one asset does not satisfy another asset.
- Saving a quote does not re-run analysis automatically.
- Saving a quote does not fabricate probabilities, outcome valuations, current item valuation, or recommendations.

When Advisor analysis is re-run, the API composes the committed offline economy snapshots with a request-scoped local quote snapshot for the request league.

## Freshness

Local quote freshness uses the existing Economy Engine freshness policy:

- `FRESH`: age <= 2 hours
- `AGING`: >2h and <=6h
- `STALE`: >6h
- `UNAVAILABLE`: no usable quote

Stale quotes keep their explicit freshness metadata. Missing or invalid quotes remain unavailable and never become zero.

The current `CraftMaterialCost` policy treats a stale quote with a valid normalized value as price-complete while carrying `freshness = STALE` on the cost line and aggregate material cost. This is intentional pre-existing Economy Engine behavior: freshness is visible to Advisor/risk policy, but stale evidence is not silently converted to missing or zero at the cost-calculation layer.

## API

```text
POST   /api/v1/advisor/economy-quotes/workspace/quotes
PUT    /api/v1/advisor/economy-quotes/workspace/quotes/{evidence_id}
GET    /api/v1/advisor/economy-quotes/workspace/quotes
DELETE /api/v1/advisor/economy-quotes/workspace/quotes/{evidence_id}
DELETE /api/v1/advisor/economy-quotes/workspace/quotes
```

List and clear support `league` and `asset_id` filters.

Conflicting content for an existing `evidence_id` is rejected; it is never silently overwritten. Updates may change quote amount, source, notes, or timestamps, but not the identity partition of league, asset, and currency.

## Frontend Workflow

The Evidence Readiness panel exposes missing crafting-material price targets. Choosing the economy workflow opens Advanced Evidence & Diagnostics, where the operator can:

1. Select a missing asset target.
2. Enter an Exalted-unit quote and provenance note.
3. Save the quote locally.
4. Re-run Advisor analysis manually.

The frontend does not calculate prices or recommendations.

## Future Live Integration

Future live providers such as poe.show/poe.ninja background ingestion or GGG Currency Exchange should remain behind EconomyProvider adapters and normalized `EconomySnapshot` records. Local quote evidence is a manual/operator source and should remain distinguishable from provider snapshots in provenance.
