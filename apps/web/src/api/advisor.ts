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
export type ManualValuationPreviewRequest = components["schemas"]["ManualValuationPreviewRequestDto"];
export type ManualValuationPreviewResponse = components["schemas"]["ManualValuationPreviewResponseDto"];
export type ManualValuationWorkspaceRecord = components["schemas"]["ManualValuationWorkspaceRecordDto"];
export type ManualValuationWorkspaceSaveRequest = components["schemas"]["ManualValuationWorkspaceSaveRequestDto"];
export type ManualValuationWorkspaceSaveResponse = components["schemas"]["ManualValuationWorkspaceSaveResponseDto"];
export type ManualValuationWorkspaceListResponse = components["schemas"]["ManualValuationWorkspaceListResponseDto"];
export type ManualValuationWorkspaceDeleteResponse = components["schemas"]["ManualValuationWorkspaceDeleteResponseDto"];
export type OutcomeManualValuationEvidence = components["schemas"]["OutcomeManualValuationEvidenceDto"];
export type CraftObservationRecordRequest = components["schemas"]["CraftObservationRecordRequestDto"];
export type CraftObservationRecordResponse = components["schemas"]["CraftObservationRecordResponseDto"];
export type CraftObservationExportRequest = components["schemas"]["CraftObservationExportRequestDto"];
export type CraftObservationExportResponse = components["schemas"]["CraftObservationExportResponseDto"];
export type ObservationReviewDecision = components["schemas"]["ObservationReviewDecisionDto"];
export type ObservationReviewRequest = components["schemas"]["ObservationReviewRequestDto"];
export type ObservationReviewResponse = components["schemas"]["ObservationReviewResponseDto"];
export type ObservationWorkspaceAcceptedExportResponse =
  components["schemas"]["ObservationWorkspaceAcceptedExportResponseDto"];
export type ObservationWorkspaceListResponse = components["schemas"]["ObservationWorkspaceListResponseDto"];
export type ObservationWorkspaceReviewRequest = components["schemas"]["ObservationWorkspaceReviewRequestDto"];
export type ObservationWorkspaceReviewResponse = components["schemas"]["ObservationWorkspaceReviewResponseDto"];
export type ObservationWorkspaceSaveRequest = components["schemas"]["ObservationWorkspaceSaveRequestDto"];
export type ObservationWorkspaceSaveResponse = components["schemas"]["ObservationWorkspaceSaveResponseDto"];
export type ObservationWorkspaceBackupResponse = components["schemas"]["ObservationWorkspaceBackupResponseDto"];
export type ObservationWorkspaceRestoreRequest = components["schemas"]["ObservationWorkspaceRestoreRequestDto"];
export type ObservationWorkspaceRestoreResponse = components["schemas"]["ObservationWorkspaceRestoreResponseDto"];
export type CuratedObservationBuildRequest = components["schemas"]["CuratedObservationBuildRequestDto"];
export type CuratedObservationBuildResponse = components["schemas"]["CuratedObservationBuildResponseDto"];
export type EmpiricalDatasetRegisterRequest = components["schemas"]["EmpiricalDatasetRegisterRequestDto"];
export type EmpiricalDatasetRegisterResponse = components["schemas"]["EmpiricalDatasetRegisterResponseDto"];
export type EmpiricalDatasetListResponse = components["schemas"]["EmpiricalDatasetListResponseDto"];

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

export async function previewManualValuation(
  request: ManualValuationPreviewRequest
): Promise<ManualValuationPreviewResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/advisor/manual-valuation/preview`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(request)
  });

  if (!response.ok) {
    let message = `Manual valuation preview API returned ${response.status}`;
    try {
      const payload = await response.json();
      message = payload?.detail?.message ?? payload?.detail ?? message;
    } catch {
      // Keep the status-based message.
    }
    throw new Error(message);
  }

  return response.json() as Promise<ManualValuationPreviewResponse>;
}

export async function saveManualValuationWorkspaceEvidence(
  request: ManualValuationWorkspaceSaveRequest
): Promise<ManualValuationWorkspaceSaveResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/advisor/manual-valuation/workspace/evidence`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(request)
  });

  if (!response.ok) {
    let message = `Manual valuation workspace save API returned ${response.status}`;
    try {
      const payload = await response.json();
      message = payload?.detail?.message ?? payload?.detail ?? message;
    } catch {
      // Keep the status-based message.
    }
    throw new Error(message);
  }

  return response.json() as Promise<ManualValuationWorkspaceSaveResponse>;
}

