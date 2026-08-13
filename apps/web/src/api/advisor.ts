import type { components } from "./openapi";

export const DEFAULT_LEAGUE = "Runes of Aldur";
export const DEFAULT_GAME_DATA_DATASET = "poe2db-unknown-version-2026-08-12-task8c-fullx1";
export const DEFAULT_CRAFTING_DATASET = "crafting-actions-poe2-quiver-2026-08-12-research";
export const DEFAULT_AFFIX_CAPACITY_DATASET = "affix-capacity-poe2-2026-08-12-research";

export type AdvisorAnalyzeRequest = components["schemas"]["AdvisorAnalyzeRequestDto"];
export type AdvisorAnalyzeResponse = components["schemas"]["AdvisorAnalyzeResponseDto"];
export type ActionAnalysis = components["schemas"]["ActionAnalysisDto"];
export type MissingRequirement = components["schemas"]["MissingRequirementDto"];

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export function createDefaultAdvisorRequest(clipboardText: string): AdvisorAnalyzeRequest {
  return {
    clipboard_text: clipboardText,
    league: DEFAULT_LEAGUE,
    game_data_dataset_version: DEFAULT_GAME_DATA_DATASET,
    crafting_dataset_version: DEFAULT_CRAFTING_DATASET,
    affix_capacity_dataset_version: DEFAULT_AFFIX_CAPACITY_DATASET,
    outcome_valuation_evidence: []
  };
}

export async function analyzeAdvisor(request: AdvisorAnalyzeRequest): Promise<AdvisorAnalyzeResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/advisor/analyze`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(request)
  });

  if (!response.ok) {
    let message = `Advisor API returned ${response.status}`;
    try {
      const payload = await response.json();
      message = payload?.detail?.message ?? payload?.detail ?? message;
    } catch {
      // Keep the status-based message.
    }
    throw new Error(message);
  }

  return response.json() as Promise<AdvisorAnalyzeResponse>;
}
