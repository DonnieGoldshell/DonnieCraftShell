import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  DEFAULT_AFFIX_CAPACITY_DATASET,
  DEFAULT_CRAFTING_DATASET,
  DEFAULT_GAME_DATA_DATASET,
  DEFAULT_LEAGUE,
  DIVINE_ASSET_ID,
  EXALTED_ASSET_ID,
  type AdvisorAnalyzeResponse,
  type ManualValuationPreviewResponse
} from "@/api/advisor";
import { AdvisorWorkbench } from "./AdvisorWorkbench";

const quiverResponse: AdvisorAnalyzeResponse = {
  analysis_id: "019febcf-bf04-73e2-a845-1f2278b0ef05",
  status: "ANALYSIS_PARTIAL",
  context: {
    league: DEFAULT_LEAGUE,
    game_data_dataset_version: DEFAULT_GAME_DATA_DATASET,
    crafting_dataset_version: DEFAULT_CRAFTING_DATASET,
    affix_capacity_dataset_version: DEFAULT_AFFIX_CAPACITY_DATASET,
    economy_snapshot_ids: ["economy-snapshot-currency"]
  },
  item: {
    item_class: "Quivers",
    rarity: "Rare",
    item_name: "Honed Stinger",
    base_type: "Primed Quiver",
    item_level: 82,
    required_level: 65,
    special_states: [],
    implicit_modifiers: [],
    prefixes: [
      {
        raw_text: "13(11-13)% increased Attack Speed",
        display_name: "of Mastery",
        tier: "2",
        affix_type: "PREFIX",
        origin: null,
        canonical_id: "dc:poe2:modifier-tier:attack-speed:t2",
        resolution_status: "RESOLVED",
        tags: ["Attack", "Speed"]
      }
    ],
    suffixes: [
      {
        raw_text: "31(26-35) to Dexterity",
        display_name: "of the Panther",
        tier: "3",
        affix_type: "SUFFIX",
        origin: null,
        canonical_id: "dc:poe2:modifier-tier:dexterity:t3",
        resolution_status: "RESOLVED",
        tags: ["Attribute"]
      }
    ],
    corruption_enhancements: [],
    unparsed_lines: []
  },
  enrichment_summary: {
    enrichment_id: "enrichment-1",
    resolved_base_id: "dc:poe2:item-base:primed-quiver",
    snapshot_id: DEFAULT_GAME_DATA_DATASET,
    resolved_modifier_count: 2,
    ambiguous_modifier_count: 0,
    unresolved_modifier_count: 0,
    warnings: []
  },
  affix_state: {
    observed_prefix_count: 3,
    observed_suffix_count: 3,
    prefix_capacity: 3,
    suffix_capacity: 3,
    open_prefix_count: 0,
    open_suffix_count: 0,
    warnings: []
  },
  actions: [
    {
      action_id: "dc:poe2:craft-action:orb-of-annulment",
      display_name: "Orb of Annulment",
      applicability: "APPLICABLE",
      applicability_reasons: ["Rare item has eligible explicit modifiers."],
      failed_preconditions: [],
      unknown_preconditions: [],
      required_materials: [{ asset_id: "dc:poe2:economy-asset:currency:orb-of-annulment", quantity: "1" }],
      material_cost: {
        complete: false,
        freshness: "UNAVAILABLE",
        lines: [],
        total: null,
        warnings: ["Missing Orb of Annulment quote."]
      },
      outcome_count: 6,
      outcome_ids: ["outcome-1", "outcome-2", "outcome-3", "outcome-4", "outcome-5", "outcome-6"],
      outcome_space_completeness: "COMPLETE",
      probability_completeness: "UNKNOWN",
      scenario: {
        readiness: "INSUFFICIENT_DATA",
        outcome_count: 6,
        valued_outcome_count: 0,
        unvalued_outcome_count: 6,
        valuation_completeness: "NONE",
        best_valuated_outcome: null,
        worst_valuated_outcome: null,
        median_valuated_outcome: null,
        upside_relative_to_current: null,
        downside_relative_to_current: null,
        reasons: ["Outcome valuation evidence is required."]
      },
      expected_value: {
        available: false,
        status: "NOT_AVAILABLE",
        gross_expected_outcome_value: null,
        craft_cost: null,
        net_expected_value: null,
        current_item_value: null,
        expected_gain_vs_sell_now: null,
        roi_on_craft_cost: null,
        algorithm_version: "dc-ev-v1",
        unavailable_reasons: ["Probability model is UNKNOWN."]
      },
      advisor_candidate_status: "NON_RANKABLE_SCENARIO",
      missing_requirements: [
        {
          type: "PROBABILITY_EVIDENCE_REQUIRED",
          action_id: "dc:poe2:craft-action:orb-of-annulment",
          blocks: ["EXPECTED_VALUE", "ADVISOR_RANKING"],
          reason: "No source-backed numeric probability model is available."
        }
      ],
      warnings: []
    },
    {
      action_id: "dc:poe2:craft-action:exalted-orb",
      display_name: "Exalted Orb",
      applicability: "NOT_APPLICABLE",
      applicability_reasons: [],
      failed_preconditions: ["No open explicit affix slot"],
      unknown_preconditions: [],
      required_materials: [{ asset_id: "dc:poe2:economy-asset:currency:exalted-orb", quantity: "1" }],
      material_cost: {
        complete: true,
        freshness: "FRESH",
        lines: [],
        total: { amount: "1", unit: "EXALTED_ECONOMIC_UNIT" },
        warnings: []
      },
      outcome_count: 0,
      outcome_ids: [],
      outcome_space_completeness: null,
      probability_completeness: "UNKNOWN",
      scenario: null,
      expected_value: null,
      advisor_candidate_status: "NON_RANKABLE",
      missing_requirements: [],
      warnings: []
    }
  ],
  decision: {
    decision_type: "NO_RECOMMENDATION",
    selected_candidate_id: null,
    reasons: ["All available craft actions lack complete probability evidence."],
    warnings: [],
    algorithm_version: "dc-advisor-v1"
  },
  risk_adjusted_decision: null,
  evidence_readiness: {
    items: [
      {
        category: "CURRENT_ITEM_VALUATION",
        label: "Current item valuation",
        status: "MISSING",
        summary: "Manual comparable listing evidence is needed for the SELL NOW baseline.",
        targets: [
          {
            target_type: "CURRENT_ITEM",
            target_id: "current",
            reason: "Current item valuation evidence is missing.",
            outcome_ids: [],
            blocks: ["Advisor decision"]
          }
        ],
        evidence_tool: "manual-current-valuation",
        diagnostics: []
      },
      {
        category: "ECONOMY_CRAFTING_COST",
        label: "Economy prices",
        status: "MISSING",
        summary: "1 crafting material price target is missing.",
        targets: [
          {
            target_type: "ECONOMY_ASSET",
            target_id: "dc:poe2:economy-asset:currency:orb-of-annulment",
            action_id: "dc:poe2:craft-action:orb-of-annulment",
            action_display_name: "Orb of Annulment",
            asset_id: "dc:poe2:economy-asset:currency:orb-of-annulment",
            reason: "Missing economy quote for Orb Of Annulment.",
            outcome_ids: [],
            blocks: ["Craft material cost", "Expected Value"]
          }
        ],
        evidence_tool: "local-economy-quotes",
        diagnostics: []
      },
      {
        category: "PROBABILITY",
        label: "Probability evidence",
        status: "MISSING",
        summary: "1 action probability model needs evidence.",
        targets: [
          {
            target_type: "ACTION_PROBABILITY_MODEL",
            target_id: "outcome-set:annulment",
            action_id: "dc:poe2:craft-action:orb-of-annulment",
            action_display_name: "Orb of Annulment",
            outcome_ids: ["outcome-1", "outcome-2", "outcome-3", "outcome-4", "outcome-5", "outcome-6"],
            reason: "Orb of Annulment probability model is UNKNOWN with 6 unknown outcome probabilities.",
            blocks: ["Expected Value"]
          }
        ],
        evidence_tool: "observation-recorder-review-import",
        diagnostics: []
      },
      {
        category: "OUTCOME_VALUATION",
        label: "Outcome valuation",
        status: "MISSING",
        summary: "1 action outcome set has missing outcome valuations.",
        targets: [
          {
            target_type: "OUTCOME_VALUATION",
            target_id: "dc:poe2:craft-action:orb-of-annulment",
            action_id: "dc:poe2:craft-action:orb-of-annulment",
            action_display_name: "Orb of Annulment",
            outcome_ids: ["outcome-1", "outcome-2", "outcome-3", "outcome-4", "outcome-5", "outcome-6"],
            reason: "Orb of Annulment has valuation coverage 0/6.",
            blocks: ["Scenario", "Expected Value"]
          }
        ],
        evidence_tool: "manual-outcome-valuation",
        diagnostics: []
      },
      {
        category: "VERIFIED_MECHANICS",
        label: "Verified mechanics",
        status: "READY",
        summary: "No verified mechanic blockers were reported for analyzed actions.",
        targets: [],
        evidence_tool: "mechanic-research",
        diagnostics: []
      }
    ],
    warnings: [
      "Evidence readiness is derived from explicit Advisor inputs, action analysis, and missing requirements; it does not fabricate confidence or recommendation eligibility."
    ]
  },
  missing_requirements: [
    {
      type: "CURRENT_VALUATION_EVIDENCE_REQUIRED",
      action_id: null,
      blocks: ["SELL_NOW", "ADVISOR_RANKING"],
      reason: "Manual current valuation evidence is required."
    },
    {
      type: "PROBABILITY_EVIDENCE_REQUIRED",
      action_id: "dc:poe2:craft-action:orb-of-annulment",
      blocks: ["EXPECTED_VALUE", "ADVISOR_RANKING"],
      reason: "No source-backed numeric probability model is available."
    }
  ],
  warnings: ["Partial analysis is a successful result."],
  provenance: []
};

