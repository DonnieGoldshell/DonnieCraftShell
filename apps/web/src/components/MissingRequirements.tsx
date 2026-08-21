import type { MissingRequirement } from "@/api/advisor";
import { displayStatus } from "@/lib/format";
import { summarizeMissingCategories } from "./PlayerSummary";

type Props = {
  requirements: MissingRequirement[];
  warnings: string[];
};

export function MissingRequirements({ requirements, warnings }: Props) {
  const categories = summarizeMissingCategories(requirements, warnings);
  const uniqueWarnings = [...new Set(warnings)];
  return (
    <section className="panel">
      <div className="section-heading">
        <h2>Missing Evidence Summary</h2>
        <span className="count">{requirements.length + warnings.length}</span>
      </div>
      {categories.length ? (
        <ul className="requirement-list">
          {categories.map((category) => (
            <li key={category.label}>
              <strong>{category.label}</strong>
              <span>{category.count} related message{category.count === 1 ? "" : "s"}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="muted">No missing requirements reported.</p>
      )}
      <details className="diagnostics-details">
        <summary>Advanced diagnostics: raw missing requirements and warnings</summary>
        {requirements.length ? (
        <ul className="requirement-list">
          {requirements.map((requirement, index) => (
            <li key={`${requirement.type}-${requirement.action_id ?? "global"}-${index}`}>
              <strong>{displayStatus(requirement.type)}</strong>
              <span>{requirement.reason}</span>
              {requirement.action_id && <small>{requirement.action_id}</small>}
            </li>
          ))}
        </ul>
        ) : (
          <p className="muted">No raw missing requirements reported.</p>
        )}
        {uniqueWarnings.length > 0 && (
          <ul className="warning-list">
            {uniqueWarnings.map((warning, index) => (
              <li key={`${warning}-${index}`}>{warning}</li>
            ))}
          </ul>
        )}
      </details>
    </section>
  );
}
