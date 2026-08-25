"use client";

import {
  FormEvent,
  type Dispatch,
  type RefObject,
  type SetStateAction,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState
} from "react";
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
import { EvidenceReadinessPanel, type EvidenceReadinessSelection } from "./EvidenceReadinessPanel";
import { EconomyQuotePanel } from "./EconomyQuotePanel";
import { ItemSummary } from "./ItemSummary";
import { ManualValuationPanel } from "./ManualValuationPanel";
import { MissingRequirements } from "./MissingRequirements";
import { ObservationReviewPanel } from "./ObservationReviewPanel";
import { PlayerSummary } from "./PlayerSummary";
import { StatusBadge } from "./StatusBadge";
import { displayStatus } from "@/lib/format";

const PLACEHOLDER = `Item Class: Quivers
Rarity: Rare
...paste Path of Exile 2 Advanced Copy text here...`;

type AdvancedToolNavigationTarget = "manual-valuation" | "economy-quotes" | "probability-workflow";

export function AdvisorWorkbench() {
  const [clipboardText, setClipboardText] = useState("");
  const [league, setLeague] = useState(DEFAULT_LEAGUE);
  const [gameDataDataset, setGameDataDataset] = useState(DEFAULT_GAME_DATA_DATASET);
  const [craftingDataset, setCraftingDataset] = useState(DEFAULT_CRAFTING_DATASET);
  const [affixDataset, setAffixDataset] = useState(DEFAULT_AFFIX_CAPACITY_DATASET);
  const [empiricalDataset, setEmpiricalDataset] = useState("");
  const [bankroll, setBankroll] = useState("");
  const [riskProfile, setRiskProfile] = useState("");
  const [currentObservations, setCurrentObservations] = useState<EditableManualListingObservation[]>([]);
  const [outcomeObservations, setOutcomeObservations] = useState<Record<string, EditableManualListingObservation[]>>({});
  const [analysis, setAnalysis] = useState<AdvisorAnalyzeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [advancedToolsOpen, setAdvancedToolsOpen] = useState(false);
  const [evidenceTarget, setEvidenceTarget] = useState<EvidenceReadinessSelection | null>(null);
  const [pendingAdvancedNavigation, setPendingAdvancedNavigation] =
    useState<AdvancedToolNavigationTarget | null>(null);

  const openEvidenceTools = useCallback((target?: EvidenceReadinessSelection) => {
    setEvidenceTarget(target ?? null);
    setAdvancedToolsOpen(true);
    setPendingAdvancedNavigation(advancedToolNavigationTarget(target));
  }, []);

  const clearPendingAdvancedNavigation = useCallback(() => {
    setPendingAdvancedNavigation(null);
  }, []);

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
        bankroll: bankroll.trim() ? { amount: bankroll.trim(), unit: "EXALTED_ECONOMIC_UNIT" } : null,
        risk_profile: riskProfile || null,
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
              <label>
                Bankroll in Exalted units
                <input
                  inputMode="decimal"
                  value={bankroll}
                  onChange={(event) => setBankroll(event.target.value)}
                  placeholder="optional for risk adjustment"
                />
              </label>
              <label>
                Risk profile
                <select value={riskProfile} onChange={(event) => setRiskProfile(event.target.value)}>
                  <option value="">Use backend default only if risk context is supplied</option>
                  <option value="CONSERVATIVE">Conservative</option>
                  <option value="BALANCED">Balanced</option>
                  <option value="AGGRESSIVE">Aggressive</option>
                </select>
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
              <ProductionEvidencePilotPanel
                analysis={analysis}
                currentObservations={currentObservations}
                outcomeObservations={outcomeObservations}
                selectedEmpiricalDatasetVersion={empiricalDataset}
                bankroll={bankroll}
                riskProfile={riskProfile}
                onOpenEvidenceTools={openEvidenceTools}
              />
              <EvidenceReadinessPanel
                readiness={analysis.evidence_readiness}
                onOpenEvidenceTools={openEvidenceTools}
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
                evidenceTarget={evidenceTarget}
                pendingNavigationTarget={pendingAdvancedNavigation}
                onNavigationComplete={clearPendingAdvancedNavigation}
                selectedEmpiricalDatasetVersion={empiricalDataset}
                onSelectEmpiricalDataset={setEmpiricalDataset}
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
                evidenceTarget={evidenceTarget}
                pendingNavigationTarget={pendingAdvancedNavigation}
                onNavigationComplete={clearPendingAdvancedNavigation}
                selectedEmpiricalDatasetVersion={empiricalDataset}
                onSelectEmpiricalDataset={setEmpiricalDataset}
              />
            </>
          )}
        </section>
      </section>
    </main>
  );
}