const valuedQuiverResponse: AdvisorAnalyzeResponse = {
  ...quiverResponse,
  status: "SCENARIO_READY",
  actions: quiverResponse.actions.map((action) =>
    action.action_id === "dc:poe2:craft-action:orb-of-annulment"
      ? {
          ...action,
          scenario: {
            readiness: "SCENARIO_ONLY",
            outcome_count: 6,
            valued_outcome_count: 1,
            unvalued_outcome_count: 5,
            valuation_completeness: "PARTIAL",
            best_valuated_outcome: { amount: "110", unit: "EXALTED_ECONOMIC_UNIT" },
            worst_valuated_outcome: { amount: "110", unit: "EXALTED_ECONOMIC_UNIT" },
            median_valuated_outcome: { amount: "110", unit: "EXALTED_ECONOMIC_UNIT" },
            upside_relative_to_current: null,
            downside_relative_to_current: null,
            reasons: ["Synthetic test response with one valuated outcome."]
          }
        }
      : action
  ),
  missing_requirements: quiverResponse.missing_requirements.filter(
    (requirement) => requirement.type !== "CURRENT_VALUATION_EVIDENCE_REQUIRED"
  )
};

const empiricalQuiverResponse: AdvisorAnalyzeResponse = {
  ...quiverResponse,
  context: {
    ...quiverResponse.context,
    empirical_probability_dataset_version: "empirical-probability-browser-test"
  },
  actions: quiverResponse.actions.map((action) =>
    action.action_id === "dc:poe2:craft-action:orb-of-annulment"
      ? {
          ...action,
          probability_completeness: "COMPLETE",
          probability: {
            completeness: "COMPLETE",
            source_outcome_set_id: "manual-recorder:dc:poe2:craft-action:orb-of-annulment",
            outcome_count: 1,
            known_outcome_count: 1,
            total_known_probability_mass: "1",
            methodology_summary: "Synthetic frontend test-only empirical probability evidence.",
            dataset_versions: ["empirical-probability-browser-test"],
            outcome_probabilities: [
              {
                outcome_id: "outcome-1",
                probability: "1",
                evidence: [
                  {
                    evidence_id: "synthetic-frontend-probability-evidence",
                    probability_type: "EMPIRICAL_ESTIMATE",
                    probability: "1",
                    outcome_id: "outcome-1",
                    evidence_dataset_version: "empirical-probability-browser-test",
                    methodology: "Synthetic frontend regression test.",
                    sample_size: 1,
                    uncertainty_interval: null,
                    warnings: ["Synthetic test-only empirical evidence."]
                  }
                ],
                warnings: []
              }
            ],
            warnings: ["Synthetic test-only empirical evidence."]
          },
          missing_requirements: []
        }
      : action
  ),
  evidence_readiness: {
    ...quiverResponse.evidence_readiness!,
    items: quiverResponse.evidence_readiness!.items.map((item) =>
      item.category === "PROBABILITY"
        ? {
            ...item,
            status: "READY",
            summary: "Selected empirical probability dataset supplied usable evidence for the action.",
            targets: []
          }
        : item
    )
  },
  missing_requirements: quiverResponse.missing_requirements.filter(
    (requirement) => requirement.type !== "PROBABILITY_EVIDENCE_REQUIRED"
  )
};

const decisionReadyQuiverResponse: AdvisorAnalyzeResponse = {
  ...quiverResponse,
  status: "DECISION_READY",
  actions: quiverResponse.actions.map((action) =>
    action.action_id === "dc:poe2:craft-action:orb-of-annulment"
      ? {
          ...action,
          material_cost: {
            complete: true,
            freshness: "FRESH",
            lines: [],
            total: { amount: "7.5", unit: "EXALTED_ECONOMIC_UNIT" },
            warnings: []
          },
          probability_completeness: "COMPLETE",
          scenario: {
            readiness: "EV_READY",
            outcome_count: 6,
            valued_outcome_count: 6,
            unvalued_outcome_count: 0,
            valuation_completeness: "COMPLETE",
            best_valuated_outcome: { amount: "130", unit: "EXALTED_ECONOMIC_UNIT" },
            worst_valuated_outcome: { amount: "130", unit: "EXALTED_ECONOMIC_UNIT" },
            median_valuated_outcome: { amount: "130", unit: "EXALTED_ECONOMIC_UNIT" },
            upside_relative_to_current: { amount: "30", unit: "EXALTED_ECONOMIC_UNIT" },
            downside_relative_to_current: { amount: "30", unit: "EXALTED_ECONOMIC_UNIT" },
            reasons: ["Synthetic test-only complete evidence makes the action EV-ready."]
          },
          expected_value: {
            available: true,
            status: "AVAILABLE",
            gross_expected_outcome_value: { amount: "130", unit: "EXALTED_ECONOMIC_UNIT" },
            craft_cost: { amount: "7.5", unit: "EXALTED_ECONOMIC_UNIT" },
            net_expected_value: { amount: "122.5", unit: "EXALTED_ECONOMIC_UNIT" },
            current_item_value: { amount: "100", unit: "EXALTED_ECONOMIC_UNIT" },
            expected_gain_vs_sell_now: { amount: "22.5", unit: "EXALTED_ECONOMIC_UNIT" },
            roi_on_craft_cost: "3",
            algorithm_version: "dc-ev-v1",
            unavailable_reasons: []
          },
          advisor_candidate_status: "RANKABLE_EV",
          missing_requirements: [],
          warnings: []
        }
      : action
  ),
  decision: {
    decision_type: "CRAFT",
    selected_candidate_id: "advisor-candidate:craft:dc:poe2:craft-action:orb-of-annulment",
    reasons: [
      "dc:poe2:craft-action:orb-of-annulment has a net expected value 22.5 Ex above the current listing-derived item valuation.",
      "Only EV-ready craft candidates participated in ranking."
    ],
    warnings: [],
    algorithm_version: "dc-advisor-v1"
  },
  risk_adjusted_decision: {
    decision_type: "CRAFT",
    raw_winner_candidate_id: "advisor-candidate:craft:dc:poe2:craft-action:orb-of-annulment",
    selected_candidate_id: "advisor-candidate:craft:dc:poe2:craft-action:orb-of-annulment",
    changed_by_policy: false,
    risk_policy_version: "dc-risk-policy-v1",
    reasons: ["Synthetic test-only risk context accepts the raw EV-ready craft candidate."],
    triggered_rules: []
  },
  evidence_readiness: {
    ...quiverResponse.evidence_readiness!,
    items: quiverResponse.evidence_readiness!.items.map((item) =>
      ["CURRENT_ITEM_VALUATION", "ECONOMY_CRAFTING_COST", "PROBABILITY", "OUTCOME_VALUATION"].includes(item.category)
        ? {
            ...item,
            status: "READY",
            summary: `Synthetic test-only ${item.label.toLowerCase()} evidence is complete for Orb of Annulment.`,
            targets: []
          }
        : item
    )
  },
  missing_requirements: [],
  warnings: ["Synthetic test-only decision-ready response."]
};

const multiProbabilityTargetResponse: AdvisorAnalyzeResponse = {
  ...quiverResponse,
  actions: [
    quiverResponse.actions[0],
    {
      ...quiverResponse.actions[0],
      action_id: "dc:poe2:craft-action:omen-greater-annulment-orb-of-annulment",
      display_name: "Greater Annulment",
      required_materials: [
        { asset_id: "dc:poe2:economy-asset:currency:orb-of-annulment", quantity: "1" },
        { asset_id: "dc:poe2:economy-asset:ritual:omen-of-greater-annulment", quantity: "1" }
      ],
      outcome_ids: ["greater-outcome-1", "greater-outcome-2"],
      outcome_count: 2,
      probability: {
        ...quiverResponse.actions[0].probability!,
        source_outcome_set_id: "outcome-set:greater-annulment",
        outcome_count: 2,
        outcome_probabilities: []
      },
      missing_requirements: [
        {
          type: "PROBABILITY_EVIDENCE_REQUIRED",
          action_id: "dc:poe2:craft-action:omen-greater-annulment-orb-of-annulment",
          blocks: ["EXPECTED_VALUE", "ADVISOR_RANKING"],
          reason: "No source-backed numeric probability model is available."
        }
      ]
    },
    quiverResponse.actions[1]
  ],
  evidence_readiness: {
    ...quiverResponse.evidence_readiness!,
    items: quiverResponse.evidence_readiness!.items.map((item) =>
      item.category === "PROBABILITY"
        ? {
            ...item,
            summary: "2 action probability models need evidence.",
            targets: [
              item.targets[0],
              {
                target_type: "ACTION_PROBABILITY_MODEL",
                target_id: "outcome-set:greater-annulment",
                action_id: "dc:poe2:craft-action:omen-greater-annulment-orb-of-annulment",
                action_display_name: "Greater Annulment",
                outcome_ids: ["greater-outcome-1", "greater-outcome-2"],
                reason: "Greater Annulment probability model is UNKNOWN with 2 unknown outcome probabilities.",
                blocks: ["Expected Value"]
              }
            ]
          }
        : item
    )
  },
  missing_requirements: [
    ...quiverResponse.missing_requirements,
    {
      type: "PROBABILITY_EVIDENCE_REQUIRED",
      action_id: "dc:poe2:craft-action:omen-greater-annulment-orb-of-annulment",
      blocks: ["EXPECTED_VALUE", "ADVISOR_RANKING"],
      reason: "No source-backed numeric probability model is available."
    }
  ]
};

