# Manual Trade Workflow

Task 10B introduces `ManualTradeProvider` as the MVP-safe valuation evidence workflow. It is intentional design, not an undocumented Trade API workaround.

## Why Manual First

Official developer documentation does not provide a documented PoE2 rare-item Trade search/listing API for third-party valuation. DonnieCraftShell therefore must not automate undocumented Trade endpoint access.

Manual workflow keeps the user in control:

```text
ComparableQuery
-> human-readable search instructions
-> user opens official Trade site
-> user records listing observations
-> EconomyRepository normalizes currencies where possible
-> ComparableEvidenceSet readiness
-> ValuationAggregator
-> LISTING_DERIVED ValuationResult when evidence is sufficient
```

## Provider Capabilities

`ManualTradeProvider` reports:

- `supports_automatic_search = false`
- `supports_manual_observations = true`
- `supports_trade_url_generation = false`
- `supports_completed_sales = false`

No network calls are made.

## Manual Observations

A manual observation preserves:

- original entered amount,
- currency EconomyAsset ID,
- league,
- observed timestamp,
- optional listing ID,
- item summary,
- optional comparable Advanced Copy text and parsed comparable item state,
- provenance/warnings.

Examples such as `5 Divine` or `2400 Exalted` can be normalized only when EconomyRepository has a usable quote or identity conversion. Invalid or unconvertible currency remains unavailable, not zero.

## User-Facing Evidence Preview

Task 19A adds the first operator-facing workflow in the web app. After running
Advisor analysis, the user can enter comparable listing rows for either:

- the current item, or
- one deterministic hypothetical `outcome_id`.

Rows can be added, edited, removed, previewed, and then included in a later
`POST /api/v1/advisor/analyze` request. Current-item evidence and outcome
evidence remain separate subjects. Outcome evidence is keyed by stable
`outcome_id`; it must not be matched by display text or leak into current-item
valuation.

The preview call uses:

```text
POST /api/v1/advisor/manual-valuation/preview
```

It maps the manual rows through the existing `ManualTradeProvider`,
`EconomyRepository`, `ComparableEvidenceSet`, and `ValuationAggregator`. The
response shows normalized values when conversion exists, evidence readiness,
listing-derived median/range when available, confidence, liquidity, warnings,
an optional Comparable Valuation Model v1 anchor bracket, and the
subject/outcome identity. It performs no Trade requests and does not accept an
arbitrary final valuation override.

## Evidence Limits

Comparable evidence is not valuation. Listing price is not realized sale price.

Manual observations should include warnings when synthetic/test-only, stale, duplicated, unconvertible, or otherwise questionable. Task 10C aggregation may produce a listing-derived estimate from usable normalized manual observations, but it still does not infer completed-sale value or expected sale price.

Unconvertible observations remain in the evidence set and reduce readiness; they are never treated as zero.

Price-only observations remain supported for backwards compatibility. They are useful market notes, but they are not structurally verified comparables. Operators should paste the comparable item's Advanced Copy text when available so DonnieCraftShell can parse and retain item class, base, item level, affixes, special states, and other parser-supported item semantics beside the asking price.

When previewing current-item manual valuation evidence, the web client sends
the current item clipboard text alongside structured comparable observations.
The API can then return a structural comparable relevance assessment showing
base similarities, exact modifier matches, tier differences, origin
differences, missing modifiers, and extra modifiers. Relevance is explanatory
only in this workflow. It does not change the listing-derived aggregation,
create market-value weights, or make price-only evidence structurally verified.

The same preview may also return modifier quality delta evidence. This is a
directional comparison for corresponding parsed modifiers only: for example,
current T1 cold damage versus comparable T3 cold damage can be reported as
`CURRENT_BETTER`, while current T3 critical chance versus comparable T1
critical chance can be reported as `COMPARABLE_BETTER`. Origin differences
such as `NATURAL` versus `FRACTURED` remain visible but do not imply a price
premium. Quality delta is not valuation, weighting, Advisor ranking, or EV
input.

When both relevance and quality delta are available, preview also runs
`ComparableValuationModel` over the manual evidence. The model classifies each
structured comparable as a lower, upper, equivalent, or uninterpreted anchor
using the modifier quality delta. It then emits a conservative listing-derived
bracket only when enough structured anchors exist on both sides of the current
item. The model does not multiply price by relevance, infer a sale price, or
promote scenario/Advisor readiness.

Issue 65 adds market-inference diagnostics to the same preview. Every
structured comparable receives a usefulness band and score derived from
structural relevance, quality similarity, freshness, and observable differences
such as base type, special states, origins, and unmatched modifiers. Several
close high-usefulness comparables may support an `INFERRED_MARKET_BAND`; distant
lower/upper anchors remain `BROAD_BRACKET_ONLY` and must not be displayed as a
high-confidence midpoint market estimate.

## Local Evidence Workspace

Manual comparable observations can be persisted locally through the Task 19B manual valuation workspace. The workspace is backup-friendly JSON under `.dcs/` by default, partitioned by canonical subject identity, and deliberately separate from Advisor submission. Loading persisted evidence into the Manual Valuation panel does not submit it to Advisor until the operator explicitly runs analysis. Details: [MANUAL_VALUATION_WORKSPACE.md](MANUAL_VALUATION_WORKSPACE.md).

## Outcome-Valuation Blockers

Task 25 makes outcome valuation evidence operational from the First Playable UI. `OUTCOME_VALUATION_EVIDENCE_REQUIRED` readiness targets are authoritative: the UI opens the Manual Valuation panel for the exact blocked action/outcome ID supplied by the backend, not for a guessed modifier or display name.

The workflow remains explicit:

```text
blocked outcome target
-> add manual comparable rows for that outcome
-> preview through backend valuation aggregation
-> save to the local manual valuation workspace
-> explicitly re-run Advisor analysis with the selected outcome evidence
```

Saving workspace evidence does not activate it, rerun analysis, or copy it to any other outcome. On rerun, only compatible submitted outcome evidence can reduce the backend-reported missing outcome list; partial coverage remains partial.
