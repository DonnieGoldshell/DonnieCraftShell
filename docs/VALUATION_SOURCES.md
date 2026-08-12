# Valuation Sources

Task 10A research date: `2026-08-12`.

## Source Policy

Rare-item valuation must use permitted and reproducible evidence. Do not reverse-engineer undocumented endpoints, scrape trade results in production, or present listings as confirmed sale prices.

## Official GGG Developer Docs

Source: [Path of Exile Developer Docs](https://www.pathofexile.com/developer/docs/reference)

Findings:

- Official API resources include account/profile, leagues, characters, stashes for account scopes, item filters, public stash for PoE1, and Currency Exchange.
- The docs state that supported resources are those defined in API reference or data exports.
- Requests for internal website APIs or in-game resources outside documentation are denied, and reverse-engineering endpoints outside documentation is against Terms guidance.
- No documented PoE2 rare-item Trade search/listing valuation API was found in Task 10A.

Implication: DonnieCraftShell must not implement production rare-item trade scraping or undocumented Trade API calls.

## Official Trade Website

Source: official Path of Exile Trade website and generated search URLs.

Findings:

- The official website is a user-facing search surface.
- A generated official Trade search URL is safer as a user workflow than automated scraping.
- Listing results are market asks, not completed sales.

Implication: MVP should generate comparable search definitions/URLs for user review and manual observation capture.

## Open-Source Price-Checking Tools

### Sidekick

Source: [Sidekick GitHub](https://github.com/Sidekick-Poe/Sidekick)

Findings:

- Sidekick is a PoE/PoE2 companion tool with price checking and trade-related workflows.
- It is open source and explicitly unaffiliated with GGG.
- Release notes mention trade-filter improvements and default modifier selection improvements.

Use for DonnieCraftShell: architecture inspiration only. Do not copy integration behavior or assume its trade access method is approved for server-side automation.

### Exiled Exchange 2

Source: [Exiled Exchange 2 GitHub](https://github.com/Kvan7/Exiled-Exchange-2)

Findings:

- Exiled Exchange 2 is an open-source PoE2 overlay for price checking, forked from Awakened PoE Trade.
- Community guides emphasize user-selected meaningful modifiers, broadening/narrowing searches, and comparing several listings.
- It does not provide guaranteed prices; rare-item pricing remains judgment-based.

Use for DonnieCraftShell: supports the design that rare valuation should build comparable searches around value-driving modifiers rather than every modifier.

## Third-Party Market Evidence

Task 10A did not identify a legitimate third-party source that provides authoritative completed-sale rare-item prices for PoE2.

Listings may be useful evidence if source, timestamp, and query definition are retained. They must be labeled listing-derived.

## Recommended Source Roles

- Official Developer API: use only documented endpoints; currently not sufficient for rare-item comparables.
- Official Trade search URL: recommended MVP user-facing workflow.
- Manual user-supplied listing observations: recommended MVP comparable evidence.
- Open-source tools: research inspiration, not permission evidence.
- Future TradeProvider adapters: allowed only after terms/source review.

## Open Questions

- Whether GGG will document a PoE2 rare-item trade/search API for third-party use.
- Whether generated Trade search URLs can include all required PoE2 modifier/stat filters reliably.
- How to preserve query definitions across Trade website changes.
- Whether any future third-party provider can supply listing or sale observations under acceptable terms.
