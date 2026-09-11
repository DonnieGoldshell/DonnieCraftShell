# Comparable Listing Acquisition

Issue 93 research date: `2026-09-10`.

## Current Verdict

DonnieCraftShell does not have a compliant automatic machine-readable source for
Path of Exile 2 rare-item comparable listings today.

The supported production path remains:

```text
ComparableQuery
-> ManualTradeProvider workflow
-> operator-entered real listing observations
-> ComparableEvidenceSet
-> ValuationAggregator / ComparableValuationModel
```

No live rare-item listing provider is enabled in production.

## Official GGG References

Sources reviewed:

- [Path of Exile Developer Docs](https://www.pathofexile.com/developer/docs)
- [Path of Exile API Reference](https://www.pathofexile.com/developer/docs/reference)
- [GGG forum: Do not share POESESSID values](https://www.pathofexile.com/forum/view-thread/3328601)

Relevant findings:

- GGG says supported resources are the API Reference or Data Exports.
- Requests for internal website APIs or in-game resources outside the
  documentation are outside the supported API boundary.
- The current API Reference says PoE2 API resources are limited.
- `Public Stashes` are documented as PoE1-only.
- `Currency Exchange` is aggregate currency exchange history; it is not
  rare-item listing search.
- GGG warns users not to share `POESESSID` and points supported access toward
  OAuth for officially documented API endpoints.

Conclusion: DonnieCraftShell must not call undocumented `/api/trade/*` website
internals, scrape Trade HTML, request or store `POESESSID`, or fabricate listing
observations.

## Implemented Foundation

The shared valuation contracts now include a narrow acquisition boundary:

- `ComparableListingAcquisitionRequest`
- `ComparableListingAcquisitionResult`
- `ComparableListingProviderCapabilities`
- `ListingAcquisitionStatus`
- `ListingAcquisitionFailureReason`
- `UnsupportedOfficialTradeListingProvider`

The request is derived from an existing `ComparableQuery` and a current or
hypothetical `ValuationSubject`. Request identity is deterministic for the same
provider, query, subject, league, and strategy.

`UnsupportedOfficialTradeListingProvider` is a fail-closed placeholder for a
future official listing provider. It returns:

- `status = UNSUPPORTED`
- `failure_reason = UNSUPPORTED_OFFICIAL_API`
- zero listings
- official-source provenance
- warnings that manual comparable evidence remains the compliant production path

This is intentionally not a live provider.

## Provider Capability Rules

A comparable-listing provider capability record rejects:

- `uses_poesessid = true`
- `uses_undocumented_trade_endpoint = true`
- `uses_html_scraping = true`

This makes the compliance boundary executable. Future provider work must prove a
documented, permitted machine-readable listing source before it can return real
listing observations.

## Evidence Conversion

When a future compliant provider returns listings, `evidence_set_from_listing_acquisition()`
can convert the acquisition result into an ordinary `ComparableEvidenceSet`.

Rules:

- provider failure or unsupported status returns no listing observations;
- listing league must match the acquisition request league;
- duplicate external listing IDs are deterministically deduplicated for evidence
  counting while retaining a warning;
- missing or unnormalized prices remain unavailable, not zero;
- acquired evidence never overrides manual evidence.

`merge_manual_and_acquired_evidence_sets()` documents the current precedence:
manual comparable evidence remains explicit and is evaluated before any future
acquired provider evidence.

## Third-Party Sources

The already-used poe.show / poe.ninja integrations provide economy/currency
overview data, not rare-item listing search. They are not a source for automatic
rare-item comparables.

Open-source price-checking tools remain useful architecture references, but they
do not by themselves establish that DonnieCraftShell may automate the same access
pattern server-side.

## What Would Unblock Automatic Acquisition

One of these would be needed before implementing live automatic comparable
listing acquisition:

- GGG documents and permits a PoE2 rare-item Trade search/listing API, ideally
  OAuth-backed and rate-limited with stable listing identities.
- A third-party provider offers real PoE2 item listing/search evidence under
  terms suitable for DonnieCraftShell, with provenance, timestamps, league
  scoping, and no dependence on undocumented GGG endpoints or session cookies.

Until then, automatic acquisition remains `UNSUPPORTED` and Advisor analysis
stays partial when manual comparable evidence is absent or insufficient.

## Bramble Spike Pilot

Issue 93 does not change the Bramble Spike pilot economics. No new listing
source is introduced, no relevance thresholds are weakened, and no outcome value
is inferred from sparse broad-bracket evidence.

The expected current result remains:

```text
Bramble Spike ordinary Annulment outcome valuations ready: 0 / 6
Probability: UNKNOWN
EV: unavailable
```
