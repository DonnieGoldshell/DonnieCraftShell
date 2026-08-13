import type { MissingRequirement } from "@/api/advisor";
import { displayStatus } from "@/lib/format";

type Props = {
  requirements: MissingRequirement[];
  warnings: string[];
};

export function MissingRequirements({ requirements, warnings }: Props) {
  return (
    <section className="panel">
      <div className="section-heading">
        <h2>Warnings & Missing Data</h2>
        <span className="count">{requirements.length + warnings.length}</span>
      </div>
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
        <p className="muted">No missing requirements reported.</p>
      )}
      {warnings.length > 0 && (
        <ul className="warning-list">
          {warnings.slice(0, 8).map((warning, index) => (
            <li key={`${warning}-${index}`}>{warning}</li>
          ))}
        </ul>
      )}
    </section>
  );
}
