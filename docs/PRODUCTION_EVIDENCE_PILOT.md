# Production Evidence Pilot

Task 27 adds an operator-facing workflow for running the first real First Playable evidence pilot on one Path of Exile 2 Rare Primed Quiver.

The pilot uses existing DonnieCraftShell contracts and local workspaces. It does not scrape Trade, fabricate prices, fabricate probabilities, auto-select empirical datasets, or calculate Advisor readiness in the frontend.

## Pilot Goal

Move one real analyzed First Playable Quiver as far as evidence honestly allows:

Clipboard item
-> backend analysis
-> real/manual current valuation evidence
-> real/manual material quote evidence
-> explicitly selected compatible probability evidence
-> real/manual outcome valuation evidence
-> optional bankroll/risk context
-> explicit rerun
-> backend decision state

`NO_RECOMMENDATION`, `ANALYSIS_PARTIAL`, `SCENARIO_READY`, and `UNKNOWN` remain successful outcomes when evidence is incomplete.

## What The UI Shows

The web workbench displays a `Production Evidence Pilot` panel after analysis.

It summarizes:

- current backend status: evidence incomplete, scenario ready, EV ready, or decision ready
- current-item valuation readiness
- crafting-material quote readiness
- probability evidence readiness
- outcome valuation readiness
- selected empirical dataset ID for the next rerun
- prepared manual valuation observations versus observations saved locally
- bankroll/risk context that will be sent on the next rerun
- the reminder that saved workspace evidence and selected IDs do not affect Advisor output until an explicit rerun

The panel routes operators into existing evidence tools:

- Manual Valuation Evidence for current item valuation
- Local Economy Quotes for material prices
- Craft Observation Recorder / Review / Import for empirical probability evidence
- Manual Valuation Evidence for each authoritative blocked outcome ID

## Real Evidence Checklist

1. Paste the real First Playable Quiver clipboard text and run analysis.
2. Confirm the item is the intended Rare Primed Quiver and inspect backend missing requirements.
3. Open current valuation workflow from the pilot panel or Evidence Readiness.
4. Enter real comparable listing observations for the current item.
5. Preview valuation evidence if useful.
6. Save current-item evidence locally if you want it to survive reloads.
7. Open the local quote workspace for each missing crafting material.
8. Enter real observed Exalted-unit quote evidence with source notes and observed timestamp.
9. Record, review, build, and register empirical probability observations if real compatible observations exist.
10. Explicitly select the registered empirical dataset ID in Advanced dataset and evidence context.
11. Open outcome valuation workflows for every authoritative blocked outcome ID.
12. Enter real comparable listing observations for each outcome.
13. Save outcome evidence locally if desired.
14. Enter bankroll and risk profile only if Dennis wants risk-adjusted output.
15. Click `Re-run Analysis`.
16. Inspect backend `Advisor Decision` and `Risk Adjustment` separately.

## Persistence And Activation

Saved local evidence is not the same as selected or submitted evidence.

- Manual valuation workspace records are saved by subject identity: `current` or `outcome:{outcome_id}`.
- Local economy quotes are saved by exact league and economy asset.
- Observation workspace/review records can be exported and built into empirical datasets.
- Empirical dataset registration is inert until the request explicitly names `empirical_probability_dataset_version`.
- Saved evidence changes no current analysis result until the operator clicks `Re-run Analysis`.

The pilot panel reports saved local manual valuation counts separately from observations prepared for the next rerun.
After a successful explicit rerun that submits current-item manual observations,
the panel may report those request-scoped rows as applied to the current
analysis. This does not mean the rows were persisted, and it does not convert a
broad-bracket-only valuation into a point SELL NOW baseline.
When the Comparable Valuation Model returns `SUPPORTED_RANGE_ONLY`, Evidence
Readiness should treat the current valuation as partial market evidence rather
than missing evidence. Stop/continue economics still fail closed until an
authoritative point market valuation exists.

## Risk And Bankroll

Bankroll and risk profile are explicit request inputs.

They affect risk-adjusted decision policy only. They do not alter raw Expected Value, raw Advisor ranking, material costs, probabilities, or valuations.

Leaving bankroll/risk blank is valid. In that case the backend can still return raw analysis, while risk-adjusted decision readiness may remain unavailable or default only when the backend already treats the provided risk context as sufficient.

## Synthetic Evidence Boundary

Synthetic evidence may appear in automated tests and documentation examples only.

For a real pilot, do not use:

- synthetic current valuation observations
- synthetic outcome valuations
- synthetic local economy quotes
- synthetic empirical probability datasets
- made-up source notes or timestamps

If real probability evidence cannot be collected, stop at the probability blocker and create a follow-up issue describing the missing evidence.

## Pilot Result Capture

When Dennis runs the pilot, capture:

- item clipboard text or fixture reference
- analysis timestamp
- league and dataset versions
- current valuation evidence summary
- local economy quote evidence summary
- empirical dataset ID, if selected
- outcome valuation coverage count
- bankroll/risk context, if supplied
- backend analysis status
- raw Advisor decision
- risk-adjusted decision
- remaining missing requirements
- warnings/blockers that prevented a genuine recommendation

Use unresolved blockers as follow-up issue material. Do not work around them by entering guessed evidence.
