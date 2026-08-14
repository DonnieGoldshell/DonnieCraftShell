import type { components } from "./openapi";

export const DEFAULT_LEAGUE = "Runes of Aldur";
export const DEFAULT_GAME_DATA_DATASET = "poe2db-unknown-version-2026-08-12-task8c-fullx1";
export const DEFAULT_CRAFTING_DATASET = "crafting-actions-poe2-quiver-2026-08-12-research";
export const DEFAULT_AFFIX_CAPACITY_DATASET = "affix-capacity-poe2-2026-08-12-research";

export type AdvisorAnalyzeRequest = components["schemas"]["AdvisorAnalyzeRequestDto"];
export type AdvisorAnalyzeResponse = components["schemas"]["AdvisorAnalyzeResponseDto"];
export type ActionAnalysis = components["schemas"]["ActionAnalysisDto"];
export type MissingRequirement = components["schemas"]["MissingRequirementDto"];
export type ManualListingObservation = components["schemas"]["ManualListingObservationDto"];
export type ManualValuationEvidence = components["schemas"]["ManualValuationEvidenceDto"];
export type OutcomeManualValuationEvidence = components["schemas"]["OutcomeManualValuationEvidenceDto"];
export type CraftObservationRecordRequest = components["schemas"]["CraftObservationRecordRequestDto"];
export type CraftObservationRecordResponse = components["schemas"]["CraftObservationRecordResponseDto"];
export type CraftObservationExportRequest = components["schemas"]["CraftObservationExportRequestDto"];
export type CraftObservationExportResponse = components["schemas"]["CraftObservationExportResponseDto"];
export type ObservationReviewDecision = components["schemas"]["ObservationReviewDecisionDto"];
export type ObservationReviewRequest = components["schemas"]["ObservationReviewRequestDto"];
export type ObservationReviewResponse = components["schemas"]["ObservationReviewResponseDto"];
export type CuratedObservationBuildRequest = components["schemas"]["CuratedObservationBuildRequestDto"];
export type CuratedObservationBuildResponse = components["schemas"]["CuratedObservationBuildResponseDto"];

export const EXALTED_ASSET_ID = "dc:poe2:economy-asset:currency:exalted-orb";
export const DIVINE_ASSET_ID = "dc:poe2:economy-asset:currency:divine-orb";

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

export async function recordCraftObservation(
  request: CraftObservationRecordRequest
): Promise<CraftObservationRecordResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/observations/record`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(request)
  });

  if (!response.ok) {
    let message = `Observation recorder API returned ${response.status}`;
    try {
      const payload = await response.json();
      message = payload?.detail?.message ?? payload?.detail ?? message;
    } catch {
      // Keep the status-based message.
    }
    throw new Error(message);
  }

  return response.json() as Promise<CraftObservationRecordResponse>;
}

export async function exportCraftObservations(
  request: CraftObservationExportRequest
): Promise<CraftObservationExportResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/observations/export`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(request)
  });

  if (!response.ok) {
    throw new Error(`Observation export API returned ${response.status}`);
  }

  return response.json() as Promise<CraftObservationExportResponse>;
}

export async function reviewCraftObservations(request: ObservationReviewRequest): Promise<ObservationReviewResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/observations/review`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(request)
  });

  if (!response.ok) {
    let message = `Observation review API returned ${response.status}`;
    try {
      const payload = await response.json();
      message = payload?.detail?.message ?? payload?.detail ?? message;
    } catch {
      // Keep the status-based message.
    }
    throw new Error(message);
  }

  return response.json() as Promise<ObservationReviewResponse>;
}

export async function buildCuratedObservationDatasets(
  request: CuratedObservationBuildRequest
): Promise<CuratedObservationBuildResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/observations/build-empirical-datasets`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(request)
  });

  if (!response.ok) {
    let message = `Curated observation build API returned ${response.status}`;
    try {
      const payload = await response.json();
      message = payload?.detail?.message ?? payload?.detail ?? message;
    } catch {
      // Keep the status-based message.
    }
    throw new Error(message);
  }

  return response.json() as Promise<CuratedObservationBuildResponse>;
}
