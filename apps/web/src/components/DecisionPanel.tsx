import type { AdvisorAnalyzeResponse } from "@/api/advisor";
import { StatusBadge } from "./StatusBadge";

type Props = {
  decision: AdvisorAnalyzeResponse["decision"];
  riskDecision: AdvisorAnalyzeResponse["risk_adjusted_decision"];
  currentMarketValuation: AdvisorAnalyzeResponse["current_market_valuation"];
  stopContinueDecision: AdvisorAnalyzeResponse["stop_continue_decision"];
};

export function DecisionPanel({ decision, riskDecision, currentMarketValuation, stopContinueDecision }: Props) {
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
      {stopContinueDecision && (
        <div className="decision-economics" aria-label="Sell now versus continue crafting economics">
          <div className="section-heading">
            <h3>Sell Now vs Continue</h3>
            <StatusBadge value={stopContinueDecision.decision_type} />
          </div>
          <dl className="decision-grid">
            <div>
              <dt>Current market value</dt>
              <dd>
                {currentMarketValuation?.display_estimated_value ??
                  formatValue(stopContinueDecision.sell_now_value) ??
                  displayMarketBlocker(stopContinueDecision)}
              </dd>
            </div>
            <div>
              <dt>Supported market range</dt>
              <dd>
                {currentMarketValuation?.display_supported_range ??
                  formatRange(currentMarketValuation?.supported_low, currentMarketValuation?.supported_high) ??
                  "Unavailable"}
              </dd>
            </div>
            <div>
              <dt>Total invested</dt>
              <dd>{formatValue(stopContinueDecision.total_invested) ?? stopContinueDecision.cost_basis_status ?? "Unknown"}</dd>
            </div>
            <div>
              <dt>Recommended next action</dt>
              <dd>{selectedRecommendationLabel(stopContinueDecision)}</dd>
            </div>
            <div>
              <dt>Expected incremental cost</dt>
              <dd>{formatValue(stopContinueDecision.expected_incremental_craft_cost) ?? "Unavailable"}</dd>
            </div>
            <div>
              <dt>Expected value after craft</dt>
              <dd>{formatValue(stopContinueDecision.expected_post_craft_value) ?? "Unavailable"}</dd>
            </div>
            <div>
              <dt>Gain/loss vs sell now</dt>
              <dd>{formatValue(stopContinueDecision.gain_loss_vs_sell_now) ?? "Unavailable"}</dd>
            </div>
            <div>
              <dt>Confidence</dt>
              <dd>{stopContinueDecision.readiness}</dd>
            </div>
          </dl>
          <details className="why-disclosure">
            <summary>WHY</summary>
            {stopContinueDecision.best_continue_action_id ? (
              <p className="muted">Best EV-ready continuation: {stopContinueDecision.best_continue_action_id}</p>
            ) : null}
            <ReasonList reasons={[...stopContinueDecision.reasons, ...stopContinueDecision.blockers]} />
            <ReasonList reasons={stopContinueDecision.warnings} />
          </details>
        </div>
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

function formatValue(value: { amount: string; unit: string } | null | undefined): string | null {
  if (!value) return null;
  return `${value.amount} Ex`;
}

function formatRange(
  low: { amount: string; unit: string } | null | undefined,
  high: { amount: string; unit: string } | null | undefined,
): string | null {
  if (!low || !high) return null;
  return `${formatValue(low)}-${formatValue(high)}`;
}

function displayMarketBlocker(decision: NonNullable<AdvisorAnalyzeResponse["stop_continue_decision"]>): string {
  if (decision.current_market_valuation_status === "SUPPORTED_RANGE_ONLY") {
    return "Range only - no point baseline";
  }
  if (decision.current_market_valuation_status === "INSUFFICIENT_MARKET_EVIDENCE") {
    return "Insufficient evidence";
  }
  return "Unavailable";
}

function selectedRecommendationLabel(
  decision: NonNullable<AdvisorAnalyzeResponse["stop_continue_decision"]>,
): string {
  if (decision.decision_type === "SELL_NOW") {
    return "Sell Now";
  }
  if (decision.decision_type === "CRAFT") {
    return decision.selected_action_id ?? "Selected craft unavailable";
  }
  return "No recommendation";
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
