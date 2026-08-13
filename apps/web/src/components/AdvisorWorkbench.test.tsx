import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  DEFAULT_AFFIX_CAPACITY_DATASET,
  DEFAULT_CRAFTING_DATASET,
  DEFAULT_GAME_DATA_DATASET,
  DEFAULT_LEAGUE,
  type AdvisorAnalyzeResponse
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
      required_materials: [{ asset_id: "dc:poe2:economy-asset:orb-of-annulment", quantity: "1" }],
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
      required_materials: [{ asset_id: "dc:poe2:economy-asset:exalted-orb", quantity: "1" }],
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

describe("AdvisorWorkbench", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

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
    expect(screen.getByText("3/3 prefixes, 3/3 suffixes")).toBeInTheDocument();
    expect(screen.getByText("Advisor Decision")).toBeInTheDocument();
    expect(screen.getAllByText("No Recommendation").length).toBeGreaterThan(0);
    expect(screen.getByText("Orb of Annulment")).toBeInTheDocument();
    expect(screen.getByText("Exalted Orb")).toBeInTheDocument();
    expect(screen.getByText("Missing price")).toBeInTheDocument();
    expect(screen.getByText("No open explicit affix slot")).toBeInTheDocument();
    expect(screen.getByText("Current Valuation Evidence Required")).toBeInTheDocument();
    expect(screen.getAllByText("Probability Evidence Required").length).toBeGreaterThan(0);
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
});
