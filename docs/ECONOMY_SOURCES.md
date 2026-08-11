# Economy Sources

This document records Task 6A economy-source research. Source behavior may change; retain provenance and verification timestamps with imported data.

## GGG Currency Exchange API

Source type: official.

Use for:

- official Currency Exchange historical evidence;
- hourly market-pair digests;
- pair volume and ratio validation;
- future source comparison and historical replay.

Verified behavior:

- Endpoint: `GET /currency-exchange[/<realm>][/<id>]`
- PoE2 realm: `poe2`
- Required service scope: `service:cxapi`
- Requires confidential-client credentials using client credentials grant.
- Data is historical hourly digest data, not the current in-progress hour.
- Response includes `next_change_id`, `league`, `market_id`, `volume_traded`, `lowest_stock`, `highest_stock`, `lowest_ratio`, and `highest_ratio`.
- Old history may eventually be removed.
- Dynamic API rate limits must be respected.

GGG provider must be disabled when credentials are absent. Credentials are backend-only and must never be committed or sent to the frontend.

## poe.show / poe.ninja Economy API

Source type: community, public economy API.

Use for MVP current market convenience:

- current PoE2 exchange overview;
- crafting material categories;
- sparkline/trend signal where useful;
- fallback/current-market layer before GGG service access exists.

Verified public endpoints:

```text
GET /poe2/api/economy/leagues
GET /poe2/api/economy/exchange/current/overview?league={league}&type={type}
```

Documented PoE2 exchange categories:

- `Currency`
- `Fragments`
- `Abyss`
- `UncutGems`
- `LineageSupportGems`
- `Essences`
- `SoulCores`
- `Idols`
- `Runes`
- `Ritual` for Omens
- `Expedition`
- `Delirium` for Liquid Emotions
- `Breach` for Catalysts
- `Verisium`

Live Task 6A research confirmed all categories returned data for league `Runes of Aldur`. The Currency response used `core.primary = divine` and `core.secondary = chaos`; `core.rates.exalted = 338.2` and `core.rates.chaos = 8.15` in the sampled response. Currency also included `perfect-exalted-orb`.

Response concepts:

- `lines[].id`: stable identifier within the overview.
- `lines[].primaryValue`: price in `core.primary`.
- `lines[].volumePrimaryValue`: traded volume in primary reference value.
- `lines[].maxVolumeCurrency`: highest-volume paired currency.
- `lines[].maxVolumeRate`: rate against that paired currency.
- `lines[].sparkline`: recent trend samples.
- `core.primary`: primary reference currency for line prices.
- `core.secondary`: secondary reference currency for cross-rates.
- `core.rates`: map from currency ID to rate against the primary reference currency.
- `core.items`: metadata for referenced currencies.

Usage rules:

- Requests must go through DonnieCraftShell backend.
- Honor HTTP cache/ETag headers.
- Use a descriptive User-Agent.
- Do not poll per user or faster than useful refresh cadence.
- Treat API stability as best-effort, not guaranteed.

## Source Policy

MVP source recommendation:

- Primary: poe.show/poe.ninja for current PoE2 economy overview.
- Future/secondary: GGG Currency Exchange for official hourly pair history once credentials exist.

Do not average conflicting values. Retain both observations, select by configured precedence, and surface discrepancy when deviation exceeds tolerance.

## Open Questions

- Exact GGG ratio semantics must be validated with real authenticated responses before normalization.
- How stable poe.show IDs remain across leagues and site revisions.
- Which crafting materials are essential for Quiver MVP cost calculations.
- Appropriate confidence thresholds for sparse volume categories.
- How much stale data is acceptable for Craft Advisor decisions.