function ProductionEvidencePilotPanel({
  analysis,
  currentObservations,
  outcomeObservations,
  selectedEmpiricalDatasetVersion,
  bankroll,
  riskProfile,
  onOpenEvidenceTools
}: {
  analysis: AdvisorAnalyzeResponse;
  currentObservations: EditableManualListingObservation[];
  outcomeObservations: Record<string, EditableManualListingObservation[]>;
  selectedEmpiricalDatasetVersion: string;
  bankroll: string;
  riskProfile: string;
  onOpenEvidenceTools: (selection?: EvidenceReadinessSelection) => void;
}) {
  const readinessItems = analysis.evidence_readiness?.items ?? [];
  const currentItemTarget = firstTarget(readinessItems, "CURRENT_ITEM_VALUATION");
  const economyTarget = firstTarget(readinessItems, "ECONOMY_CRAFTING_COST");
  const probabilityTarget = firstTarget(readinessItems, "PROBABILITY");
  const outcomeTarget = firstTarget(readinessItems, "OUTCOME_VALUATION");
  const currentSavedCount = currentObservations.filter((observation) => observation.evidence_id).length;
  const outcomePreparedCount = Object.values(outcomeObservations).flat().length;
  const outcomeSavedCount = Object.values(outcomeObservations)
    .flat()
    .filter((observation) => observation.evidence_id).length;
  const totalOutcomeTargets = outcomeTarget?.outcome_ids.length ?? 0;
  const preparedOutcomeTargets = outcomeTarget
    ? outcomeTarget.outcome_ids.filter((outcomeId) => (outcomeObservations[outcomeId] ?? []).length > 0).length
    : 0;
  const summary = pilotSummary(analysis);

  return (
    <section className="panel pilot-panel" aria-label="Production evidence pilot">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Production evidence pilot</p>
          <h2>{summary.title}</h2>
          <p className="muted">{summary.description}</p>
        </div>
      </div>
      <ul className="pilot-steps">
        <PilotStep
          title="Analyze pasted item"
          status="READY"
          detail={`${analysis.item?.base_type ?? "Item"} analyzed in ${analysis.context.league}.`}
        />
        <PilotStep
          title="Current item valuation"
          status={statusForCategory(readinessItems, "CURRENT_ITEM_VALUATION")}
          detail={`${currentObservations.length} prepared for next rerun; ${currentSavedCount} saved locally.`}
          actionLabel={currentItemTarget ? "Open current valuation workflow" : undefined}
          onAction={currentItemTarget ? () => onOpenEvidenceTools({ target: currentItemTarget }) : undefined}
        />
        <PilotStep
          title="Crafting material quote"
          status={statusForCategory(readinessItems, "ECONOMY_CRAFTING_COST")}
          detail="Local quote workspace evidence applies only after an explicit Advisor rerun."
          actionLabel={economyTarget ? "Open local quote workspace" : undefined}
          onAction={economyTarget ? () => onOpenEvidenceTools({ target: economyTarget }) : undefined}
        />
        <PilotStep
          title="Probability evidence"
          status={statusForCategory(readinessItems, "PROBABILITY")}
          detail={
            selectedEmpiricalDatasetVersion.trim()
              ? `Selected for next rerun: ${selectedEmpiricalDatasetVersion.trim()}.`
              : "No empirical dataset selected for the next rerun."
          }
          actionLabel={probabilityTarget ? "Open probability evidence workflow" : undefined}
          onAction={probabilityTarget ? () => onOpenEvidenceTools({ target: probabilityTarget }) : undefined}
        />
        <PilotStep
          title="Outcome valuations"
          status={statusForCategory(readinessItems, "OUTCOME_VALUATION")}
          detail={`${preparedOutcomeTargets}/${totalOutcomeTargets} blocked outcomes have prepared evidence; ${outcomePreparedCount} observations prepared; ${outcomeSavedCount} saved locally.`}
          actionLabel={outcomeTarget ? "Open next outcome valuation" : undefined}
          onAction={
            outcomeTarget
              ? () =>
                  onOpenEvidenceTools({
                    target: outcomeTarget,
                    outcomeId: outcomeTarget.outcome_ids.find(
                      (outcomeId) => !(outcomeObservations[outcomeId] ?? []).length
                    ) ?? outcomeTarget.outcome_ids[0] ?? null
                  })
              : undefined
          }
        />
        <PilotStep
          title="Bankroll and risk context"
          status={bankroll.trim() || riskProfile ? "READY" : "UNKNOWN"}
          detail={
            bankroll.trim() || riskProfile
              ? `Next rerun includes ${bankroll.trim() ? `${bankroll.trim()} Ex bankroll` : "no bankroll"} and ${
                  riskProfile ? displayStatus(riskProfile) : "backend default"
                } risk profile. Risk affects risk adjustment, not raw EV.`
              : "Optional. Add this in Advanced dataset and evidence context before rerun for risk adjustment."
          }
        />
        <PilotStep
          title="Explicit rerun"
          status="UNKNOWN"
          detail="Saved workspace evidence and selected dataset IDs do not affect Advisor output until you click Re-run Analysis."
        />
      </ul>
    </section>
  );
}

