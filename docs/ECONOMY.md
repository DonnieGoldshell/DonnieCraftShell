# Economy Engine

The Economy Engine provides league-scoped, time-aware market prices for Craft Advisor, Profit Finder, crafting cost calculation, and historical analysis. It must not fetch prices per user request, fabricate missing values, or hide stale data.

## Architecture

```text
EconomyProvider
  GggCurrencyExchangeProvider
  PoeNinjaEconomyProvider
        -> Raw Economy Observations
        -> EconomyNormalizer
        -> EconomySnapshot / EconomyQuote / ExchangeRate
        -> EconomyRepository
        -> Craft Advisor / Profit Finder
```

Provider payloads stay behind adapters. Domain logic consumes normalized records only.

## Core Models

- `EconomyAsset`: internal asset ID such as `dc:poe2:currency:divine-orb`, display name, category, game, aliases/source IDs, and provenance.
- `EconomySnapshot`: source, game, league ID/name, observed/reference timestamp, retrieved_at, snapshot ID, freshness state, and provenance.
- `EconomyQuote`: asset ID, normalized Exalted value, native/source price, source, league, observed_at, retrieved_at, volume, confidence, freshness, and snapshot ID.
- `ExchangeRate`: explicit pair such as `divine -> exalted`, rate, volume, observed_at, source, confidence, and snapshot ID.
- `EconomyProviderRun`: ingestion status, cache metadata, rate-limit state, failures, and next cursor where relevant.

Persisted entities should map explicitly to domain records: `economy_assets`, `economy_asset_aliases`, `economy_snapshots`, `economy_quotes`, `exchange_rates`, and `economy_provider_runs`.

## Normalized Unit

Internal value remains:

```text
1 Exalted Orb = 1 economic unit
```

All arithmetic must use `Decimal`. Missing price is `None`, never zero.

If a source quotes values in Divine, first obtain an explicit Divine to Exalted rate. With poe.show current Currency data, `core.primary = divine` and `core.rates.exalted = 338.2` means:

```text
1 Divine = 338.2 Exalted
normalized_exalted_value = primaryValue_in_divine * 338.2
```

Example from live research on league `Runes of Aldur`: Divine Orb has `primaryValue = 1`; therefore its normalized value is `338.2` Exalted units at that snapshot. Perfect Exalted Orb has `primaryValue = 2.63`, so its conceptual normalized value is `2.63 * 338.2 = 889.466` Exalted units. These are research examples, not committed price fixtures.

## Freshness

Freshness is DonnieCraftShell policy, not source truth. Make thresholds configurable:

- `FRESH`: observed/retrieved age <= 2 hours.
- `AGING`: > 2 hours and <= 6 hours.
- `STALE`: > 6 hours.
- `UNAVAILABLE`: no usable quote.

Recommendation confidence should later degrade when required economy data is aging or stale.

## Repository Access

Design repository methods:

- `get_current_quote(league_id, asset_id, source_policy)`
- `get_quote_at(league_id, asset_id, at)`
- `get_snapshot(snapshot_id)`
- `get_history(league_id, asset_id, range)`
- `get_exchange_rate(league_id, base_asset_id, quote_asset_id, at=None)`

Historical snapshots must be retained so craft sessions and recommendations remain reproducible.

Task 6B implements a framework-independent in-memory `EconomyRepository` and an offline poe.show Currency normalizer. See [ECONOMY_IMPORT.md](ECONOMY_IMPORT.md) for the captured fixture, asset mapping, normalization command, and exact Task 6B values.

Task 6C extends the same path to Ritual/Omens and Essences, plus a small craft-material cost abstraction. See [ECONOMY_DATASET_STATUS.md](ECONOMY_DATASET_STATUS.md).

Task 7C connects crafting actions to economy costs through `CraftActionCostService`. Crafting mechanics provide required material IDs and quantities; the Economy Engine prices those materials using `CraftMaterialCost`.

