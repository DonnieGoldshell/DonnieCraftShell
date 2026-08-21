"use client";

import { FormEvent, type Dispatch, type SetStateAction, useState } from "react";
import {
  DEFAULT_AFFIX_CAPACITY_DATASET,
  DEFAULT_CRAFTING_DATASET,
  DEFAULT_GAME_DATA_DATASET,
  DEFAULT_LEAGUE,
  analyzeAdvisor,
  createDefaultAdvisorRequest,
  type AdvisorAnalyzeResponse,
  type ManualListingObservation,
  type ManualValuationEvidence,
  type OutcomeManualValuationEvidence
} from "@/api/advisor";
import { ActionTable } from "./ActionTable";
import { CraftObservationRecorderPanel } from "./CraftObservationRecorderPanel";
import { DecisionPanel } from "./DecisionPanel";
import { EvidenceReadinessPanel } from "./EvidenceReadinessPanel";
import { ItemSummary } from "./ItemSummary";
import { ManualValuationPanel } from "./ManualValuationPanel";
import { MissingRequirements } from "./MissingRequirements";
import { ObservationReviewPanel } from "./ObservationReviewPanel";
import { PlayerSummary } from "./PlayerSummary";
import { StatusBadge } from "./StatusBadge";

const PLACEHOLDER = `Item Class: Quivers
Rarity: Rare
...paste Path of Exile 2 Advanced Copy text here...`;

export function AdvisorWorkbench() {
  const [clipboardText, setClipboardText] = useState("");
  const [league, setLeague] = useState(DEFAULT_LEAGUE);
  const [gameDataDataset, setGameDataDataset] = useState(DEFAULT_GAME_DATA_DATASET);
  const [craftingDataset, setCraftingDataset] = useState(DEFAULT_CRAFTING_DATASET);
  const [affixDataset, setAffixDataset] = useState(DEFAULT_AFFIX_CAPACITY_DATASET);
  const [empiricalDataset, setEmpiricalDataset] = useState("");
  const [currentObservations, setCurrentObservations] = useState<EditableManualListingObservation[]>([]);
  const [outcomeObservations, setOutcomeObservations] = useState<Record<string, EditableManualListingObservation[]>>({});
  const [analysis, setAnalysis] = useState<AdvisorAnalyzeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [advancedToolsOpen, setAdvancedToolsOpen] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const request = {
        ...createDefaultAdvisorRequest(clipboardText),
        league,
        game_data_dataset_version: gameDataDataset,
        crafting_dataset_version: craftingDataset,
        affix_capacity_dataset_version: affixDataset,
        empirical_probability_dataset_version: empiricalDataset.trim() || null,
        current_valuation_evidence: buildManualEvidence(currentObservations),
        outcome_valuation_evidence: buildOutcomeEvidence(outcomeObservations)
      };
      const result = await analyzeAdvisor(request);
      setAnalysis(result);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to analyze item.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="shell">
      <section className="workspace">
        <form className="panel input-panel" onSubmit={submit}>
          <div className="section-heading">
            <h1>Quiver Craft Advisor</h1>
            <StatusBadge value={analysis?.status ?? "ANALYSIS_PARTIAL"} />
          </div>
          <label>
            Clipboard item text
            <textarea
              value={clipboardText}
              onChange={(event) => setClipboardText(event.target.value)}
              placeholder={PLACEHOLDER}
              rows={16}
            />
          </label>
          <details className="advanced-disclosure">
            <summary>Advanced dataset and evidence context</summary>
            <div className="context-grid">
              <label>
                League
                <input value={league} onChange={(event) => setLeague(event.target.value)} />
              </label>
              <label>
                Game data
                <input value={gameDataDataset} onChange={(event) => setGameDataDataset(event.target.value)} />
              </label>
              <label>
                Crafting actions
                <input value={craftingDataset} onChange={(event) => setCraftingDataset(event.target.value)} />
              </label>
              <label>
                Affix capacity
                <input value={affixDataset} onChange={(event) => setAffixDataset(event.target.value)} />
              </label>
              <label>
                Empirical evidence dataset
                <input
                  value={empiricalDataset}
                  onChange={(event) => setEmpiricalDataset(event.target.value)}
                  placeholder="optional explicit dataset ID"
                />
              </label>
            </div>
          </details>
          <button type="submit" disabled={loading || !clipboardText.trim()}>
            {loading ? "Analyzing..." : analysis ? "Re-run Analysis" : "Analyze Quiver"}
          </button>
          {error && <p className="error-message">{error}</p>}
        </form>

        <section className="results-column">
          {analysis ? (
            <>
              <PlayerSummary analysis={analysis} />
              <EvidenceReadinessPanel
                readiness={analysis.evidence_readiness}
                onOpenEvidenceTools={() => setAdvancedToolsOpen(true)}
              />
              <ItemSummary item={analysis.item} affixState={analysis.affix_state} />
              <DecisionPanel decision={analysis.decision} riskDecision={analysis.risk_adjusted_decision} />
              <ActionTable actions={analysis.actions} />
              <MissingRequirements requirements={analysis.missing_requirements} warnings={analysis.warnings} />
              <AdvancedTools
                analysis={analysis}
                clipboardText={clipboardText}
                league={league}
                craftingDataset={craftingDataset}
                gameDataDataset={gameDataDataset}
                currentObservations={currentObservations}
                outcomeObservations={outcomeObservations}
                setCurrentObservations={setCurrentObservations}
                setOutcomeObservations={setOutcomeObservations}
                advancedToolsOpen={advancedToolsOpen}
                setAdvancedToolsOpen={setAdvancedToolsOpen}
              />
            </>
          ) : (
            <>
              <section className="panel empty-state">
                <h2>Paste a Quiver to begin</h2>
                <p>
                  The first slice calls the FastAPI Advisor endpoint and displays the analysis exactly as far as
                  current evidence allows.
                </p>
              </section>
              <AdvancedTools
                analysis={analysis}
                clipboardText={clipboardText}
                league={league}
                craftingDataset={craftingDataset}
                gameDataDataset={gameDataDataset}
                currentObservations={currentObservations}
                outcomeObservations={outcomeObservations}
                setCurrentObservations={setCurrentObservations}
                setOutcomeObservations={setOutcomeObservations}
                advancedToolsOpen={advancedToolsOpen}
                setAdvancedToolsOpen={setAdvancedToolsOpen}
              />
            </>
          )}
        </section>
      </section>
    </main>
  );
}

