"use client";

import { FormEvent, useState } from "react";
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
import { DecisionPanel } from "./DecisionPanel";
import { ItemSummary } from "./ItemSummary";
import { ManualValuationPanel } from "./ManualValuationPanel";
import { MissingRequirements } from "./MissingRequirements";
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
  const [currentObservations, setCurrentObservations] = useState<ManualListingObservation[]>([]);
  const [outcomeObservations, setOutcomeObservations] = useState<Record<string, ManualListingObservation[]>>({});
  const [analysis, setAnalysis] = useState<AdvisorAnalyzeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

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
          </div>
          <button type="submit" disabled={loading || !clipboardText.trim()}>
            {loading ? "Analyzing..." : analysis ? "Re-run Analysis" : "Analyze Quiver"}
          </button>
          {error && <p className="error-message">{error}</p>}
        </form>

        <section className="results-column">
          <ManualValuationPanel
            actions={analysis?.actions ?? []}
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
            onClearCurrentObservations={() => setCurrentObservations([])}
            onClearOutcomeObservations={(outcomeId) =>
              setOutcomeObservations((groups) => {
                const next = { ...groups };
                delete next[outcomeId];
                return next;
              })
            }
          />
          {analysis ? (
            <>
              <ItemSummary item={analysis.item} affixState={analysis.affix_state} />
              <DecisionPanel decision={analysis.decision} riskDecision={analysis.risk_adjusted_decision} />
              <ActionTable actions={analysis.actions} />
              <MissingRequirements requirements={analysis.missing_requirements} warnings={analysis.warnings} />
            </>
          ) : (
            <section className="panel empty-state">
              <h2>Paste a Quiver to begin</h2>
              <p>
                The first slice calls the FastAPI Advisor endpoint and displays the analysis exactly as far as
                current evidence allows.
              </p>
            </section>
          )}
        </section>
      </section>
    </main>
  );
}

function buildManualEvidence(observations: ManualListingObservation[]): ManualValuationEvidence | null {
  if (!observations.length) return null;
  return {
    strategy: "STRICT",
    observations,
    notes: "User-entered manual comparable listing evidence. Listing-derived estimate is not a realized sale price."
  };
}

function buildOutcomeEvidence(
  groupedObservations: Record<string, ManualListingObservation[]>
): OutcomeManualValuationEvidence[] {
  return Object.entries(groupedObservations)
    .filter(([, observations]) => observations.length > 0)
    .map(([outcome_id, observations]) => ({
      outcome_id,
      evidence: {
        strategy: "STRICT",
        observations,
        notes: "User-entered manual outcome comparable listing evidence."
      }
    }));
}
