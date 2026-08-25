# Advisor API

Task 13B exposes the framework-independent `CraftAdvisorOrchestrator` through FastAPI.

## Endpoint

```text
POST /api/v1/advisor/analyze
POST /api/v1/advisor/manual-valuation/preview
POST /api/v1/advisor/economy-quotes/workspace/quotes
```

The endpoints perform no external network calls. Advisor analysis uses configured local/offline repositories, request-supplied manual valuation evidence, and explicit local economy quote evidence where available for the request league.

## Browser Access / CORS

The local API is configured to allow the local Next.js frontend origin by default:

```text
http://localhost:3000
http://127.0.0.1:3000
```

Use `DCS_CORS_ALLOWED_ORIGINS` to configure a comma-separated allow-list for other environments. Keep the allow-list explicit; do not use `*` as the production default.

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
- `empirical_probability_dataset_version`

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

### Manual Valuation Preview

`POST /api/v1/advisor/manual-valuation/preview` lets the frontend validate and
preview manual comparable evidence before rerunning the full Advisor analysis.
The request includes:

- `subject_id`
- `subject_type`: `CURRENT_ITEM` or `HYPOTHETICAL_OUTCOME`
- optional `outcome_id`
- explicit `league`
- optional `as_of`
- manual valuation evidence with Decimal amount strings

The response returns the evidence-set identity, normalized comparable rows,
usable/unusable counts, duplicate listing IDs, readiness, listing-derived
estimate/range when available, confidence, liquidity, economy snapshot IDs, and
warnings. The preview uses the same manual provider and aggregation path as
Advisor analysis. It does not scrape Trade, fabricate prices, or accept a final
price override.

## Empirical Probability Evidence

`empirical_probability_dataset_version` selects an explicitly registered or
configured offline empirical probability dataset. It does not cause runtime
scraping, auto-discovery, or fallback selection of another dataset.

Production/default dependency assembly skips synthetic/test-only empirical
fixtures. Tests may inject synthetic datasets explicitly to prove transport and
readiness behavior.

When empirical evidence is absent, partial, incompatible with league/game or
dataset context, or disabled because it is synthetic, real action probabilities
remain `UNKNOWN` and the response includes probability missing requirements.

## Local Economy Quote Evidence

Task 22A adds local/operator economy quote workspace endpoints:

```text
POST   /api/v1/advisor/economy-quotes/workspace/quotes
PUT    /api/v1/advisor/economy-quotes/workspace/quotes/{evidence_id}
GET    /api/v1/advisor/economy-quotes/workspace/quotes
DELETE /api/v1/advisor/economy-quotes/workspace/quotes/{evidence_id}
DELETE /api/v1/advisor/economy-quotes/workspace/quotes
```

The workspace stores exact league/asset crafting-material quote evidence in Exalted economic units. Saving a quote does not submit valuation evidence, fabricate probability evidence, or re-run Advisor analysis. The next `POST /api/v1/advisor/analyze` request composes matching local quotes into a request-scoped economy repository. Non-matching leagues/assets remain unavailable, never zero.

See [LOCAL_ECONOMY_QUOTES.md](LOCAL_ECONOMY_QUOTES.md).

## Empirical Dataset Registry

Local/operator endpoints support the Task 17A lifecycle:

- `POST /api/v1/observations/empirical-datasets/register`
- `GET /api/v1/observations/empirical-datasets`

The register endpoint accepts one Task 15A-compatible empirical probability
dataset payload, such as a dataset returned by
`POST /api/v1/observations/build-empirical-datasets`. Registration alone does
not alter Advisor analysis. The Advisor request must explicitly name the
registered dataset ID in `empirical_probability_dataset_version`.

The browser workflow intentionally keeps this as a two-step operator action.
After a build/register succeeds, the UI surfaces the resulting dataset ID and
offers an explicit "use for next analysis" action. It does not automatically
select the dataset and does not rerun `/api/v1/advisor/analyze` until the
operator asks for a rerun. This preserves the API contract that empirical
evidence is consumed only when the request names the dataset.

## Response

The response includes:

- `analysis_id`
- status and context
- parsed item summary
- enrichment summary
- affix state
- action summaries
- probability summaries for each modeled action
- raw Advisor decision
- optional risk-adjusted decision
- missing requirements
- warnings and provenance

Partial analysis is HTTP 200. `NO_RECOMMENDATION` is also HTTP 200.

Each action probability summary includes completeness, total known probability
mass, outcome probabilities where available, evidence type, sample size,
uncertainty interval, evidence dataset version, and warnings. Decimal
probability values serialize as strings.

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