Task 22A adds a local operator quote workspace for missing crafting-material prices. These records are exact league/asset evidence in Exalted economic units and are composed into a request-scoped local `EconomySnapshot` only when Advisor analysis is re-run. Local quotes preserve provenance and freshness, but they do not scrape providers, infer related asset prices, cross-use leagues, or alter committed normalized economy fixtures. See [LOCAL_ECONOMY_QUOTES.md](LOCAL_ECONOMY_QUOTES.md).

Issue 77 adds optional backend-only live poe.show economy ingestion for
league-scoped Advisor analysis. When enabled by API configuration, the backend
fetches bounded poe.show PoE2 `Currency`, `Ritual`, and `Essences` overview
responses, preserves the raw provider response in a local `.dcs/` cache with
ETag/source URI/retrieval metadata, normalizes the payload through the same
`EconomySnapshot` contracts, and composes those snapshots into the
request-scoped `EconomyRepository`. The frontend never calls poe.show directly.

Live ingestion has two separate time policies:

- Refresh interval: configured backend cache cadence. The MVP default is 1 hour,
  aligned with poe.show's roughly hourly source refresh. A cached response still
  inside this interval is normalized directly without a network request. Once
  due, the provider uses conditional ETag requests and reuses cached payloads on
  `304 Not Modified`.
- Freshness: domain evidence quality on the resulting `EconomyQuote` /
  `EconomySnapshot`. A cached snapshot can be due for refresh yet still produce
  explicit `FRESH`, `AGING`, or `STALE` evidence according to DonnieCraftShell's
  economy freshness policy.

Live economy quote precedence is:

1. Fresh/current explicit local operator quote evidence for the exact league and
   asset.
2. Automatic live poe.show quote for the exact requested league.
3. No quote; cost remains incomplete.

Old local placeholder quotes do not silently override newer live quotes. Provider
failures may use a valid cached snapshot with explicit freshness/warnings; they
must not fabricate prices. All conversion continues to come from the current
provider snapshot rate data, not constants.

Advisor API responses expose an explicit economy evidence summary. Clients must
use that summary to distinguish `OFFLINE_BUNDLED`, `LIVE_FETCHED`,
`LIVE_CACHED`, `LIVE_CACHE_FALLBACK`, `LOCAL_OVERRIDE`, and missing/unavailable
states. They must not infer live market evidence from `EconomyQuote.source ==
"poe.show"` because the committed offline snapshots also originate from
poe.show.

poe.show asset identity is resolved explicitly. The normalizer first maps the
exchange-overview `lines[].id`; if that provider row ID is not a known
DonnieCraftShell alias, it may use the matching `core.items[].detailsId` metadata
as a source-backed fallback. Display names alone are not treated as stable asset
identity. This preserves the separation between poe.show source IDs and
DonnieCraftShell canonical economy asset IDs while allowing provider rows such as
Orb of Annulment to clear crafting-cost blockers when their metadata is present.

Applicability and price completeness are independent:

- `APPLICABLE` action + complete cost: action can be performed and all required material quotes are available.
- `APPLICABLE` action + incomplete cost: action may be legal, but at least one material quote is missing.
- `NOT_APPLICABLE` action + complete cost: price exists, but mechanics block the action.
- `UNKNOWN` action + complete cost: materials are priced, but legality is unresolved.

Missing quote remains unavailable and must never be treated as zero.

## Source Selection

Do not blindly average sources. Keep observations separate, then choose according to policy:

1. Prefer configured source precedence for the use case.
2. Retain all source observations with provenance.
3. If sources disagree beyond a configurable tolerance, surface a warning and lower confidence.
4. If the preferred source is unavailable, use fallback only with explicit source/freshness metadata.

MVP 0.1 should use poe.show/poe.ninja as the primary current economy provider. GGG Currency Exchange should be secondary/future until confidential-client credentials and ingestion are configured.

## Failure Behavior

Provider failures must be explicit: unavailable, unauthenticated, rate limited, malformed response, stale last-known snapshot, or missing asset mapping. Prefer last-known stale data with warnings over fabricated prices, but return no economy answer when the required quote is missing or too stale for the decision policy.