export async function updateManualValuationWorkspaceEvidence(
  evidenceId: string,
  request: ManualValuationWorkspaceSaveRequest
): Promise<ManualValuationWorkspaceSaveResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/advisor/manual-valuation/workspace/evidence/${encodeURIComponent(evidenceId)}`,
    {
      method: "PUT",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(request)
    }
  );

  if (!response.ok) {
    let message = `Manual valuation workspace update API returned ${response.status}`;
    try {
      const payload = await response.json();
      message = payload?.detail?.message ?? payload?.detail ?? message;
    } catch {
      // Keep the status-based message.
    }
    throw new Error(message);
  }

  return response.json() as Promise<ManualValuationWorkspaceSaveResponse>;
}

export async function listManualValuationWorkspaceEvidence(
  subjectId?: string
): Promise<ManualValuationWorkspaceListResponse> {
  const query = subjectId ? `?subject_id=${encodeURIComponent(subjectId)}` : "";
  const response = await fetch(`${API_BASE_URL}/api/v1/advisor/manual-valuation/workspace/evidence${query}`);

  if (!response.ok) {
    throw new Error(`Manual valuation workspace list API returned ${response.status}`);
  }

  return response.json() as Promise<ManualValuationWorkspaceListResponse>;
}

export async function deleteManualValuationWorkspaceEvidence(
  evidenceId: string
): Promise<ManualValuationWorkspaceDeleteResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/advisor/manual-valuation/workspace/evidence/${encodeURIComponent(evidenceId)}`,
    { method: "DELETE" }
  );

  if (!response.ok) {
    let message = `Manual valuation workspace delete API returned ${response.status}`;
    try {
      const payload = await response.json();
      message = payload?.detail?.message ?? payload?.detail ?? message;
    } catch {
      // Keep the status-based message.
    }
    throw new Error(message);
  }

  return response.json() as Promise<ManualValuationWorkspaceDeleteResponse>;
}

export async function clearManualValuationWorkspaceSubject(
  subjectId: string
): Promise<ManualValuationWorkspaceDeleteResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/advisor/manual-valuation/workspace/subject?subject_id=${encodeURIComponent(subjectId)}`,
    { method: "DELETE" }
  );

  if (!response.ok) {
    let message = `Manual valuation workspace clear API returned ${response.status}`;
    try {
      const payload = await response.json();
      message = payload?.detail?.message ?? payload?.detail ?? message;
    } catch {
      // Keep the status-based message.
    }
    throw new Error(message);
  }

  return response.json() as Promise<ManualValuationWorkspaceDeleteResponse>;
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

export async function saveObservationWorkspaceRecord(
  request: ObservationWorkspaceSaveRequest
): Promise<ObservationWorkspaceSaveResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/observations/workspace/records`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(request)
  });

  if (!response.ok) {
    let message = `Observation workspace save API returned ${response.status}`;
    try {
      const payload = await response.json();
      message = payload?.detail?.message ?? payload?.detail ?? message;
    } catch {
      // Keep the status-based message.
    }
    throw new Error(message);
  }

  return response.json() as Promise<ObservationWorkspaceSaveResponse>;
}

export async function listObservationWorkspace(): Promise<ObservationWorkspaceListResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/observations/workspace`);

  if (!response.ok) {
    throw new Error(`Observation workspace list API returned ${response.status}`);
  }

  return response.json() as Promise<ObservationWorkspaceListResponse>;
}

export async function reviewObservationWorkspace(
  request: ObservationWorkspaceReviewRequest
): Promise<ObservationWorkspaceReviewResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/observations/workspace/reviews`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(request)
  });

  if (!response.ok) {
    let message = `Observation workspace review API returned ${response.status}`;
    try {
      const payload = await response.json();
      message = payload?.detail?.message ?? payload?.detail ?? message;
    } catch {
      // Keep the status-based message.
    }
    throw new Error(message);
  }

  return response.json() as Promise<ObservationWorkspaceReviewResponse>;
}

export async function exportObservationWorkspaceAccepted(): Promise<ObservationWorkspaceAcceptedExportResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/observations/workspace/accepted-export`);

  if (!response.ok) {
    throw new Error(`Observation workspace accepted export API returned ${response.status}`);
  }

  return response.json() as Promise<ObservationWorkspaceAcceptedExportResponse>;
}

export async function exportObservationWorkspaceBackup(): Promise<ObservationWorkspaceBackupResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/observations/workspace/backup`);

  if (!response.ok) {
    throw new Error(`Observation workspace backup API returned ${response.status}`);
  }

  return response.json() as Promise<ObservationWorkspaceBackupResponse>;
}

export async function restoreObservationWorkspaceBackup(
  request: ObservationWorkspaceRestoreRequest
): Promise<ObservationWorkspaceRestoreResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/observations/workspace/restore`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(request)
  });

  if (!response.ok) {
    let message = `Observation workspace restore API returned ${response.status}`;
    try {
      const payload = await response.json();
      message = payload?.detail?.message ?? payload?.detail ?? message;
    } catch {
      // Keep the status-based message.
    }
    throw new Error(message);
  }

  return response.json() as Promise<ObservationWorkspaceRestoreResponse>;
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

export async function registerEmpiricalDataset(
  request: EmpiricalDatasetRegisterRequest
): Promise<EmpiricalDatasetRegisterResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/observations/empirical-datasets/register`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(request)
  });

  if (!response.ok) {
    let message = `Empirical dataset registry API returned ${response.status}`;
    try {
      const payload = await response.json();
      message = payload?.detail?.message ?? payload?.detail ?? message;
    } catch {
      // Keep the status-based message.
    }
    throw new Error(message);
  }

  return response.json() as Promise<EmpiricalDatasetRegisterResponse>;
}

export async function listEmpiricalDatasets(): Promise<EmpiricalDatasetListResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/observations/empirical-datasets`);

  if (!response.ok) {
    throw new Error(`Empirical dataset list API returned ${response.status}`);
  }

  return response.json() as Promise<EmpiricalDatasetListResponse>;
}