function manualPreviewResponse(
  overrides: Partial<ManualValuationPreviewResponse> = {}
): ManualValuationPreviewResponse {
  return {
    subject_id: "current",
    subject_type: "CURRENT_ITEM",
    outcome_id: null,
    strategy: "STRICT",
    evidence_set_id: "manual-preview-current",
    observation_count: 1,
    usable_observation_count: 1,
    unusable_observation_count: 0,
    duplicate_listing_ids: [],
    readiness: "READY",
    estimate_type: "LISTING_DERIVED",
    estimated_value: { amount: "120", unit: "EXALTED_ECONOMIC_UNIT" },
    plausible_low: { amount: "120", unit: "EXALTED_ECONOMIC_UNIT" },
    plausible_high: { amount: "120", unit: "EXALTED_ECONOMIC_UNIT" },
    confidence: {
      level: "MEDIUM",
      reasons: ["Synthetic test preview."]
    },
    liquidity: "LOW",
    economy_snapshot_ids: ["economy-snapshot-currency"],
    comparable_results: [
      {
        comparable_id: "manual-preview-current:0",
        external_listing_id: "edit-me",
        listing_price: "120",
        listing_currency_asset_id: EXALTED_ASSET_ID,
        normalized_value: { amount: "120", unit: "EXALTED_ECONOMIC_UNIT" },
        economy_freshness: "FRESH",
        economy_snapshot_id: "economy-snapshot-currency",
        observed_at: "2026-08-13T10:00:00Z",
        warnings: ["Manual API observation; listing price is not a realized sale."]
      }
    ],
    warnings: ["Manual API observation; listing price is not a realized sale."],
    ...overrides
  };
}

