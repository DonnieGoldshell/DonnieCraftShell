import type { ActionAnalysis } from "@/api/advisor";

export function displayStatus(value: string | null | undefined): string {
  if (!value) return "Unknown";
  return value
    .toLowerCase()
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export function statusTone(value: string | null | undefined): "good" | "warn" | "muted" | "bad" {
  if (!value) return "muted";
  if (["APPLICABLE", "DECISION_READY", "CRAFT", "SELL_NOW", "READY", "EV_READY"].includes(value)) return "good";
  if (["NO_RECOMMENDATION", "ANALYSIS_PARTIAL", "SCENARIO_READY", "SCENARIO_ONLY", "UNKNOWN"].includes(value)) return "warn";
  if (["NOT_APPLICABLE", "UNSUPPORTED_ITEM", "PARSE_FAILED"].includes(value)) return "bad";
  return "muted";
}

export function costLabel(action: ActionAnalysis): string {
  if (!action.material_cost.complete) return "Missing price";
  return action.material_cost.total ? `${action.material_cost.total.amount} Ex` : "No cost";
}
