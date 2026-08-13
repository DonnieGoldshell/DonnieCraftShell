import { FormEvent, useMemo, useState } from "react";
import {
  DIVINE_ASSET_ID,
  EXALTED_ASSET_ID,
  type ActionAnalysis,
  type ManualListingObservation
} from "@/api/advisor";

type OutcomeOption = {
  actionId: string;
  actionName: string;
  outcomeId: string;
};

type Props = {
  actions: ActionAnalysis[];
  currentObservations: ManualListingObservation[];
  outcomeObservations: Record<string, ManualListingObservation[]>;
  onAddCurrentObservation: (observation: ManualListingObservation) => void;
  onAddOutcomeObservation: (outcomeId: string, observation: ManualListingObservation) => void;
  onClearCurrentObservations: () => void;
  onClearOutcomeObservations: (outcomeId: string) => void;
};

const CURRENCY_OPTIONS = [
  { label: "Exalted Orb", value: EXALTED_ASSET_ID },
  { label: "Divine Orb", value: DIVINE_ASSET_ID }
];

const emptyObservation = {
  amount: "",
  currency_asset_id: DIVINE_ASSET_ID,
  external_listing_id: "",
  observed_at: "",
  item_summary: "",
  notes: ""
};

export function ManualValuationPanel({
  actions,
  currentObservations,
  outcomeObservations,
  onAddCurrentObservation,
  onAddOutcomeObservation,
  onClearCurrentObservations,
  onClearOutcomeObservations
}: Props) {
  const outcomeOptions = useMemo(
    () =>
      actions.flatMap((action) =>
        action.outcome_ids.map((outcomeId) => ({
          actionId: action.action_id,
          actionName: action.display_name,
          outcomeId
        }))
      ),
    [actions]
  );
  const [target, setTarget] = useState<"current" | "outcome">("current");
  const [outcomeId, setOutcomeId] = useState("");
  const [draft, setDraft] = useState(emptyObservation);
  const [error, setError] = useState<string | null>(null);

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    const amount = draft.amount.trim();
    if (!amount) {
      setError("Listing amount is required.");
      return;
    }
    if (target === "outcome" && !outcomeId) {
      setError("Choose an outcome ID for outcome valuation evidence.");
      return;
    }
    const observation: ManualListingObservation = {
      amount,
      currency_asset_id: draft.currency_asset_id,
      external_listing_id: optionalText(draft.external_listing_id),
      observed_at: optionalText(draft.observed_at),
      item_summary: optionalText(draft.item_summary),
      notes: optionalText(draft.notes)
    };
    if (target === "current") {
      onAddCurrentObservation(observation);
    } else {
      onAddOutcomeObservation(outcomeId, observation);
    }
    setDraft({ ...emptyObservation, currency_asset_id: draft.currency_asset_id });
  }

  return (
    <section className="panel evidence-panel">
      <div className="section-heading">
        <h2>Manual Valuation Evidence</h2>
        <span className="count">
          {currentObservations.length + Object.values(outcomeObservations).flat().length}
        </span>
      </div>
      <p className="muted">
        Enter comparable listing observations only. The API converts and aggregates evidence; listing-derived
        estimates are not guaranteed sale prices.
      </p>
      <form className="evidence-form" onSubmit={submit}>
        <label>
          Evidence subject
          <select value={target} onChange={(event) => setTarget(event.target.value as "current" | "outcome")}>
            <option value="current">Current item</option>
            <option value="outcome" disabled={!outcomeOptions.length}>
              Hypothetical outcome
            </option>
          </select>
        </label>
        {target === "outcome" && (
          <label>
            Outcome ID
            <select value={outcomeId} onChange={(event) => setOutcomeId(event.target.value)}>
              <option value="">Choose outcome</option>
              {outcomeOptions.map((option) => (
                <option key={option.outcomeId} value={option.outcomeId}>
                  {option.actionName}: {shortId(option.outcomeId)}
                </option>
              ))}
            </select>
          </label>
        )}
        <label>
          Listing amount
          <input
            inputMode="decimal"
            value={draft.amount}
            onChange={(event) => setDraft({ ...draft, amount: event.target.value })}
            placeholder="5.5"
          />
        </label>
        <label>
          Currency
          <select
            value={draft.currency_asset_id}
            onChange={(event) => setDraft({ ...draft, currency_asset_id: event.target.value })}
          >
            {CURRENCY_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label>
          Listing ID
          <input
            value={draft.external_listing_id}
            onChange={(event) => setDraft({ ...draft, external_listing_id: event.target.value })}
            placeholder="optional"
          />
        </label>
        <label>
          Observed at
          <input
            value={draft.observed_at}
            onChange={(event) => setDraft({ ...draft, observed_at: event.target.value })}
            placeholder="2026-08-13T09:00:00Z"
          />
        </label>
        <label className="wide-field">
          Listing/item note
          <input
            value={draft.item_summary}
            onChange={(event) => setDraft({ ...draft, item_summary: event.target.value })}
            placeholder="manual comparable summary"
          />
        </label>
        <label className="wide-field">
          Evidence notes
          <input
            value={draft.notes}
            onChange={(event) => setDraft({ ...draft, notes: event.target.value })}
            placeholder="source/context"
          />
        </label>
        <button type="submit">Add Observation</button>
        {error && <p className="error-message compact">{error}</p>}
      </form>

      <EvidenceList
        title="Current item observations"
        observations={currentObservations}
        onClear={currentObservations.length ? onClearCurrentObservations : undefined}
      />
      {Object.entries(outcomeObservations).map(([id, observations]) => (
        <EvidenceList
          key={id}
          title={`Outcome ${shortId(id)} observations`}
          observations={observations}
          onClear={() => onClearOutcomeObservations(id)}
        />
      ))}
    </section>
  );
}

function EvidenceList({
  title,
  observations,
  onClear
}: {
  title: string;
  observations: ManualListingObservation[];
  onClear?: () => void;
}) {
  return (
    <div className="evidence-list-block">
      <div className="section-heading compact-heading">
        <h3>{title}</h3>
        {onClear && (
          <button className="secondary-button" type="button" onClick={onClear}>
            Clear
          </button>
        )}
      </div>
      {observations.length ? (
        <ul className="evidence-list">
          {observations.map((observation, index) => (
            <li key={`${observation.external_listing_id ?? "manual"}-${index}`}>
              <strong>
                {observation.amount} {currencyLabel(observation.currency_asset_id)}
              </strong>
              <small>
                {[observation.external_listing_id, observation.observed_at, observation.item_summary, observation.notes]
                  .filter(Boolean)
                  .join(" · ") || "manual observation"}
              </small>
            </li>
          ))}
        </ul>
      ) : (
        <p className="muted">No observations entered.</p>
      )}
    </div>
  );
}

function optionalText(value: string): string | null {
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

function currencyLabel(assetId: string): string {
  return CURRENCY_OPTIONS.find((option) => option.value === assetId)?.label ?? assetId;
}

function shortId(id: string): string {
  return id.length > 18 ? `${id.slice(0, 10)}...${id.slice(-6)}` : id;
}
