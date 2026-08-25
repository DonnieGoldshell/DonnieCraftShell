import type { AdvisorAnalyzeResponse } from "@/api/advisor";
import { displayStatus } from "@/lib/format";
import { StatusBadge } from "./StatusBadge";

type EvidenceReadiness = NonNullable<AdvisorAnalyzeResponse["evidence_readiness"]>;
type EvidenceReadinessItem = EvidenceReadiness["items"][number];
export type EvidenceReadinessTarget = EvidenceReadinessItem["targets"][number];
export type EvidenceReadinessSelection = {
  target: EvidenceReadinessTarget;
  outcomeId?: string | null;
};

type Props = {
  readiness: AdvisorAnalyzeResponse["evidence_readiness"];
  onOpenEvidenceTools: (selection?: EvidenceReadinessSelection) => void;
};

const TOOL_LABELS: Record<string, string> = {
  "manual-current-valuation": "Open manual valuation evidence",
  "manual-outcome-valuation": "Open manual outcome valuation evidence",
  "observation-recorder-review-import": "Open observation recorder and review tools",
  "economy-data-import": "Open economy quote workflow",
  "local-economy-quotes": "Open economy quote workflow",
  "mechanic-research": "Review mechanic diagnostics"
};

export function EvidenceReadinessPanel({ readiness, onOpenEvidenceTools }: Props) {
  if (!readiness) return null;
  const items = readiness.items;
  const blockedCount = items.filter((item) => item.status !== "READY").length;

  return (
    <section className="panel readiness-panel" aria-label="Evidence readiness">
      <div className="section-heading">
        <div>
          <h2>Evidence Readiness</h2>
          <p className="muted">
            This checklist shows what would make the analysis more complete. Completing it does not guarantee a craft
            recommendation.
          </p>
        </div>
        <span className="count">{blockedCount} open</span>
      </div>
      <ul className="readiness-list">
        {items.map((item) => (
          <EvidenceReadinessRow key={item.category} item={item} onOpenEvidenceTools={onOpenEvidenceTools} />
        ))}
      </ul>
      {readiness.warnings.length > 0 && (
        <p className="muted readiness-warning">{readiness.warnings[0]}</p>
      )}
    </section>
  );
}

function EvidenceReadinessRow({
  item,
  onOpenEvidenceTools
}: {
  item: EvidenceReadinessItem;
  onOpenEvidenceTools: (selection?: EvidenceReadinessSelection) => void;
}) {
  const actionableTarget = item.targets[0];
  const toolLabel = readinessToolLabel(item);
  const probabilityTargets = probabilityEvidenceTargets(item);
  const outcomeValuationTargets = outcomeValuationEvidenceTargets(item);
  return (
    <li className="readiness-row">
      <div className="readiness-row-main">
        <StatusBadge value={item.status} />
        <div>
          <strong>{item.label}</strong>
          <p>{item.summary}</p>
        </div>
      </div>
      {item.targets.length > 0 && (
        <ul className="readiness-target-list">
          {item.targets.slice(0, 4).map((target) => (
            <li key={`${target.target_type}:${target.action_id ?? "global"}:${target.target_id}`}>
              <span>{target.action_display_name ?? target.asset_id ?? displayStatus(target.target_type)}</span>
              <small>{targetSummary(target)}</small>
            </li>
          ))}
          {item.targets.length > 4 && <li className="muted">+{item.targets.length - 4} more targets in diagnostics</li>}
        </ul>
      )}
      {probabilityTargets.length > 0 && (
        <div className="readiness-action-list">
          {probabilityTargets.map((target) => (
            <button
              key={`${target.action_id}:${target.target_id}`}
              type="button"
              className="secondary-button"
              onClick={() => onOpenEvidenceTools({ target })}
            >
              Collect probability evidence for {target.action_display_name ?? target.action_id}
            </button>
          ))}
        </div>
      )}
      {outcomeValuationTargets.length > 0 && (
        <div className="readiness-action-list">
          {outcomeValuationTargets.map(({ target, outcomeId }) => (
            <button
              key={`${target.action_id}:${outcomeId}`}
              type="button"
              className="secondary-button"
              onClick={() => onOpenEvidenceTools({ target, outcomeId })}
            >
              Add outcome valuation evidence for {target.action_display_name ?? target.action_id} outcome{" "}
              {shortTargetId(outcomeId)}
            </button>
          ))}
        </div>
      )}
      {probabilityTargets.length === 0 &&
        outcomeValuationTargets.length === 0 &&
        toolLabel &&
        item.status !== "READY" &&
        actionableTarget && (
        <button type="button" className="secondary-button" onClick={() => onOpenEvidenceTools({ target: actionableTarget })}>
          {toolLabel}
        </button>
      )}
    </li>
  );
}

function probabilityEvidenceTargets(item: EvidenceReadinessItem): EvidenceReadinessTarget[] {
  if (item.evidence_tool !== "observation-recorder-review-import" || item.status === "READY") {
    return [];
  }
  return item.targets.filter((target) => target.target_type === "ACTION_PROBABILITY_MODEL" && target.action_id);
}

function outcomeValuationEvidenceTargets(
  item: EvidenceReadinessItem
): { target: EvidenceReadinessTarget; outcomeId: string }[] {
  if (item.evidence_tool !== "manual-outcome-valuation" || item.status === "READY") {
    return [];
  }
  return item.targets
    .filter((target) => target.target_type === "OUTCOME_VALUATION" && target.action_id)
    .flatMap((target) => target.outcome_ids.map((outcomeId) => ({ target, outcomeId })));
}

function readinessToolLabel(item: EvidenceReadinessItem): string | null {
  if (
    item.evidence_tool === "observation-recorder-review-import" &&
    item.targets.some((target) => target.target_type === "ACTION_PROBABILITY_MODEL" && target.action_id)
  ) {
    return "Collect probability evidence";
  }
  return item.evidence_tool ? TOOL_LABELS[item.evidence_tool] : null;
}

function shortTargetId(id: string): string {
  return id.length > 18 ? `${id.slice(0, 10)}...${id.slice(-6)}` : id;
}

function targetSummary(target: EvidenceReadinessItem["targets"][number]): string {
  if (target.outcome_ids.length) {
    return `${target.outcome_ids.length} outcome${target.outcome_ids.length === 1 ? "" : "s"} need evidence`;
  }
  return target.reason;
}
