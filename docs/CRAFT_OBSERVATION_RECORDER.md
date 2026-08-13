# Craft Observation Recorder

Task 16A adds a manual evidence-collection workflow for real crafting observations.
It records what the user observed before and after performing a craft outside
DonnieCraftShell. It does not calculate probabilities, expected value, valuation,
or Advisor recommendations.

## Workflow

1. Analyze a supported item and action so DonnieCraftShell has a source
   `CraftOutcomeSet` and deterministic outcome IDs.
2. Paste the item clipboard text before the craft.
3. Perform the craft manually in Path of Exile 2.
4. Paste the resulting item clipboard text after the craft.
5. Record the observation as:
   - `AUTOMATIC` only when before/after state maps uniquely to one existing
     outcome ID.
   - `MANUAL` when the user explicitly chooses an outcome ID.
   - `UNCLASSIFIED` when the result cannot be mapped safely.
6. Review saved observations in the local browser session.
7. Export JSON compatible with the empirical observation import workflow.

## Classification Semantics

The first automatic classifier is intentionally conservative. It supports only a
single explicit modifier removal that matches exactly one backend-derived
`CraftOutcomeSet` state. Client-supplied candidate IDs or modifier text are not
authoritative for `AUTOMATIC` classification. Ambiguous, unsupported,
added-modifier, special-origin, corrupted, or otherwise unclear transitions are
recorded as `UNCLASSIFIED`.

Manual classification is allowed, but it is preserved as `MANUAL` and requires
an explicit outcome ID from the backend-derived current outcome set.
DonnieCraftShell never silently invents or guesses an outcome ID.

## Item Context Validation

Recorder context is derived from parsed before/after item text. The API rejects
records when the request item class does not match the parsed item class, when
before/after item classes differ, or when conservative identity fields such as
rarity, base type, item level, required level, or implicits differ. This prevents
evidence labeled as one item context from being produced by unrelated item
states.

The exported source outcome-set identity is derived from backend-generated
outcome enumeration, not from client-supplied request fields. Crafting and
modifier dataset versions are likewise derived from or strictly validated
against the injected backend datasets before they are written as evidence
provenance.

## Raw Record ID Policy

Each recorded observation receives a deterministic raw record ID derived from:

- action ID
- source outcome-set identity
- item class
- league
- observed timestamp
- before-item fingerprint
- after-item fingerprint
- classification method
- outcome ID or `UNCLASSIFIED`

Reloading the same saved record preserves the same ID. Distinct crafts with
different before/after evidence or classification produce different IDs. Existing
Task 15C import deduplication still protects duplicate exported records.

## Provenance Fields

Recorder exports preserve:

- before and after raw clipboard text
- before and after item fingerprints
- league and game/version context where known
- crafting and modifier dataset versions
- source outcome-set identity
- source ID and source type
- observed timestamp
- classification method, reason, and warnings
- verification status

No account credentials, secrets, process data, or automated gameplay interaction
are collected.

## Export Format

The export payload is:

```json
{
  "recorder_version": "dc-observation-recorder-v1",
  "exported_at": "2026-08-13T10:00:00+00:00",
  "observations": [
    {
      "raw_record_id": "manual-craft-observation-...",
      "action_id": "dc:poe2:craft-action:orb-of-annulment",
      "source_outcome_set_id": "...",
      "item_class": "Quivers",
      "league": "Runes of Aldur",
      "observed_at": "...",
      "source_type": "MANUAL_RESEARCH",
      "outcome_id": "...",
      "unclassified": false,
      "classification_method": "MANUAL"
    }
  ]
}
```

Extra recorder/audit fields are tolerated by the Task 15C importer. The importer
uses the empirical observation fields and preserves unclassified observations in
the denominator.

## Probability Boundary

Recording observations does not make a probability model trustworthy or
complete. Exported observations must still pass the Task 15C import workflow,
then the empirical probability readiness gates from Task 15A/15B. Real Advisor
probabilities remain `UNKNOWN` unless an explicitly configured empirical dataset
is selected and passes all context checks.

## Current Limitations

- Automatic classification only handles single explicit removals.
- Browser storage is local React session state; no database exists yet.
- Export review/curation is still external to the recorder.
- No complete real empirical PoE2 sample is included.
