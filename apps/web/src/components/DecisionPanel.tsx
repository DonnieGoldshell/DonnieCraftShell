import type { AdvisorAnalyzeResponse } from "@/api/advisor";
import { StatusBadge } from "./StatusBadge";

type Props = {
  decision: AdvisorAnalyzeResponse["decision"];
  riskDecision: AdvisorAnalyzeResponse["risk_adjusted_decision"];
};

export function DecisionPanel({ decision, riskDecision }: Props) {
  return (
    <section className="panel">
      <div className="section-heading">
        <h2>Advisor Decision</h2>
        <StatusBadge value={decision?.decision_type ?? "NO_RECOMMENDATION"} />
      </div>
      {decision ? (
        <>
          <p className="muted">Raw Advisor decision. Scenario-only actions are visible but not rankable as EV.</p>
          <ReasonList reasons={decision.reasons} />
          <p className="version">Algorithm: {decision.algorithm_version ?? "Unknown"}</p>
        </>
      ) : (
        <p className="muted">No Advisor decision was produced for this analysis.</p>
      )}
      {riskDecision && (
        <div className="risk-box">
          <div className="section-heading">
            <h3>Risk Adjustment</h3>
            <StatusBadge value={riskDecision.decision_type} />
          </div>
          <p className="muted">
            Raw winner: {riskDecision.raw_winner_candidate_id ?? "None"} · Selected after policy:{" "}
            {riskDecision.selected_candidate_id ?? "None"}
          </p>
          <ReasonList reasons={riskDecision.reasons} />
        </div>
      )}
    </section>
  );
}

function ReasonList({ reasons }: { reasons: string[] }) {
  if (!reasons.length) return null;
  return (
    <ul className="reason-list">
      {reasons.map((reason) => (
        <li key={reason}>{reason}</li>
      ))}
    </ul>
  );
}