function AdvancedTools({
  analysis,
  clipboardText,
  league,
  craftingDataset,
  gameDataDataset,
  currentObservations,
  outcomeObservations,
  setCurrentObservations,
  setOutcomeObservations,
  advancedToolsOpen,
  setAdvancedToolsOpen
}: {
  analysis: AdvisorAnalyzeResponse | null;
  clipboardText: string;
  league: string;
  craftingDataset: string;
  gameDataDataset: string;
  currentObservations: EditableManualListingObservation[];
  outcomeObservations: Record<string, EditableManualListingObservation[]>;
  setCurrentObservations: Dispatch<SetStateAction<EditableManualListingObservation[]>>;
  setOutcomeObservations: Dispatch<SetStateAction<Record<string, EditableManualListingObservation[]>>>;
  advancedToolsOpen: boolean;
  setAdvancedToolsOpen: Dispatch<SetStateAction<boolean>>;
}) {
  return (
    <details
      className="advanced-tools"
      open={advancedToolsOpen}
      onToggle={(event) => setAdvancedToolsOpen(event.currentTarget.open)}
    >
      <summary>
        <span>
          <strong>Advanced Evidence & Diagnostics</strong>
          <small>Manual evidence, recorder, review, and raw diagnostic tooling</small>
        </span>
        <span className="count">Optional</span>
      </summary>
      <div className="advanced-tools-body" hidden={!advancedToolsOpen}>
        <p className="muted">
          These tools preserve manual evidence, observation recording, dataset IDs, and raw diagnostics. They do not
          change Advisor recommendations unless their evidence is explicitly submitted.
        </p>
        <ManualValuationPanel
          actions={analysis?.actions ?? []}
          league={league}
          currentObservations={currentObservations}
          outcomeObservations={outcomeObservations}
          onAddCurrentObservation={(observation) =>
            setCurrentObservations((observations) => [...observations, observation])
          }
          onAddOutcomeObservation={(outcomeId, observation) =>
            setOutcomeObservations((groups) => ({
              ...groups,
              [outcomeId]: [...(groups[outcomeId] ?? []), observation]
            }))
          }
          onUpdateCurrentObservation={(index, observation) =>
            setCurrentObservations((observations) =>
              observations.map((existing, existingIndex) => (existingIndex === index ? observation : existing))
            )
          }
          onUpdateOutcomeObservation={(outcomeId, index, observation) =>
            setOutcomeObservations((groups) => ({
              ...groups,
              [outcomeId]: (groups[outcomeId] ?? []).map((existing, existingIndex) =>
                existingIndex === index ? observation : existing
              )
            }))
          }
          onRemoveCurrentObservation={(index) =>
            setCurrentObservations((observations) => observations.filter((_, existingIndex) => existingIndex !== index))
          }
          onRemoveOutcomeObservation={(outcomeId, index) =>
            setOutcomeObservations((groups) => ({
              ...groups,
              [outcomeId]: (groups[outcomeId] ?? []).filter((_, existingIndex) => existingIndex !== index)
            }))
          }
          onClearCurrentObservations={() => setCurrentObservations([])}
          onClearOutcomeObservations={(outcomeId) =>
            setOutcomeObservations((groups) => {
              const next = { ...groups };
              delete next[outcomeId];
              return next;
            })
          }
          onReplaceCurrentObservations={setCurrentObservations}
          onReplaceOutcomeObservations={(outcomeId, observations) =>
            setOutcomeObservations((groups) => ({
              ...groups,
              [outcomeId]: observations
            }))
          }
        />
        {analysis && (
          <>
            <CraftObservationRecorderPanel
              actions={analysis.actions}
              defaultBeforeText={clipboardText}
              league={league}
              craftingDatasetVersion={craftingDataset}
              modifierDatasetVersion={gameDataDataset}
            />
            <ObservationReviewPanel />
          </>
        )}
      </div>
    </details>
  );
}

export type EditableManualListingObservation = ManualListingObservation & {
  evidence_id?: string | null;
};

function buildManualEvidence(observations: EditableManualListingObservation[]): ManualValuationEvidence | null {
  if (!observations.length) return null;
  return {
    strategy: "STRICT",
    observations: observations.map(withoutWorkspaceFields),
    notes: "User-entered manual comparable listing evidence. Listing-derived estimate is not a realized sale price."
  };
}

function buildOutcomeEvidence(
  groupedObservations: Record<string, EditableManualListingObservation[]>
): OutcomeManualValuationEvidence[] {
  return Object.entries(groupedObservations)
    .filter(([, observations]) => observations.length > 0)
    .map(([outcome_id, observations]) => ({
      outcome_id,
      evidence: {
        strategy: "STRICT",
        observations: observations.map(withoutWorkspaceFields),
        notes: "User-entered manual outcome comparable listing evidence."
      }
    }));
}

function withoutWorkspaceFields(observation: EditableManualListingObservation): ManualListingObservation {
  const { evidence_id, ...manualObservation } = observation;
  void evidence_id;
  return manualObservation;
}
