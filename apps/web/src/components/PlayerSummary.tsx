import type { AdvisorAnalyzeResponse, MissingRequirement } from "@/api/advisor";
import { displayStatus } from "@/lib/format";
import { StatusBadge } from "./StatusBadge";

type Props = {
  analysis: AdvisorAnalyzeResponse;
};

export function PlayerSummary({ analysis }: Props) {
  const item = analysis.item;
  const decisionType = analysis.decision?.decision_type ?? "NO_RECOMMENDATION";
  const reason = analysis.decision?.reasons[0] ?? "Analysis is partial because required evidence is still missing.";
  const missingCategories = summarizeMissingCategories(analysis.missing_requirements, analysis.warnings);

  return (
    <section className="panel player-summary" aria-label="Player advisor summary">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Advisor summary</p>
          <h2>{item?.base_type ? `Advisor for ${item.base_type}` : "Advisor for unknown item"}</h2>
        </div>
        <StatusBadge value={decisionType} />
      </div>
      <dl className="summary-facts">
        <div>
          <dt>Item</dt>
          <dd>
            {[item?.rarity, item?.item_class, item?.item_level ? `ilvl ${item.item_level}` : null]
              .filter(Boolean)
              .join(" ")}
          </dd>
        </div>
        <div>
          <dt>Affixes</dt>
          <dd>{affixLabel(analysis.affix_state)}</dd>
        </div>
        <div>
          <dt>Decision</dt>
          <dd>{displayStatus(decisionType)}</dd>
        </div>
      </dl>
      <p className="player-reason">{reason}</p>
      {missingCategories.length > 0 && (
        <div className="player-blockers">
          <strong>What is blocking a stronger recommendation?</strong>
          <ul>
            {missingCategories.map((category) => (
              <li key={category.label}>
                <span>{category.label}</span>
                <small>{category.count} item{category.count === 1 ? "" : "s"}</small>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}

export function summarizeMissingCategories(requirements: MissingRequirement[], warnings: string[]) {
  const counts = new Map<string, number>();
  for (const requirement of requirements) {
    increment(counts, categoryForRequirement(requirement.type));
  }
  for (const warning of warnings) {
    increment(counts, categoryForWarning(warning));
  }
  return [...counts.entries()]
    .map(([label, count]) => ({ label, count }))
    .sort((left, right) => right.count - left.count || left.label.localeCompare(right.label));
}

function affixLabel(affixState: AdvisorAnalyzeResponse["affix_state"]): string {
  if (!affixState) return "Unknown";
  return `${affixState.observed_prefix_count ?? "?"}/${affixState.prefix_capacity ?? "?"} prefixes, ${
    affixState.observed_suffix_count ?? "?"
  }/${affixState.suffix_capacity ?? "?"} suffixes`;
}

function categoryForRequirement(type: string): string {
  if (type.includes("VALUATION")) return "Valuation evidence";
  if (type.includes("PROBABILITY")) return "Probability evidence";
  if (type.includes("ECONOMY") || type.includes("QUOTE")) return "Economy prices";
  if (type.includes("MECHANIC") || type.includes("VERIFIED")) return "Verified mechanics";
  return "Other missing data";
}

function categoryForWarning(warning: string): string {
  const lower = warning.toLowerCase();
  if (lower.includes("valuation") || lower.includes("listing")) return "Valuation evidence";
  if (lower.includes("probability") || lower.includes("equal-distribution")) return "Probability evidence";
  if (lower.includes("economy") || lower.includes("price") || lower.includes("quote")) return "Economy prices";
  if (lower.includes("mechanic") || lower.includes("verified") || lower.includes("not simulated")) {
    return "Verified mechanics";
  }
  return "Diagnostics";
}

function increment(counts: Map<string, number>, label: string) {
  counts.set(label, (counts.get(label) ?? 0) + 1);
}
