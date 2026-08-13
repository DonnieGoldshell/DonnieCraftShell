import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  DEFAULT_AFFIX_CAPACITY_DATASET,
  DEFAULT_CRAFTING_DATASET,
  DEFAULT_GAME_DATA_DATASET,
  DEFAULT_LEAGUE,
  DIVINE_ASSET_ID,
  EXALTED_ASSET_ID,
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
    expect(screen.getAllByText("Orb of Annulment").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Exalted Orb").length).toBeGreaterThan(0);
    expect(screen.getByText("Missing price")).toBeInTheDocument();
    expect(screen.getByText("No open explicit affix slot")).toBeInTheDocument();
    expect(screen.getByText("Current Valuation Evidence Required")).toBeInTheDocument();
    expect(screen.getAllByText("Probability Evidence Required").length).toBeGreaterThan(0);
    expect(screen.getByText(/listing-derived estimates are not guaranteed sale prices/i)).toBeInTheDocument();
  });

  it("adds current-item manual comparable observations to the next advisor request", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => quiverResponse
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<AdvisorWorkbench />);
    await user.type(screen.getByLabelText(/listing amount/i), "5.5");
    await user.type(screen.getByLabelText(/listing id/i), "current-listing-1");
    await user.type(screen.getByLabelText(/listing\/item note/i), "manual current comparable");
    await user.click(screen.getByRole("button", { name: /add observation/i }));
    expect(screen.getByText("5.5 Divine Orb")).toBeInTheDocument();

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

  it("keeps incomplete manual valuation evidence local instead of sending an empty observation", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<AdvisorWorkbench />);
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
      });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<AdvisorWorkbench />);
    await user.type(screen.getByLabelText(/clipboard item text/i), "Item Class: Quivers\nRarity: Rare");
    await user.click(screen.getByRole("button", { name: /analyze quiver/i }));
    await screen.findByText("Craft Observation Recorder");

    await user.selectOptions(screen.getByLabelText(/craft action/i), "dc:poe2:craft-action:orb-of-annulment");
    await user.selectOptions(screen.getByLabelText(/manual outcome id/i), "outcome-1");
    await user.type(screen.getByLabelText(/manual classification reason/i), "observed after craft");
    await user.type(screen.getByLabelText(/after craft clipboard text/i), "Item Class: Quivers\nRarity: Rare\nafter");
    await user.click(screen.getByRole("button", { name: /record observation/i }));

    expect(await screen.findByText("MANUAL")).toBeInTheDocument();
    expect(screen.getByText(/manual-cra.*n-test/i)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /export json/i }));
    await screen.findByText(/dc-observation-recorder-v1/i);
    const recordBody = JSON.parse(fetchMock.mock.calls[1][1].body as string);
    expect(recordBody.manual_outcome_id).toBe("outcome-1");
    expect(recordBody.manual_reason).toBe("observed after craft");
    const exportBody = JSON.parse(fetchMock.mock.calls[2][1].body as string);
    expect(exportBody.observations).toEqual([
      expect.objectContaining({
        raw_record_id: "manual-craft-observation-test",
        classification_method: "MANUAL"
      })
    ]);
  });
});
