# Craft Investment Ledger

Issue 69 adds the first accounting foundation for the current item. The ledger
tracks operator-entered realized capital only:

- base acquisition cost;
- prior crafting spend already incurred;
- optional action/source notes;
- normalized Exalted economic value when conversion is known.

It does not reconstruct historical spend from modifiers, action candidates, or
item state. Prospective craft costs are not included until the operator records
them as realized spend.

## Cost Basis

`CraftInvestmentLedger` contains immutable `CraftInvestmentEntry` records. Each
entry stores a stable entry ID, ledger ID, subject ID, kind, description,
original amount, currency asset ID, optional normalized `EconomicValue`,
optional economy snapshot reference, timestamp, notes, provenance, and warnings.

`CraftInvestmentCalculator.cost_basis()` computes:

- base acquisition total;
- crafting spend total;
- known invested total from normalized entries;
- complete total invested only when every entry has a normalized value.

Missing or unconvertible entries make the cost basis `INCOMPLETE`. They are not
treated as zero.

A current-item ledger also requires an explicit `BASE_ACQUISITION` entry before
the cost basis can be `COMPLETE`. An empty ledger, or a ledger containing only
crafting-spend entries, is incomplete even if all present entries are
normalized. If the operator truly acquired the item for free, they can record an
explicit base-acquisition entry with amount `0` and normalized value `0`; that
intentional zero is complete.

## Current Profit Position

`CurrentProfitPosition` compares the complete cost basis to the explicit
headline market valuation contract from manual valuation preview.

Statuses:

- `INCOMPLETE_COST_BASIS`: at least one ledger entry has no normalized value.
- `INSUFFICIENT_MARKET_EVIDENCE`: market valuation does not support a point or
  supported range.
- `SUPPORTED_PROFIT_RANGE_ONLY`: market valuation is range-only and a supported
  profit range can be shown.
- `CURRENT_PROFIT_ESTIMATE_AVAILABLE`: market valuation has an evidence-backed
  point estimate and total invested capital is complete.

Point unrealized profit is calculated only when
`market_valuation.status == ESTIMATED_MARKET_VALUE`:

```text
unrealized_profit = estimated_market_value - total_invested
roi = unrealized_profit / total_invested
```

ROI remains unavailable when total invested is zero.

For `SUPPORTED_RANGE_ONLY`, no midpoint, median, lower bound, or upper bound is
promoted to a point estimate. The system may expose:

```text
supported_profit_low = supported_market_low - total_invested
supported_profit_high = supported_market_high - total_invested
```

A positive upper bound alone is not profit certainty.

For `INSUFFICIENT_MARKET_EVIDENCE`, no current profit is fabricated. The legacy
manual evidence median remains diagnostics only and cannot bypass
`market_valuation.status`.

## Local Workspace

The API can persist local operator ledger entries under
`.dcs/craft_investment_workspace.json` by default. Set
`DCS_CRAFT_INVESTMENT_WORKSPACE_PATH=disabled` to use in-memory mode.

Workspace endpoints:

- `POST /api/v1/advisor/craft-investment/preview`
- `POST /api/v1/advisor/craft-investment/workspace/entries`
- `GET /api/v1/advisor/craft-investment/workspace/entries`
- `PUT /api/v1/advisor/craft-investment/workspace/entries/{entry_id}`
- `DELETE /api/v1/advisor/craft-investment/workspace/entries/{entry_id}`
- `DELETE /api/v1/advisor/craft-investment/workspace/ledger`

This workflow is offline and manual. It does not scrape market data, infer
prices, execute crafts, or recommend SELL/CONTINUE/STOP.

## Future Boundary

Future profitability and stop/continue logic should consume this ledger as the
source of invested capital. Future craft economics remain separate from current
cost basis until a new realized ledger entry is recorded.
