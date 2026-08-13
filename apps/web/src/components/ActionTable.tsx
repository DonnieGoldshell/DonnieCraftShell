import type { ActionAnalysis } from "@/api/advisor";
import { costLabel, economicValueLabel } from "@/lib/format";
import { StatusBadge } from "./StatusBadge";

type Props = {
  actions: ActionAnalysis[];
};

export function ActionTable({ actions }: Props) {
  if (!actions.length) {
    return <section className="panel">No action candidates are available for this item.</section>;
  }

  return (
    <section className="panel">
      <div className="section-heading">
        <h2>Crafting Actions</h2>
        <span className="count">{actions.length}</span>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Action</th>
              <th>Applicability</th>
              <th>Cost</th>
              <th>Outcomes</th>
              <th>Probability</th>
              <th>Scenario</th>
              <th>Advisor</th>
            </tr>
          </thead>
          <tbody>
            {actions.map((action) => (
              <tr key={action.action_id}>
                <td>
                  <strong>{action.display_name}</strong>
                  <small>{action.action_id}</small>
                </td>
                <td>
                  <StatusBadge value={action.applicability} />
                  {action.failed_preconditions.length > 0 && <small>{action.failed_preconditions[0]}</small>}
                </td>
                <td>
                  <span>{costLabel(action)}</span>
                  <small>{action.material_cost.freshness}</small>
                </td>
                <td>
                  <span>{action.outcome_count}</span>
                  <small>{action.outcome_space_completeness ?? "Not enumerated"}</small>
                  {action.outcome_ids.length > 0 && <small>{action.outcome_ids.length} outcome IDs exposed</small>}
                </td>
                <td>
                  <StatusBadge value={action.probability_completeness} />
                </td>
                <td>
                  <StatusBadge value={action.scenario?.readiness ?? null} />
                  {action.scenario && (
                    <>
                      <small>
                        {action.scenario.valued_outcome_count}/{action.scenario.outcome_count} valued ·{" "}
                        {action.scenario.valuation_completeness ?? "Unknown valuation"}
                      </small>
                      <small>Median: {economicValueLabel(action.scenario.median_valuated_outcome)}</small>
                      <small>Best: {economicValueLabel(action.scenario.best_valuated_outcome)}</small>
                      <small>Worst: {economicValueLabel(action.scenario.worst_valuated_outcome)}</small>
                    </>
                  )}
                </td>
                <td>
                  <StatusBadge value={action.advisor_candidate_status ?? null} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
