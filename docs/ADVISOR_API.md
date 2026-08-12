# Advisor API

Task 13B exposes the framework-independent `CraftAdvisorOrchestrator` through FastAPI.

## Endpoint

```text
POST /api/v1/advisor/analyze
```

The endpoint performs no external network calls. It uses configured local/offline repositories plus request-supplied manual valuation evidence.

## Request

Required fields:

```json
{
  "clipboard_text": "<Path of Exile 2 clipboard text>",
  "league": "Runes of Aldur",
  "game_data_dataset_version": "poe2db-unknown-version-2026-08-12-task8c-fullx1",
  "crafting_dataset_version": "crafting-actions-poe2-quiver-2026-08-12-research",
  "affix_capacity_dataset_version": "affix-capacity-poe2-2026-08-12-research"
}
```

Optional fields:

- `as_of`
- `game_context`
- `bankroll`
- `risk_profile`
- `current_valuation_evidence`
- `outcome_valuation_evidence`

Money uses Decimal strings:

```json
{
  "bankroll": {
    "amount": "1000",
    "unit": "EXALTED_ECONOMIC_UNIT"
  }
}
```

## Manual Valuation Evidence

Manual valuation input is listing-observation evidence, not a final price override.

```json
{
  "current_valuation_evidence": {
    "strategy": "STRICT",
    "observations": [
      {
        "amount": "5",
        "currency_asset_id": "dc:poe2:economy-asset:currency:divine-orb",
        "external_listing_id": "optional-listing-id",
        "observed_at": "2026-08-11T13:30:00+00:00",
        "item_summary": "manual comparable summary"
      }
    ]
  }
}
```

The API maps these observations through `ManualTradeProvider`, `EconomyRepository`, and `ValuationAggregator`. Missing currency conversion remains unavailable, never zero.

Outcome valuation evidence is keyed by deterministic `outcome_id`.

## Response

The response includes:

- `analysis_id`
- status and context
- parsed item summary
- enrichment summary
- affix state
- action summaries
- raw Advisor decision
- optional risk-adjusted decision
- missing requirements
- warnings and provenance

Partial analysis is HTTP 200. `NO_RECOMMENDATION` is also HTTP 200.

## Error Behavior

- Empty `clipboard_text`: HTTP 400 with `VALIDATION_ERROR`.
- Pydantic shape errors: FastAPI HTTP 422.
- Parsed but unsupported MVP item: HTTP 200 with `status = UNSUPPORTED_ITEM`.
- Parser failure for non-item text: structured analysis result with `PARSE_FAILED`.
- Unexpected dependency/configuration failure: 5xx.

## OpenAPI

OpenAPI is available at:

```text
/openapi.json
/docs
```

Frontend TypeScript contracts should later be generated from OpenAPI rather than manually duplicated.
