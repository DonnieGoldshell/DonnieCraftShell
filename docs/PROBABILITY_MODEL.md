# Probability Model

Task 9B implements framework-independent probability evidence contracts. It does not assign numeric probabilities to real crafting outcomes.

## Boundary

```text
CraftOutcomeEngine
-> CraftOutcomeSet

ProbabilityProvider
-> OutcomeProbabilityModel
```

The probability layer reads outcome sets and returns probability evidence beside them. It must not mutate `ParsedItem` or `CraftOutcomeSet`.

## Contracts

Executable contracts live in `packages/shared/donniecraftshell_contracts/probability.py`.

- `ProbabilityType`: `DETERMINISTIC`, `EXACT_MECHANICAL`, `DERIVED_MECHANICAL`, `EMPIRICAL_ESTIMATE`, `UNKNOWN`.
- `ProbabilityInterval`: optional lower/upper interval for future empirical evidence.
- `ProbabilityEvidence`: provenance-first record for action/outcome/candidate probability evidence.
- `OutcomeProbability`: probability evidence for one hypothetical final outcome.
- `DeterministicOperationEvidence`: deterministic operation component evidence, such as a guaranteed modifier family.
- `OutcomeProbabilityModel`: model for an entire outcome set.
- `ProbabilityProvider`: provider interface.
- `AnalyticalProbabilityRule`: explicit verified-mechanic rule that may derive probabilities from an already-enumerated outcome set.
- `AnalyticalProbabilityProvider`: applies only configured verified analytical rules and otherwise fails closed to UNKNOWN.
- `CompositeProbabilityProvider`: applies providers in explicit precedence order without averaging or merging conflicting evidence.
- `CurrentResearchProbabilityProvider`: Task 9A-compliant provider returning explicit unknown final probabilities for current real actions.

Task 15A adds the empirical evidence pipeline in `empirical_probability.py`.
It loads offline outcome-count observations, validates context and
provenance, and emits `EMPIRICAL_ESTIMATE` evidence through the existing
`OutcomeProbabilityModel` contract. See
[EMPIRICAL_PROBABILITY.md](EMPIRICAL_PROBABILITY.md).

Task 22B adds the analytical-provider framework. Production configuration uses
provider precedence:

1. Verified analytical mechanic rules.
2. Explicitly selected empirical probability datasets.
3. Current research fallback (`UNKNOWN`).

No production analytical rules are currently configured, because the existing
source-of-truth does not verify uniform Annulment selection or Exalted modifier
weights. The provider can be exercised by synthetic tests, but real actions
remain UNKNOWN until a source-backed rule is added.

## Invariants

Known numeric probabilities use `Decimal` and must satisfy `0 <= p <= 1`. Binary floating point is rejected.

Unknown probability is represented as `None`, never `0`.

If `probability_completeness = COMPLETE`, every outcome must have a numeric probability and known mass must equal `1` within `0.000000001`.

If `probability_completeness = PARTIAL`, known mass may be less than `1`.

If `probability_completeness = UNKNOWN`, no normalization is performed and no equal distribution fallback is allowed.

Empirical evidence uses observed frequencies from preserved raw counts. Missing,
unclassified, unmapped, or context-incompatible observations do not become zero
probabilities and do not pass EV readiness.

## Current Action Status

Final outcome probabilities remain `UNKNOWN` for:

- Annulment actions
- Exalted-style actions
- Greater/Perfect Exalted actions
- Omen-modified Exalted and Annulment actions

Essence of Hysteria carries deterministic evidence for the guaranteed Quiver modifier-family component, but final combined outcome probabilities remain `UNKNOWN` because random-removal probabilities are not source-backed.

## Analytical Evidence Rules

Analytical probabilities are allowed only when a rule explicitly states the
verified mechanical selection law and carries provenance. The provider checks:

- action identity,
- outcome-space completeness,
- selection rule where specified,
- source outcome-set identity where specified,
- exact enumerated outcome IDs where specified.

If any check fails, the provider returns the normal UNKNOWN research model and
adds a warning. It never falls back to equal distribution merely because
outcomes were enumerated.

The initial supported rule type is `UNIFORM_ENUMERATED_OUTCOMES`, but it is
only valid when a verified source establishes uniform selection over precisely
that enumerated outcome set. This is not currently established for PoE2
Annulment, Omen Annulment, Essence random removal, or Exalted-style modifier
addition.

## EV Readiness

`can_calculate_expected_value(probability_model)` returns true only when probability completeness is `COMPLETE`, every final outcome has a numeric probability, and total known mass equals `1`.

This readiness check does not evaluate valuation quality and does not calculate EV.
