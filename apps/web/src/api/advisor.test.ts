import { afterEach, describe, expect, it, vi } from "vitest";
import {
  DEFAULT_AFFIX_CAPACITY_DATASET,
  DEFAULT_CRAFTING_DATASET,
  DEFAULT_GAME_DATA_DATASET,
  DEFAULT_LEAGUE,
  analyzeAdvisor,
  createDefaultAdvisorRequest,
  type AdvisorAnalyzeResponse
} from "./advisor";

describe("advisor API client", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("builds explicit MVP context without silently using latest datasets", () => {
    expect(createDefaultAdvisorRequest("item text")).toEqual({
      clipboard_text: "item text",
      league: DEFAULT_LEAGUE,
      game_data_dataset_version: DEFAULT_GAME_DATA_DATASET,
      crafting_dataset_version: DEFAULT_CRAFTING_DATASET,
      affix_capacity_dataset_version: DEFAULT_AFFIX_CAPACITY_DATASET,
      outcome_valuation_evidence: []
    });
  });

  it("posts to the advisor endpoint and preserves Decimal strings in the response", async () => {
    const response: AdvisorAnalyzeResponse = {
      analysis_id: "019febcf-bf04-73e2-a845-1f2278b0ef05",
      status: "ANALYSIS_PARTIAL",
      context: {
        league: DEFAULT_LEAGUE,
        game_data_dataset_version: DEFAULT_GAME_DATA_DATASET,
        crafting_dataset_version: DEFAULT_CRAFTING_DATASET,
        affix_capacity_dataset_version: DEFAULT_AFFIX_CAPACITY_DATASET,
        economy_snapshot_ids: []
      },
      item: null,
      enrichment_summary: null,
      affix_state: null,
      actions: [
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
        reasons: ["No EV-ready craft candidate is available."],
        warnings: [],
        algorithm_version: "dc-advisor-v1"
      },
      risk_adjusted_decision: null,
      missing_requirements: [],
      warnings: [],
      provenance: []
    };
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => response
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await analyzeAdvisor(createDefaultAdvisorRequest("item text"));

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/advisor/analyze",
      expect.objectContaining({
        method: "POST",
        headers: { "Content-Type": "application/json" }
      })
    );
    expect(result.actions[0].material_cost.total?.amount).toBe("1");
  });

  it("surfaces structured API error messages", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 400,
        json: async () => ({ detail: { message: "Clipboard text is required." } })
      })
    );

    await expect(analyzeAdvisor(createDefaultAdvisorRequest(""))).rejects.toThrow("Clipboard text is required.");
  });
});
