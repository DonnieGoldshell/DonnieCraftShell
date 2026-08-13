import type { AdvisorAnalyzeResponse } from "@/api/advisor";
import { StatusBadge } from "./StatusBadge";

type Props = {
  item: AdvisorAnalyzeResponse["item"];
  affixState: AdvisorAnalyzeResponse["affix_state"];
};

export function ItemSummary({ item, affixState }: Props) {
  if (!item) {
    return <section className="panel">No parsed item is available.</section>;
  }

  return (
    <section className="panel">
      <div className="section-heading">
        <h2>{item.base_type ?? "Unknown item"}</h2>
        <StatusBadge value={item.rarity} />
      </div>
      <dl className="facts-grid">
        <div>
          <dt>Class</dt>
          <dd>{item.item_class ?? "Unknown"}</dd>
        </div>
        <div>
          <dt>Item level</dt>
          <dd>{item.item_level ?? "Unknown"}</dd>
        </div>
        <div>
          <dt>Required level</dt>
          <dd>{item.required_level ?? "Unknown"}</dd>
        </div>
        <div>
          <dt>Affixes</dt>
          <dd>
            {affixState
              ? `${affixState.observed_prefix_count ?? "?"}/${affixState.prefix_capacity ?? "?"} prefixes, ${affixState.observed_suffix_count ?? "?"}/${affixState.suffix_capacity ?? "?"} suffixes`
              : "Unknown"}
          </dd>
        </div>
      </dl>
      <div className="mod-columns">
        <ModifierList title="Prefixes" modifiers={item.prefixes} />
        <ModifierList title="Suffixes" modifiers={item.suffixes} />
        <ModifierList title="Implicits" modifiers={item.implicit_modifiers} />
      </div>
    </section>
  );
}

function ModifierList({ title, modifiers }: { title: string; modifiers: NonNullable<Props["item"]>["prefixes"] }) {
  return (
    <div>
      <h3>{title}</h3>
      {modifiers.length ? (
        <ul className="modifier-list">
          {modifiers.map((modifier, index) => (
            <li key={`${title}-${index}`}>
              <span>{modifier.raw_text}</span>
              <small>
                {[modifier.display_name, modifier.tier ? `T${modifier.tier}` : null, modifier.origin, modifier.resolution_status]
                  .filter(Boolean)
                  .join(" · ")}
              </small>
            </li>
          ))}
        </ul>
      ) : (
        <p className="muted">None reported.</p>
      )}
    </div>
  );
}