function PilotStep({
  title,
  status,
  detail,
  actionLabel,
  onAction
}: {
  title: string;
  status: string;
  detail: string;
  actionLabel?: string;
  onAction?: () => void;
}) {
  return (
    <li>
      <div className="pilot-step-main">
        <StatusBadge value={status} />
        <div>
          <strong>{title}</strong>
          <small>{detail}</small>
        </div>
      </div>
      {actionLabel && onAction && (
        <button type="button" className="secondary-button" onClick={onAction}>
          {actionLabel}
        </button>
      )}
    </li>
  );
}

function firstTarget(
  items: NonNullable<AdvisorAnalyzeResponse["evidence_readiness"]>["items"],
  category: string
) {
  return items.find((item) => item.category === category && item.status !== "READY")?.targets[0] ?? null;
}

function statusForCategory(
  items: NonNullable<AdvisorAnalyzeResponse["evidence_readiness"]>["items"],
  category: string
): string {
  return items.find((item) => item.category === category)?.status ?? "UNKNOWN";
}

function pilotSummary(analysis: AdvisorAnalyzeResponse): { title: string; description: string } {
  if (analysis.status === "DECISION_READY") {
    return {
      title: "Decision ready - backend decision available",
      description: "Raw and risk-adjusted decision state, when present, came back from the backend Advisor policy."
    };
  }
  if (analysis.actions.some((action) => action.expected_value?.available)) {
    return {
      title: "EV ready - raw decision evidence exists",
      description: "At least one action has backend EV output; inspect Advisor decision and risk adjustment separately."
    };
  }
  if (analysis.status === "SCENARIO_READY") {
    return {
      title: "Scenario ready - EV unavailable",
      description: "Outcome valuations can support descriptive scenario analysis, but missing inputs still block EV ranking."
    };
  }
  return {
    title: "Evidence incomplete - recommendation unavailable",
    description: "Use the existing evidence tools, then explicitly rerun analysis. Partial and unknown states are expected."
  };
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
  setAdvancedToolsOpen,
  evidenceTarget,
  pendingNavigationTarget,
  onNavigationComplete,
  selectedEmpiricalDatasetVersion,
  onSelectEmpiricalDataset
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
  evidenceTarget: EvidenceReadinessSelection | null;
  pendingNavigationTarget: AdvancedToolNavigationTarget | null;
  onNavigationComplete: () => void;
  selectedEmpiricalDatasetVersion: string;
  onSelectEmpiricalDataset: Dispatch<SetStateAction<string>>;
}) {
  const manualValuationRef = useRef<HTMLElement | null>(null);
  const economyQuoteRef = useRef<HTMLElement | null>(null);
  const probabilityWorkflowRef = useRef<HTMLElement | null>(null);
  const targetActionId =
    evidenceTarget?.target.target_type === "ACTION_PROBABILITY_MODEL" ? evidenceTarget.target.action_id ?? null : null;
  const outcomeValuationTarget =
    evidenceTarget?.target.target_type === "OUTCOME_VALUATION"
      ? {
          actionId: evidenceTarget.target.action_id ?? null,
          actionName: evidenceTarget.target.action_display_name ?? null,
          outcomeId: evidenceTarget.outcomeId ?? evidenceTarget.target.outcome_ids[0] ?? null,
          outcomeIds: evidenceTarget.target.outcome_ids
        }
      : null;
  const currentValuationReadiness = useMemo(() => {
    const item = analysis?.evidence_readiness?.items.find((readiness) => readiness.category === "CURRENT_ITEM_VALUATION");
    return item?.status ?? null;
  }, [analysis]);
  const targetRef = advancedToolTargetRef(
    pendingNavigationTarget,
    manualValuationRef,
    economyQuoteRef,
    probabilityWorkflowRef
  );

  useEffect(() => {
    if (!advancedToolsOpen || !pendingNavigationTarget) return;
    const target = targetRef?.current;
    if (!target) return;

    target.focus({ preventScroll: true });
    target.scrollIntoView?.({ behavior: "smooth", block: "start" });
    onNavigationComplete();
  }, [advancedToolsOpen, pendingNavigationTarget, targetRef, onNavigationComplete]);

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
          ref={manualValuationRef}
          actions={analysis?.actions ?? []}
          league={league}
          currentObservations={currentObservations}
          outcomeObservations={outcomeObservations}
          outcomeValuationTarget={outcomeValuationTarget}
          currentValuationReadiness={currentValuationReadiness}
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
        <EconomyQuotePanel ref={economyQuoteRef} analysis={analysis} league={league} />
        {analysis && (
          <>
            <CraftObservationRecorderPanel
              ref={probabilityWorkflowRef}
              actions={analysis.actions}
              defaultBeforeText={clipboardText}
              league={league}
              craftingDatasetVersion={craftingDataset}
              modifierDatasetVersion={gameDataDataset}
              targetActionId={targetActionId}
            />
            <ObservationReviewPanel
              targetActionId={targetActionId}
              selectedEmpiricalDatasetVersion={selectedEmpiricalDatasetVersion}
              onSelectEmpiricalDataset={onSelectEmpiricalDataset}
            />
          </>
        )}
      </div>
    </details>
  );
}

function advancedToolNavigationTarget(
  selection?: EvidenceReadinessSelection
): AdvancedToolNavigationTarget | null {
  if (!selection) return "manual-valuation";
  switch (selection.target.target_type) {
    case "CURRENT_ITEM":
    case "OUTCOME_VALUATION":
      return "manual-valuation";
    case "ECONOMY_ASSET":
      return "economy-quotes";
    case "ACTION_PROBABILITY_MODEL":
      return "probability-workflow";
    default:
      return "manual-valuation";
  }
}

function advancedToolTargetRef(
  target: AdvancedToolNavigationTarget | null,
  manualValuationRef: RefObject<HTMLElement | null>,
  economyQuoteRef: RefObject<HTMLElement | null>,
  probabilityWorkflowRef: RefObject<HTMLElement | null>
): RefObject<HTMLElement | null> | null {
  switch (target) {
    case "manual-valuation":
      return manualValuationRef;
    case "economy-quotes":
      return economyQuoteRef;
    case "probability-workflow":
      return probabilityWorkflowRef;
    default:
      return null;
  }
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