describe("AdvisorWorkbench", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  async function openAdvancedTools(user: ReturnType<typeof userEvent.setup>) {
    if (screen.queryByRole("button", { name: /add observation/i })) {
      return;
    }
    await user.click(screen.getByText(/advanced evidence & diagnostics/i));
  }

  it("renders partial Quiver analysis, action states, decision and missing requirements", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => quiverResponse
      })
    );
    const user = userEvent.setup();

    render(<AdvisorWorkbench />);
    await user.type(screen.getByLabelText(/clipboard item text/i), "Item Class: Quivers\nRarity: Rare");
    await user.click(screen.getByRole("button", { name: /analyze quiver/i }));

    expect(await screen.findByText("Primed Quiver")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: /player advisor summary/i })).toBeInTheDocument();
    expect(screen.getByText("Advisor for Primed Quiver")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: /production evidence pilot/i })).toBeInTheDocument();
    expect(screen.getByText("Evidence incomplete - recommendation unavailable")).toBeInTheDocument();
    expect(screen.getByText(/saved workspace evidence and selected dataset ids do not affect advisor output/i)).toBeInTheDocument();
    expect(screen.getAllByText("3/3 prefixes, 3/3 suffixes").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("What is blocking a stronger recommendation?")).toBeInTheDocument();
    expect(screen.getAllByText("Valuation evidence").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Probability evidence").length).toBeGreaterThan(0);
    expect(screen.getByRole("region", { name: /evidence readiness/i })).toBeInTheDocument();
    expect(screen.getByText("Evidence Readiness")).toBeInTheDocument();
    expect(screen.getByText("Manual comparable listing evidence is needed for the SELL NOW baseline.")).toBeInTheDocument();
    expect(screen.getByText("1 action probability model needs evidence.")).toBeInTheDocument();
    expect(screen.getAllByText(/6 outcomes need evidence/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/does not guarantee a craft recommendation/i)).toBeInTheDocument();
    expect(screen.getByText("Advisor Decision")).toBeInTheDocument();
    expect(screen.getAllByText("No Recommendation").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Orb of Annulment").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Exalted Orb").length).toBeGreaterThan(0);
    expect(screen.getByText("Missing price")).toBeInTheDocument();
    expect(screen.getByText("No open explicit affix slot")).toBeInTheDocument();
    expect(screen.getByText("Current Valuation Evidence Required")).toBeInTheDocument();
    expect(screen.getAllByText("Probability Evidence Required").length).toBeGreaterThan(0);
    expect(screen.getByText(/advanced diagnostics: raw missing requirements/i)).toBeInTheDocument();
    expect(screen.getByText(/advanced evidence & diagnostics/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /add observation/i })).not.toBeInTheDocument();

    expect(screen.getByRole("button", { name: /collect probability evidence/i })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /open current valuation workflow/i }));
    expect(screen.getByRole("button", { name: /add observation/i })).toBeVisible();
    expect(screen.getByLabelText(/evidence subject/i)).toHaveValue("current");
    expect(fetch).toHaveBeenCalledTimes(1);

    await user.click(screen.getByRole("button", { name: /collect probability evidence/i }));

    expect(screen.getByRole("button", { name: /add observation/i })).toBeVisible();
    expect(screen.getByText(/targeted from evidence readiness: collect probability evidence for orb of annulment/i)).toBeVisible();
    expect((screen.getByLabelText(/craft action/i) as HTMLSelectElement).value).toBe(
      "dc:poe2:craft-action:orb-of-annulment"
    );
    expect(fetch).toHaveBeenCalledTimes(1);

    await user.click(screen.getByText(/advanced evidence & diagnostics/i));
    expect(screen.queryByRole("button", { name: /add observation/i })).not.toBeInTheDocument();
    await openAdvancedTools(user);

    expect(screen.getByText(/listing-derived estimates are not guaranteed sale prices/i)).toBeVisible();
    expect(screen.getByRole("button", { name: /add observation/i })).toBeVisible();
  });

  it("renders backend decision-ready state without stale evidence collection CTAs", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => decisionReadyQuiverResponse
      })
    );
    const user = userEvent.setup();

    render(<AdvisorWorkbench />);
    await user.type(screen.getByLabelText(/clipboard item text/i), "Item Class: Quivers\nRarity: Rare");
    await user.click(screen.getByRole("button", { name: /analyze quiver/i }));

    await screen.findByText("Decision Ready");
    expect(screen.getByText("Decision ready - backend decision available")).toBeInTheDocument();
    expect(screen.getByText(/raw and risk-adjusted decision state/i)).toBeInTheDocument();
    expect(screen.getAllByText("Craft").length).toBeGreaterThan(0);
    expect(screen.getAllByText(/net expected value 22.5 ex above/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/raw winner: advisor-candidate:craft:dc:poe2:craft-action:orb-of-annulment/i)).toBeInTheDocument();
    expect(screen.getByText("Net EV: 122.5 Ex")).toBeInTheDocument();
    expect(screen.getByText("Gain: 22.5 Ex")).toBeInTheDocument();
    expect(screen.getByText("Craft cost: 7.5 Ex")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /collect probability evidence/i })).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /add outcome valuation evidence for orb of annulment/i })
    ).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /open current valuation workflow/i })).not.toBeInTheDocument();
  });

  it("opens probability collection per authoritative blocked action target only", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => multiProbabilityTargetResponse
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<AdvisorWorkbench />);
    await user.type(screen.getByLabelText(/clipboard item text/i), "Item Class: Quivers\nRarity: Rare");
    await user.click(screen.getByRole("button", { name: /analyze quiver/i }));

    expect(await screen.findByText("Primed Quiver")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /collect probability evidence for/i })).toHaveLength(2);
    expect(screen.getByRole("button", { name: /collect probability evidence for orb of annulment/i })).toBeVisible();
    expect(screen.getByRole("button", { name: /collect probability evidence for greater annulment/i })).toBeVisible();
    expect(screen.queryByRole("button", { name: /collect probability evidence for exalted orb/i })).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /collect probability evidence for greater annulment/i }));
    expect(await screen.findByText("Craft Observation Recorder")).toBeInTheDocument();
    expect(screen.getByText(/targeted from evidence readiness: collect probability evidence for greater annulment/i)).toBeVisible();
    expect((screen.getByLabelText(/craft action/i) as HTMLSelectElement).value).toBe(
      "dc:poe2:craft-action:omen-greater-annulment-orb-of-annulment"
    );
    expect(fetchMock).toHaveBeenCalledTimes(1);

    await user.click(screen.getByRole("button", { name: /collect probability evidence for orb of annulment/i }));
    expect(screen.getByText(/targeted from evidence readiness: collect probability evidence for orb of annulment/i)).toBeVisible();
    expect((screen.getByLabelText(/craft action/i) as HTMLSelectElement).value).toBe(
      "dc:poe2:craft-action:orb-of-annulment"
    );
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect((screen.getByLabelText(/empirical evidence dataset/i) as HTMLInputElement).value).toBe("");
  });

  it("opens local economy quote workflow from readiness without rerunning analysis on save", async () => {
    const quoteRecord = {
      evidence_id: "local-annulment",
      league: DEFAULT_LEAGUE,
      asset_id: "dc:poe2:economy-asset:currency:orb-of-annulment",
      amount: "7.5",
      currency_asset_id: EXALTED_ASSET_ID,
      observed_at: "2026-08-21T12:00:00+00:00",
      source_type: "MANUAL_RESEARCH",
      source_reference: "operator note",
      notes: "Synthetic frontend test quote.",
      created_at: "2026-08-21T12:00:00+00:00",
      updated_at: "2026-08-21T12:00:00+00:00"
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => quiverResponse
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          workspace_version: "dc-economy-quote-workspace-v1",
          status: "SAVED",
          evidence_id: "local-annulment",
          record: quoteRecord,
          persistence: {
            storage_version: "dc-economy-quote-workspace-storage-v1",
            storage_mode: "IN_MEMORY",
            persistence_enabled: false,
            loaded_quote_count: 1,
            skipped_quote_count: 0,
            warnings: []
          },
          warnings: ["Stored local economy quote evidence applies only after Advisor analysis is re-run."]
        })
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          workspace_version: "dc-economy-quote-workspace-v1",
          records: [quoteRecord],
          persistence: {
            storage_version: "dc-economy-quote-workspace-storage-v1",
            storage_mode: "IN_MEMORY",
            persistence_enabled: false,
            loaded_quote_count: 1,
            skipped_quote_count: 0,
            warnings: []
          },
          warnings: []
        })
      });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<AdvisorWorkbench />);
    await user.type(screen.getByLabelText(/clipboard item text/i), "Item Class: Quivers\nRarity: Rare");
    await user.click(screen.getByRole("button", { name: /analyze quiver/i }));
    await screen.findByText("Primed Quiver");
    await user.click(screen.getByRole("button", { name: /open economy quote workflow/i }));

    expect(screen.getByRole("region", { name: /local economy quote workflow/i })).toBeVisible();
    expect(screen.getByLabelText(/needed asset/i)).toHaveValue("dc:poe2:economy-asset:currency:orb-of-annulment");

    await user.type(screen.getByLabelText(/quote in exalted units/i), "7.5");
    await user.type(screen.getByLabelText(/source reference/i), "operator note");
    await user.click(screen.getByRole("button", { name: /save local quote/i }));

    await screen.findByText(/re-run analysis to apply it/i);
    expect(fetchMock.mock.calls.filter((call) => String(call[0]).includes("/api/v1/advisor/analyze"))).toHaveLength(1);
    expect(fetchMock.mock.calls[1][0]).toContain("/api/v1/advisor/economy-quotes/workspace/quotes");
    const saveBody = JSON.parse(fetchMock.mock.calls[1][1].body as string);
    expect(saveBody.record).toEqual(
      expect.objectContaining({
        league: DEFAULT_LEAGUE,
        asset_id: "dc:poe2:economy-asset:currency:orb-of-annulment",
        amount: "7.5",
        currency_asset_id: EXALTED_ASSET_ID,
        source_reference: "operator note"
      })
    );
  });

  it("adds current-item manual comparable observations to the next advisor request", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => quiverResponse
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<AdvisorWorkbench />);
    await openAdvancedTools(user);
    await user.type(screen.getByLabelText(/listing amount/i), "5.5");
    await user.type(screen.getByLabelText(/listing id/i), "current-listing-1");
    await user.type(screen.getByLabelText(/listing\/item note/i), "manual current comparable");
    await user.click(screen.getByRole("button", { name: /add observation/i }));
    expect(screen.getByLabelText(/current item observations amount 1/i)).toHaveValue("5.5");

    await user.type(screen.getByLabelText(/clipboard item text/i), "Item Class: Quivers\nRarity: Rare");
    await user.click(screen.getByRole("button", { name: /analyze quiver/i }));

    await screen.findByText("Primed Quiver");
    const body = JSON.parse(fetchMock.mock.calls[0][1].body as string);
    expect(body.current_valuation_evidence).toEqual({
      strategy: "STRICT",
      notes: expect.stringContaining("User-entered manual comparable"),
      observations: [
        expect.objectContaining({
          amount: "5.5",
          currency_asset_id: DIVINE_ASSET_ID,
          external_listing_id: "current-listing-1",
          item_summary: "manual current comparable"
        })
      ]
    });
    expect(body.outcome_valuation_evidence).toEqual([]);
  });

  it("edits, removes, previews, and resubmits current-item manual valuation evidence", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => manualPreviewResponse()
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => quiverResponse
      });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<AdvisorWorkbench />);
    await openAdvancedTools(user);
    await user.type(screen.getByLabelText(/listing amount/i), "100");
    await user.selectOptions(screen.getAllByLabelText(/^currency$/i)[0], EXALTED_ASSET_ID);
    await user.type(screen.getByLabelText(/listing id/i), "edit-me");
    await user.click(screen.getByRole("button", { name: /add observation/i }));

    await user.clear(screen.getByLabelText(/listing amount/i));
    await user.type(screen.getByLabelText(/listing amount/i), "200");
    await user.selectOptions(screen.getAllByLabelText(/^currency$/i)[0], EXALTED_ASSET_ID);
    await user.type(screen.getByLabelText(/listing id/i), "remove-me");
    await user.click(screen.getByRole("button", { name: /add observation/i }));

    await user.clear(screen.getByLabelText(/current item observations amount 1/i));
    await user.type(screen.getByLabelText(/current item observations amount 1/i), "120");
    await user.click(screen.getAllByRole("button", { name: /remove/i })[1]);
    await user.click(screen.getByRole("button", { name: /preview valuation evidence/i }));

    expect(await screen.findByText("Current Item Valuation")).toBeInTheDocument();
    expect(screen.getByText("Ready")).toBeInTheDocument();
    expect(screen.getAllByText("120 Ex").length).toBeGreaterThan(0);
    const previewBody = JSON.parse(fetchMock.mock.calls[0][1].body as string);
    expect(previewBody.league).toBe(DEFAULT_LEAGUE);
    expect(previewBody.evidence.observations).toEqual([
      expect.objectContaining({
        amount: "120",
        external_listing_id: "edit-me"
      })
    ]);

    await user.type(screen.getByLabelText(/clipboard item text/i), "Item Class: Quivers\nRarity: Rare");
    await user.click(screen.getByRole("button", { name: /analyze quiver/i }));
    await screen.findByText("Primed Quiver");
    expect(screen.getByText(/1 prepared for next rerun; 0 saved locally/i)).toBeInTheDocument();
    expect(screen.getByText(/saved workspace evidence and selected dataset ids do not affect advisor output/i)).toBeInTheDocument();
    const analyzeBody = JSON.parse(fetchMock.mock.calls[1][1].body as string);
    expect(analyzeBody.current_valuation_evidence.observations).toEqual([
      expect.objectContaining({
        amount: "120",
        external_listing_id: "edit-me"
      })
    ]);
    expect(JSON.stringify(analyzeBody)).not.toContain("remove-me");
  });

  it("loads and saves persisted current-item valuation evidence without auto-submitting it", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          workspace_version: "dc-manual-valuation-workspace-v1",
          records: [
            {
              evidence_id: "persisted-current-listing",
              subject_id: "current",
              subject_type: "CURRENT_ITEM",
              outcome_id: null,
              league: DEFAULT_LEAGUE,
              strategy: "STRICT",
              amount: "140",
              currency_asset_id: EXALTED_ASSET_ID,
              external_listing_id: "persisted-current-listing",
              observed_at: "2026-08-13T10:00:00Z",
              item_summary: "synthetic persisted current comparable",
              notes: "synthetic test-only persisted valuation evidence",
              created_at: "2026-08-13T10:00:00Z",
              updated_at: "2026-08-13T10:00:00Z"
            }
          ],
          persistence: {
            storage_version: "dc-manual-valuation-workspace-storage-v1",
            storage_mode: "FILE",
            persistence_enabled: true,
            loaded_record_count: 1,
            skipped_record_count: 0,
            warnings: []
          },
          warnings: []
        })
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => quiverResponse
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          workspace_version: "dc-manual-valuation-workspace-v1",
          status: "UPDATED",
          record: {
            evidence_id: "persisted-current-listing",
            subject_id: "current",
            subject_type: "CURRENT_ITEM",
            outcome_id: null,
            league: DEFAULT_LEAGUE,
            strategy: "STRICT",
            amount: "145",
            currency_asset_id: EXALTED_ASSET_ID,
            external_listing_id: "persisted-current-listing",
            observed_at: "2026-08-13T10:00:00Z",
            item_summary: "synthetic persisted current comparable",
            notes: "synthetic test-only persisted valuation evidence",
            created_at: "2026-08-13T10:00:00Z",
            updated_at: "2026-08-13T10:01:00Z"
          },
          persistence: {
            storage_version: "dc-manual-valuation-workspace-storage-v1",
            storage_mode: "FILE",
            persistence_enabled: true,
            loaded_record_count: 1,
            skipped_record_count: 0,
            warnings: []
          },
          warnings: []
        })
      });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<AdvisorWorkbench />);
    await openAdvancedTools(user);
    await user.click(screen.getByRole("button", { name: /load persisted evidence/i }));
    expect(await screen.findByText(/loaded 1 persisted observation/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/current item observations amount 1/i)).toHaveValue("140");

    await user.type(screen.getByLabelText(/clipboard item text/i), "Item Class: Quivers\nRarity: Rare");
    await user.click(screen.getByRole("button", { name: /analyze quiver/i }));
    await screen.findByText("Primed Quiver");
    expect(screen.getByText(/1 prepared for next rerun; 1 saved locally/i)).toBeInTheDocument();
    expect(screen.getByText(/saved workspace evidence and selected dataset ids do not affect advisor output/i)).toBeInTheDocument();
    const analyzeBody = JSON.parse(fetchMock.mock.calls[1][1].body as string);
    expect(analyzeBody.current_valuation_evidence.observations).toEqual([
      expect.objectContaining({
        amount: "140",
        external_listing_id: "persisted-current-listing"
      })
    ]);
    expect(JSON.stringify(analyzeBody)).not.toContain("evidence_id");

    await openAdvancedTools(user);
    await user.clear(screen.getByLabelText(/current item observations amount 1/i));
    await user.type(screen.getByLabelText(/current item observations amount 1/i), "145");
    await user.click(screen.getByRole("button", { name: /save subject evidence/i }));
    await screen.findByText(/saved 1 observation locally/i);
    expect(fetchMock.mock.calls[2][0]).toContain(
      "/api/v1/advisor/manual-valuation/workspace/evidence/persisted-current-listing"
    );
    const updateBody = JSON.parse(fetchMock.mock.calls[2][1].body as string);
    expect(updateBody.record).toEqual(expect.objectContaining({ subject_id: "current", amount: "145" }));
  });

  it("keeps persisted outcome valuation evidence isolated from current-item evidence", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => quiverResponse
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          workspace_version: "dc-manual-valuation-workspace-v1",
          records: [
            {
              evidence_id: "persisted-outcome-2",
              subject_id: "outcome:outcome-2",
              subject_type: "HYPOTHETICAL_OUTCOME",
              outcome_id: "outcome-2",
              league: DEFAULT_LEAGUE,
              strategy: "STRICT",
              amount: "155",
              currency_asset_id: EXALTED_ASSET_ID,
              external_listing_id: "persisted-outcome-2",
              observed_at: "2026-08-13T10:00:00Z",
              item_summary: "synthetic persisted outcome comparable",
              notes: "synthetic test-only persisted valuation evidence",
              created_at: "2026-08-13T10:00:00Z",
              updated_at: "2026-08-13T10:00:00Z"
            }
          ],
          persistence: {
            storage_version: "dc-manual-valuation-workspace-storage-v1",
            storage_mode: "FILE",
            persistence_enabled: true,
            loaded_record_count: 1,
            skipped_record_count: 0,
            warnings: []
          },
          warnings: []
        })
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ status: "DELETED", deleted_count: 1, warnings: [] })
      });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<AdvisorWorkbench />);
    await user.type(screen.getByLabelText(/clipboard item text/i), "Item Class: Quivers\nRarity: Rare");
    await user.click(screen.getByRole("button", { name: /analyze quiver/i }));
    await screen.findByText("Primed Quiver");
    await openAdvancedTools(user);

    await user.selectOptions(screen.getByLabelText(/evidence subject/i), "outcome");
    await user.selectOptions(screen.getByLabelText(/^Outcome ID$/i), "outcome-2");
    await user.click(screen.getByRole("button", { name: /load persisted evidence/i }));
    expect(await screen.findByText(/loaded 1 persisted observation/i)).toBeInTheDocument();
    expect(screen.queryByText("Current item observations amount 1")).not.toBeInTheDocument();
    expect(screen.getByLabelText(/outcome outcome-2 observations amount 1/i)).toHaveValue("155");
    expect(fetchMock.mock.calls[1][0]).toContain("subject_id=outcome%3Aoutcome-2");

    await user.click(screen.getByRole("button", { name: /remove/i }));
    await waitFor(() => expect(fetchMock.mock.calls[2][0]).toContain("persisted-outcome-2"));
  });

  it("sends an explicit empirical dataset ID only when the operator supplies one", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => quiverResponse
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<AdvisorWorkbench />);
    await user.type(screen.getByLabelText(/clipboard item text/i), "Item Class: Quivers\nRarity: Rare");
    await user.type(screen.getByLabelText(/empirical evidence dataset/i), "api-registered-empirical-probability");
    await user.click(screen.getByRole("button", { name: /analyze quiver/i }));

    await screen.findByText("Primed Quiver");
    const body = JSON.parse(fetchMock.mock.calls[0][1].body as string);
    expect(body.empirical_probability_dataset_version).toBe("api-registered-empirical-probability");
  });

  it("sends bankroll and risk context to the backend without frontend decision logic", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => quiverResponse
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<AdvisorWorkbench />);
    await user.type(screen.getByLabelText(/clipboard item text/i), "Item Class: Quivers\nRarity: Rare");
    await user.type(screen.getByLabelText(/bankroll in exalted units/i), "250");
    await user.selectOptions(screen.getByLabelText(/risk profile/i), "CONSERVATIVE");
    await user.click(screen.getByRole("button", { name: /analyze quiver/i }));

    await screen.findByText("Primed Quiver");
    const body = JSON.parse(fetchMock.mock.calls[0][1].body as string);
    expect(body.bankroll).toEqual({ amount: "250", unit: "EXALTED_ECONOMIC_UNIT" });
    expect(body.risk_profile).toBe("CONSERVATIVE");
    expect(screen.getByText(/next rerun includes 250 ex bankroll and conservative risk profile/i)).toBeInTheDocument();
    expect(screen.getAllByText("No Recommendation").length).toBeGreaterThan(0);
  });

  it("adds outcome manual comparable observations and re-runs analysis with outcome IDs", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => quiverResponse
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => valuedQuiverResponse
      });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<AdvisorWorkbench />);
    await user.type(screen.getByLabelText(/clipboard item text/i), "Item Class: Quivers\nRarity: Rare");
    await user.click(screen.getByRole("button", { name: /analyze quiver/i }));
    await screen.findByText("Primed Quiver");
    await openAdvancedTools(user);

    await user.selectOptions(screen.getByLabelText(/evidence subject/i), "outcome");
    await user.selectOptions(screen.getByLabelText(/^Outcome ID$/i), "outcome-2");
    await user.clear(screen.getByLabelText(/listing amount/i));
    await user.type(screen.getByLabelText(/listing amount/i), "110");
    await user.selectOptions(screen.getByLabelText(/currency/i), EXALTED_ASSET_ID);
    await user.type(screen.getByLabelText(/evidence notes/i), "manual outcome comparable");
    await user.click(screen.getByRole("button", { name: /add observation/i }));
    expect(screen.getByText("Outcome outcome-2 observations")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /re-run analysis/i }));

    await screen.findByText("Scenario Ready");
    expect(screen.getByText("Median: 110 Ex")).toBeInTheDocument();
    const body = JSON.parse(fetchMock.mock.calls[1][1].body as string);
    expect(body.outcome_valuation_evidence).toEqual([
      {
        outcome_id: "outcome-2",
        evidence: {
          strategy: "STRICT",
          notes: "User-entered manual outcome comparable listing evidence.",
          observations: [
            expect.objectContaining({
              amount: "110",
              currency_asset_id: EXALTED_ASSET_ID,
              notes: "manual outcome comparable"
            })
          ]
        }
      }
    ]);
  });

  it("targets outcome valuation readiness blockers without auto-submitting saved evidence", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => quiverResponse
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () =>
          manualPreviewResponse({
            subject_id: "outcome:outcome-2",
            subject_type: "HYPOTHETICAL_OUTCOME",
            outcome_id: "outcome-2",
            evidence_set_id: "manual-preview-outcome-2",
            estimated_value: { amount: "110", unit: "EXALTED_ECONOMIC_UNIT" },
            plausible_low: { amount: "110", unit: "EXALTED_ECONOMIC_UNIT" },
            plausible_high: { amount: "110", unit: "EXALTED_ECONOMIC_UNIT" }
          })
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          workspace_version: "dc-manual-valuation-workspace-v1",
          status: "SAVED",
          evidence_id: "persisted-outcome-2",
          record: {
            evidence_id: "persisted-outcome-2",
            subject_id: "outcome:outcome-2",
            subject_type: "HYPOTHETICAL_OUTCOME",
            outcome_id: "outcome-2",
            league: DEFAULT_LEAGUE,
            strategy: "STRICT",
            amount: "110",
            currency_asset_id: EXALTED_ASSET_ID,
            external_listing_id: "outcome-2-listing",
            observed_at: "2026-08-13T10:00:00Z",
            item_summary: "synthetic targeted outcome comparable",
            notes: "synthetic test-only outcome valuation evidence",
            created_at: "2026-08-13T10:00:00Z",
            updated_at: "2026-08-13T10:00:00Z"
          },
          persistence: {
            storage_version: "dc-manual-valuation-workspace-storage-v1",
            storage_mode: "FILE",
            persistence_enabled: true,
            loaded_record_count: 1,
            skipped_record_count: 0,
            warnings: []
          },
          warnings: []
        })
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => valuedQuiverResponse
      });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<AdvisorWorkbench />);
    await user.type(screen.getByLabelText(/clipboard item text/i), "Item Class: Quivers\nRarity: Rare");
    await user.click(screen.getByRole("button", { name: /analyze quiver/i }));
    await screen.findByText("Primed Quiver");

    const outcomeButtons = screen.getAllByRole("button", {
      name: /add outcome valuation evidence for orb of annulment outcome/i
    });
    expect(outcomeButtons).toHaveLength(6);
    expect(
      screen.queryByRole("button", { name: /add outcome valuation evidence for exalted orb outcome/i })
    ).not.toBeInTheDocument();

    await user.click(outcomeButtons[1]);
    await waitFor(() => expect(screen.getByLabelText(/^Outcome ID$/i)).toHaveValue("outcome-2"));
    expect(screen.getByLabelText(/evidence subject/i)).toHaveValue("outcome");
    expect(screen.getByLabelText("Targeted outcome valuation progress")).toHaveTextContent(
      "0/6 blocked outcomes have saved local evidence"
    );
    expect(screen.getByLabelText("Targeted outcome valuation progress")).toHaveTextContent(
      "Current item valuation: Missing"
    );

    await user.clear(screen.getByLabelText(/listing amount/i));
    await user.type(screen.getByLabelText(/listing amount/i), "110");
    await user.selectOptions(screen.getAllByLabelText(/^currency$/i)[0], EXALTED_ASSET_ID);
    await user.type(screen.getByLabelText(/listing id/i), "outcome-2-listing");
    await user.type(screen.getByLabelText(/evidence notes/i), "synthetic test-only outcome valuation evidence");
    await user.click(screen.getByRole("button", { name: /add observation/i }));
    await user.click(screen.getByRole("button", { name: /preview valuation evidence/i }));
    expect(await screen.findByText("Outcome outcome-2 Valuation")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /save subject evidence/i }));
    expect(await screen.findByText(/saved 1 observation locally/i)).toBeInTheDocument();
    expect(screen.getByLabelText("Targeted outcome valuation progress")).toHaveTextContent(
      "1/6 blocked outcomes have saved local evidence"
    );
    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(screen.getByText("Analysis Partial")).toBeInTheDocument();
    expect(screen.queryByText("Scenario Ready")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /re-run analysis/i }));
    await screen.findByText("Scenario Ready");
    const previewBody = JSON.parse(fetchMock.mock.calls[1][1].body as string);
    const saveBody = JSON.parse(fetchMock.mock.calls[2][1].body as string);
    const rerunBody = JSON.parse(fetchMock.mock.calls[3][1].body as string);
    expect(previewBody).toEqual(expect.objectContaining({ subject_id: "outcome:outcome-2", outcome_id: "outcome-2" }));
    expect(saveBody.record).toEqual(
      expect.objectContaining({ subject_id: "outcome:outcome-2", outcome_id: "outcome-2" })
    );
    expect(rerunBody.outcome_valuation_evidence).toEqual([
      {
        outcome_id: "outcome-2",
        evidence: {
          strategy: "STRICT",
          notes: "User-entered manual outcome comparable listing evidence.",
          observations: [
            expect.objectContaining({
              amount: "110",
              currency_asset_id: EXALTED_ASSET_ID,
              external_listing_id: "outcome-2-listing"
            })
          ]
        }
      }
    ]);
    expect(JSON.stringify(rerunBody)).not.toContain("persisted-outcome-2");
  });

  it("previews outcome manual valuation evidence without leaking it to the current item subject", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => quiverResponse
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () =>
          manualPreviewResponse({
            subject_id: "outcome:outcome-2",
            subject_type: "HYPOTHETICAL_OUTCOME",
            outcome_id: "outcome-2",
            evidence_set_id: "manual-preview-outcome-2",
            estimated_value: { amount: "110", unit: "EXALTED_ECONOMIC_UNIT" },
            plausible_low: { amount: "110", unit: "EXALTED_ECONOMIC_UNIT" },
            plausible_high: { amount: "110", unit: "EXALTED_ECONOMIC_UNIT" },
            comparable_results: [
              {
                comparable_id: "manual-preview-outcome-2:0",
                external_listing_id: null,
                listing_price: "110",
                listing_currency_asset_id: EXALTED_ASSET_ID,
                normalized_value: { amount: "110", unit: "EXALTED_ECONOMIC_UNIT" },
                economy_freshness: "FRESH",
                economy_snapshot_id: "economy-snapshot-currency",
                observed_at: "2026-08-13T10:00:00Z",
                warnings: []
              }
            ]
          })
      });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<AdvisorWorkbench />);
    await user.type(screen.getByLabelText(/clipboard item text/i), "Item Class: Quivers\nRarity: Rare");
    await user.click(screen.getByRole("button", { name: /analyze quiver/i }));
    await screen.findByText("Primed Quiver");
    await openAdvancedTools(user);

    await user.selectOptions(screen.getByLabelText(/evidence subject/i), "outcome");
    await user.selectOptions(screen.getByLabelText(/^Outcome ID$/i), "outcome-2");
    await user.clear(screen.getByLabelText(/listing amount/i));
    await user.type(screen.getByLabelText(/listing amount/i), "110");
    await user.selectOptions(screen.getAllByLabelText(/^currency$/i)[0], EXALTED_ASSET_ID);
    await user.click(screen.getByRole("button", { name: /add observation/i }));
    await user.click(screen.getByRole("button", { name: /preview valuation evidence/i }));

    expect(await screen.findByText("Outcome outcome-2 Valuation")).toBeInTheDocument();
    const previewBody = JSON.parse(fetchMock.mock.calls[1][1].body as string);
    expect(previewBody.subject_id).toBe("outcome:outcome-2");
    expect(previewBody.subject_type).toBe("HYPOTHETICAL_OUTCOME");
    expect(previewBody.outcome_id).toBe("outcome-2");
    expect(previewBody.evidence.observations).toEqual([
      expect.objectContaining({
        amount: "110",
        currency_asset_id: EXALTED_ASSET_ID
      })
    ]);
  });

  it("keeps incomplete manual valuation evidence local instead of sending an empty observation", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<AdvisorWorkbench />);
    await openAdvancedTools(user);
    await user.click(screen.getByRole("button", { name: /add observation/i }));

    expect(screen.getByText("Listing amount is required.")).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("shows API errors without fabricating analysis", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 400,
        json: async () => ({ detail: { message: "Clipboard text is malformed." } })
      })
    );
    const user = userEvent.setup();

    render(<AdvisorWorkbench />);
    await user.type(screen.getByLabelText(/clipboard item text/i), "bad item");
    await user.click(screen.getByRole("button", { name: /analyze quiver/i }));

    await waitFor(() => expect(screen.getByText("Clipboard text is malformed.")).toBeInTheDocument());
    expect(screen.queryByText("Primed Quiver")).not.toBeInTheDocument();
  });

  it("records, reviews, and exports one manual craft observation", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => quiverResponse
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          raw_record_id: "manual-craft-observation-test",
          classification: {
            method: "MANUAL",
            outcome_id: "outcome-1",
            reason: "User explicitly selected the outcome.",
            warnings: []
          },
          before_item_fingerprint: "before-fingerprint",
          after_item_fingerprint: "after-fingerprint",
          export_record: {
            raw_record_id: "manual-craft-observation-test",
            action_id: "dc:poe2:craft-action:orb-of-annulment",
            source_outcome_set_id: "manual-recorder:dc:poe2:craft-action:orb-of-annulment",
            item_class: "Quivers",
            league: DEFAULT_LEAGUE,
            observed_at: "2026-08-13T10:00:00Z",
            source_id: "browser-manual-recorder-session",
            source_type: "MANUAL_RESEARCH",
            outcome_id: "outcome-1",
            unclassified: false,
            classification_method: "MANUAL"
          },
          warnings: ["Observation does not make probability evidence complete by itself."]
        })
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          workspace_version: "dc-observation-workspace-v1",
          status: "SAVED",
          raw_record_id: "manual-craft-observation-test",
          entry: {
            raw_record_id: "manual-craft-observation-test",
            record: {
              raw_record_id: "manual-craft-observation-test",
              outcome_id: "outcome-1",
              classification_method: "MANUAL"
            },
            decision: {
              raw_record_id: "manual-craft-observation-test",
              status: "PENDING",
              reviewed_at: null,
              note: null,
              reviewer_id: null
            },
            summary: {
              raw_record_id: "manual-craft-observation-test",
              review_status: "PENDING",
              outcome_id: "outcome-1",
              unclassified: false,
              synthetic: false,
              classification_method: "MANUAL",
              warnings: []
            }
          },
          persistence: {
            storage_version: "dc-observation-workspace-storage-v1",
            storage_mode: "FILE",
            persistence_enabled: true,
            loaded_record_count: 1,
            loaded_decision_count: 1,
            skipped_entry_count: 0,
            warnings: []
          },
          warnings: ["Stored observation remains pending until explicitly reviewed."]
        })
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          recorder_version: "dc-observation-recorder-v1",
          exported_at: "2026-08-13T10:01:00Z",
          observations: [
            {
              raw_record_id: "manual-craft-observation-test",
              outcome_id: "outcome-1",
              unclassified: false
            }
          ],
          warnings: ["Recorder exports are raw observations; import/readiness gates still apply."]
        })
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          review_version: "dc-observation-review-v1",
          records: [
            {
              raw_record_id: "manual-craft-observation-test",
              status: "PENDING",
              duplicate: false,
              valid_for_import: true,
              exported: false,
              classification_method: "MANUAL",
              outcome_id: "outcome-1",
              unclassified: false,
              synthetic: false,
              action_id: "dc:poe2:craft-action:orb-of-annulment",
              source_outcome_set_id: "manual-recorder:dc:poe2:craft-action:orb-of-annulment",
              warnings: ["Manual classification remains manual evidence after curation."]
            }
          ],
          accepted_export: {
            review_version: "dc-observation-review-v1",
            exported_at: "2026-08-13T10:02:00Z",
            observations: [],
            warnings: []
          },
          review_manifest: {
            review_version: "dc-observation-review-v1",
            generated_at: "2026-08-13T10:02:00Z",
            accepted_count: 0,
            rejected_count: 0,
            pending_count: 1,
            duplicate_count: 0,
            records: []
          },
          warnings: []
        })
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          review_version: "dc-observation-review-v1",
          records: [
            {
              raw_record_id: "manual-craft-observation-test",
              status: "ACCEPTED",
              duplicate: false,
              valid_for_import: true,
              exported: true,
              classification_method: "MANUAL",
              outcome_id: "outcome-1",
              unclassified: false,
              synthetic: false,
              action_id: "dc:poe2:craft-action:orb-of-annulment",
              source_outcome_set_id: "manual-recorder:dc:poe2:craft-action:orb-of-annulment",
              warnings: ["Manual classification remains manual evidence after curation."]
            }
          ],
          accepted_export: {
            review_version: "dc-observation-review-v1",
            exported_at: "2026-08-13T10:03:00Z",
            observations: [
              {
                raw_record_id: "manual-craft-observation-test",
                outcome_id: "outcome-1",
                unclassified: false,
                classification_method: "MANUAL"
              }
            ],
            warnings: []
          },
          review_manifest: {
            review_version: "dc-observation-review-v1",
            generated_at: "2026-08-13T10:03:00Z",
            accepted_count: 1,
            rejected_count: 0,
            pending_count: 0,
            duplicate_count: 0,
            records: [
              {
                raw_record_id: "manual-craft-observation-test",
                status: "ACCEPTED",
                note: "reviewed in browser"
              }
            ]
          },
          warnings: []
        })
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          build_version: "dc-curated-observation-import-v1",
          built_at: "2026-08-13T10:04:00Z",
          source_record_count: 1,
          imported_record_count: 1,
          accepted_record_count: 1,
          duplicate_record_count: 0,
          unclassified_record_count: 0,
          invalid_record_count: 0,
          dataset_count: 1,
          dataset_ids: ["empirical-probability-browser-test"],
          datasets: [
            {
              dataset_id: "empirical-probability-browser-test",
              observations: [{ outcome_id: "outcome-1", observed_count: 1, raw_record_ids: ["manual-craft-observation-test"] }]
            }
          ],
          rejected_records: [],
          warnings: ["Dataset build does not activate probability evidence or make Advisor EV-ready by itself."]
        })
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          registry_version: "dc-empirical-dataset-registry-v1",
          status: "REGISTERED",
          dataset_id: "empirical-probability-browser-test",
          persistence: {
            storage_version: "dc-empirical-dataset-registry-storage-v1",
            storage_mode: "FILE",
            persistence_enabled: true,
            loaded_dataset_count: 1,
            skipped_dataset_count: 0,
            warnings: []
          },
          dataset: {
            dataset_id: "empirical-probability-browser-test",
            action_id: "dc:poe2:craft-action:orb-of-annulment",
            source_outcome_set_id: "manual-recorder:dc:poe2:craft-action:orb-of-annulment",
            game: "Path of Exile 2",
            league: DEFAULT_LEAGUE,
            sample_size: 1,
            unclassified_count: 0,
            outcome_count: 1,
            retrieved_at: "2026-08-13T10:04:00Z",
            synthetic: false,
            verification_status: "NEEDS_VERIFICATION",
            methodology: "browser test",
            warnings: []
          },
          warnings: []
        })
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          registry_version: "dc-empirical-dataset-registry-v1",
          persistence: {
            storage_version: "dc-empirical-dataset-registry-storage-v1",
            storage_mode: "FILE",
            persistence_enabled: true,
            loaded_dataset_count: 1,
            skipped_dataset_count: 0,
            warnings: []
          },
          datasets: [
            {
              dataset_id: "empirical-probability-browser-test",
              action_id: "dc:poe2:craft-action:orb-of-annulment",
              source_outcome_set_id: "manual-recorder:dc:poe2:craft-action:orb-of-annulment",
              game: "Path of Exile 2",
              league: DEFAULT_LEAGUE,
              sample_size: 1,
              unclassified_count: 0,
              outcome_count: 1,
              retrieved_at: "2026-08-13T10:04:00Z",
              synthetic: false,
              verification_status: "NEEDS_VERIFICATION",
              methodology: "browser test",
              warnings: []
            }
          ],
          warnings: ["Registered empirical datasets remain inactive until explicitly selected."]
        })
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => empiricalQuiverResponse
      });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<AdvisorWorkbench />);
    await user.type(screen.getByLabelText(/clipboard item text/i), "Item Class: Quivers\nRarity: Rare");
    await user.click(screen.getByRole("button", { name: /analyze quiver/i }));
    await user.click(screen.getByRole("button", { name: /collect probability evidence/i }));
    await screen.findByText("Craft Observation Recorder");

    expect(screen.getByRole("region", { name: /probability evidence progress/i })).toBeVisible();
    expect((screen.getByLabelText(/craft action/i) as HTMLSelectElement).value).toBe(
      "dc:poe2:craft-action:orb-of-annulment"
    );
    await user.selectOptions(screen.getByLabelText(/manual outcome id/i), "outcome-1");
    await user.type(screen.getByLabelText(/manual classification reason/i), "observed after craft");
    await user.type(screen.getByLabelText(/after craft clipboard text/i), "Item Class: Quivers\nRarity: Rare\nafter");
    await user.click(screen.getByRole("button", { name: /record observation/i }));

    expect(await screen.findByText("MANUAL")).toBeInTheDocument();
    expect(screen.getAllByText(/manual-cra.*n-test/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/SAVED: manual-craft-observation-test/i)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /export json/i }));
    await screen.findByText(/dc-observation-recorder-v1/i);
    const recordBody = JSON.parse(fetchMock.mock.calls[1][1].body as string);
    expect(recordBody.manual_outcome_id).toBe("outcome-1");
    expect(recordBody.manual_reason).toBe("observed after craft");
    expect(fetchMock.mock.calls[2][0]).toContain("/api/v1/observations/workspace/records");
    const exportBody = JSON.parse(fetchMock.mock.calls[3][1].body as string);
    expect(exportBody.observations).toEqual([
      expect.objectContaining({
        raw_record_id: "manual-craft-observation-test",
        classification_method: "MANUAL"
      })
    ]);

    const recorderExport = JSON.stringify({
      observations: [
        {
          raw_record_id: "manual-craft-observation-test",
          outcome_id: "outcome-1",
          unclassified: false,
          classification_method: "MANUAL"
        }
      ]
    });
    fireEvent.change(screen.getByLabelText(/recorder export json/i), { target: { value: recorderExport } });
    await user.click(screen.getByRole("button", { name: /load review batch/i }));
    expect(await screen.findByText(/manual classification remains manual evidence/i)).toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText(/review status manual-craft-observation-test/i), "ACCEPTED");
    await user.type(screen.getByLabelText(/review note manual-craft-observation-test/i), "reviewed in browser");
    await user.click(screen.getByRole("button", { name: /export accepted json/i }));
    expect((await screen.findAllByText(/dc-observation-review-v1/i)).length).toBeGreaterThanOrEqual(2);
    const reviewBody = JSON.parse(fetchMock.mock.calls[5][1].body as string);
    expect(reviewBody.decisions).toEqual([
      expect.objectContaining({
        raw_record_id: "manual-craft-observation-test",
        status: "ACCEPTED",
        note: "reviewed in browser",
        reviewer_id: "browser-observation-review-session"
      })
    ]);

    await user.click(screen.getByRole("button", { name: /build empirical datasets/i }));
    expect(await screen.findByText("Curated Import Build")).toBeInTheDocument();
    expect(screen.getAllByText(/empirical-probability-browser-test/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/does not activate probability evidence/i).length).toBeGreaterThanOrEqual(1);
    const buildBody = JSON.parse(fetchMock.mock.calls[6][1].body as string);
    expect(buildBody.accepted_export.observations).toEqual([
      expect.objectContaining({
        raw_record_id: "manual-craft-observation-test",
        classification_method: "MANUAL"
      })
    ]);

    await user.click(screen.getByRole("button", { name: /register first dataset/i }));
    expect(await screen.findByText(/REGISTERED: empirical-probability-browser-test/i)).toBeInTheDocument();
    expect(screen.getAllByText(/registration does not activate probability evidence/i).length).toBeGreaterThan(0);
    expect((screen.getByLabelText(/empirical evidence dataset/i) as HTMLInputElement).value).toBe("");
    expect(screen.getByText(/registry persistence: FILE active - 1 loaded/i)).toBeInTheDocument();
    expect(screen.getAllByText(/sample 1/i).length).toBeGreaterThan(0);
    expect(fetchMock.mock.calls[7][0]).toContain("/api/v1/observations/empirical-datasets/register");
    expect(fetchMock.mock.calls[8][0]).toContain("/api/v1/observations/empirical-datasets");
    expect(fetchMock.mock.calls.filter((call) => String(call[0]).includes("/api/v1/advisor/analyze"))).toHaveLength(1);

    await user.click(screen.getByRole("button", { name: /use dataset for next analysis/i }));
    expect((screen.getByLabelText(/empirical evidence dataset/i) as HTMLInputElement).value).toBe(
      "empirical-probability-browser-test"
    );
    await user.click(screen.getByRole("button", { name: /re-run analysis/i }));
    await screen.findByText(/selected empirical probability dataset supplied usable evidence/i);
    expect(fetchMock.mock.calls[9][0]).toContain("/api/v1/advisor/analyze");
    const rerunBody = JSON.parse(fetchMock.mock.calls[9][1].body as string);
    expect(rerunBody.empirical_probability_dataset_version).toBe("empirical-probability-browser-test");
    expect(screen.queryByRole("button", { name: /collect probability evidence/i })).not.toBeInTheDocument();
  });

  it("loads persisted observation workspace evidence for review after refresh", async () => {
    const workspaceEntry = {
      raw_record_id: "manual-craft-observation-reloaded",
      record: {
        raw_record_id: "manual-craft-observation-reloaded",
        outcome_id: "outcome-1",
        unclassified: false,
        classification_method: "MANUAL"
      },
      decision: {
        raw_record_id: "manual-craft-observation-reloaded",
        status: "ACCEPTED",
        reviewed_at: "2026-08-13T10:03:00Z",
        note: "already reviewed",
        reviewer_id: "browser-observation-review-session"
      },
      summary: {
        raw_record_id: "manual-craft-observation-reloaded",
        review_status: "ACCEPTED",
        outcome_id: "outcome-1",
        unclassified: false,
        synthetic: false,
        classification_method: "MANUAL",
        note: "already reviewed",
        warnings: []
      }
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => quiverResponse
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          workspace_version: "dc-observation-workspace-v1",
          entries: [workspaceEntry],
          persistence: {
            storage_version: "dc-observation-workspace-storage-v1",
            storage_mode: "FILE",
            persistence_enabled: true,
            loaded_record_count: 1,
            loaded_decision_count: 1,
            skipped_entry_count: 0,
            warnings: []
          },
          warnings: []
        })
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          review_version: "dc-observation-review-v1",
          records: [
            {
              raw_record_id: "manual-craft-observation-reloaded",
              status: "ACCEPTED",
              duplicate: false,
              valid_for_import: true,
              exported: true,
              classification_method: "MANUAL",
              outcome_id: "outcome-1",
              unclassified: false,
              synthetic: false,
              action_id: "dc:poe2:craft-action:orb-of-annulment",
              source_outcome_set_id: "manual-recorder:dc:poe2:craft-action:orb-of-annulment",
              warnings: ["Manual classification remains manual evidence after curation."]
            }
          ],
          accepted_export: {
            review_version: "dc-observation-review-v1",
            observations: [
              {
                raw_record_id: "manual-craft-observation-reloaded",
                outcome_id: "outcome-1",
                classification_method: "MANUAL"
              }
            ],
            warnings: []
          },
          review_manifest: {
            review_version: "dc-observation-review-v1",
            records: []
          },
          warnings: []
        })
      });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<AdvisorWorkbench />);
    await user.type(screen.getByLabelText(/clipboard item text/i), "Item Class: Quivers\nRarity: Rare");
    await user.click(screen.getByRole("button", { name: /analyze quiver/i }));
    await openAdvancedTools(user);
    await screen.findByText("Observation Review");

    await user.click(screen.getByRole("button", { name: /load persisted workspace/i }));

    expect(await screen.findByText(/workspace persistence: FILE active - 1 records - 1 decisions/i)).toBeInTheDocument();
    expect(screen.getAllByText(/manual-cra.*loaded/i).length).toBeGreaterThan(0);
    expect((screen.getByLabelText(/review status manual-craft-observation-reloaded/i) as HTMLSelectElement).value).toBe(
      "ACCEPTED"
    );
    expect(fetchMock.mock.calls[1][0]).toContain("/api/v1/observations/workspace");
  });

  it("exports and restores a persisted observation workspace backup", async () => {
    const workspaceEntry = {
      raw_record_id: "manual-craft-observation-backup",
      record: {
        raw_record_id: "manual-craft-observation-backup",
        outcome_id: "outcome-1",
        unclassified: false,
        classification_method: "MANUAL"
      },
      decision: {
        raw_record_id: "manual-craft-observation-backup",
        status: "ACCEPTED",
        reviewed_at: "2026-08-13T10:03:00Z",
        note: "backup reviewed",
        reviewer_id: "browser-observation-review-session"
      },
      summary: {
        raw_record_id: "manual-craft-observation-backup",
        review_status: "ACCEPTED",
        outcome_id: "outcome-1",
        unclassified: false,
        synthetic: false,
        classification_method: "MANUAL",
        note: "backup reviewed",
        warnings: []
      }
    };
    const backup = {
      workspace_version: "dc-observation-workspace-v1",
      storage_version: "dc-observation-workspace-storage-v1",
      records: [workspaceEntry.record],
      decisions: [workspaceEntry.decision]
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => quiverResponse
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          workspace_version: "dc-observation-workspace-v1",
          backup,
          persistence: {
            storage_version: "dc-observation-workspace-storage-v1",
            storage_mode: "FILE",
            persistence_enabled: true,
            loaded_record_count: 1,
            loaded_decision_count: 1,
            skipped_entry_count: 0,
            warnings: []
          },
          warnings: []
        })
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          workspace_version: "dc-observation-workspace-v1",
          restore: {
            status: "RESTORED",
            mode: "MERGE",
            records_received: 1,
            records_imported: 1,
            records_already_present: 0,
            records_conflicting: 0,
            records_invalid: 0,
            decisions_received: 1,
            decisions_imported: 1,
            decisions_invalid: 0,
            resulting_record_count: 1,
            resulting_decision_count: 1,
            warnings: []
          },
          entries: [workspaceEntry],
          persistence: {
            storage_version: "dc-observation-workspace-storage-v1",
            storage_mode: "FILE",
            persistence_enabled: true,
            loaded_record_count: 1,
            loaded_decision_count: 1,
            skipped_entry_count: 0,
            warnings: []
          },
          warnings: []
        })
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          review_version: "dc-observation-review-v1",
          records: [
            {
              raw_record_id: "manual-craft-observation-backup",
              status: "ACCEPTED",
              duplicate: false,
              valid_for_import: true,
              exported: true,
              classification_method: "MANUAL",
              outcome_id: "outcome-1",
              unclassified: false,
              synthetic: false,
              action_id: "dc:poe2:craft-action:orb-of-annulment",
              source_outcome_set_id: "manual-recorder:dc:poe2:craft-action:orb-of-annulment",
              warnings: []
            }
          ],
          accepted_export: {
            review_version: "dc-observation-review-v1",
            observations: [workspaceEntry.record],
            warnings: []
          },
          review_manifest: {
            review_version: "dc-observation-review-v1",
            records: []
          },
          warnings: []
        })
      });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<AdvisorWorkbench />);
    await user.type(screen.getByLabelText(/clipboard item text/i), "Item Class: Quivers\nRarity: Rare");
    await user.click(screen.getByRole("button", { name: /analyze quiver/i }));
    await openAdvancedTools(user);
    await screen.findByText("Observation Review");

    await user.click(screen.getByRole("button", { name: /export workspace backup/i }));
    const backupTextarea = (await screen.findByLabelText(/workspace backup json/i)) as HTMLTextAreaElement;
    expect(backupTextarea.value).toContain("manual-craft-observation-backup");

    await user.click(screen.getByRole("button", { name: /restore workspace backup/i }));

    expect(await screen.findByText(/RESTORED: 1 records imported/i)).toBeInTheDocument();
    expect(screen.getAllByText(/manual-cra.*backup/i).length).toBeGreaterThan(0);
    expect(fetchMock.mock.calls[1][0]).toContain("/api/v1/observations/workspace/backup");
    expect(fetchMock.mock.calls[2][0]).toContain("/api/v1/observations/workspace/restore");
    expect(JSON.parse(fetchMock.mock.calls[2][1].body as string)).toEqual({ backup, mode: "MERGE" });
  });
});
