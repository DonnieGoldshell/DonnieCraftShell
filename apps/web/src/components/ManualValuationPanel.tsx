import { FormEvent, useMemo, useState } from "react";
import {
  DIVINE_ASSET_ID,
  EXALTED_ASSET_ID,
  type ActionAnalysis,
  previewManualValuation,
  type ManualListingObservation,
  type ManualValuationPreviewResponse
} from "@/api/advisor";

type OutcomeOption = {
  actionId: string;
  actionName: string;
  outcomeId: string;
};

type Props = {
  actions: ActionAnalysis[];
  league: string;
  currentObservations: ManualListingObservation[];
  outcomeObservations: Record<string, ManualListingObservation[]>;
  onAddCurrentObservation: (observation: ManualListingObservation) => void;
  onAddOutcomeObservation: (outcomeId: string, observation: ManualListingObservation) => void;
  onUpdateCurrentObservation: (index: number, observation: ManualListingObservation) => void;
  onUpdateOutcomeObservation: (outcomeId: string, index: number, observation: ManualListingObservation) => void;
  onRemoveCurrentObservation: (index: number) => void;
  onRemoveOutcomeObservation: (outcomeId: string, index: number) => void;
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
  league,
  currentObservations,
  outcomeObservations,
  onAddCurrentObservation,
  onAddOutcomeObservation,
  onUpdateCurrentObservation,
  onUpdateOutcomeObservation,
  onRemoveCurrentObservation,
  onRemoveOutcomeObservation,
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
  const [preview, setPreview] = useState<ManualValuationPreviewResponse | null>(null);
  const [previewBusy, setPreviewBusy] = useState(false);

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setPreview(null);
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

  async function previewEvidence() {
    setError(null);
    setPreview(null);
    const observations = target === "current" ? currentObservations : outcomeObservations[outcomeId] ?? [];
    if (target === "outcome" && !outcomeId) {
      setError("Choose an outcome ID before previewing outcome valuation evidence.");
      return;
    }
    if (!observations.length) {
      setError("Add at least one observation before previewing valuation evidence.");
      return;
    }

    setPreviewBusy(true);
    try {
      const result = await previewManualValuation({
        subject_id: target === "current" ? "current" : `outcome:${outcomeId}`,
        subject_type: target === "current" ? "CURRENT_ITEM" : "HYPOTHETICAL_OUTCOME",
        outcome_id: target === "current" ? null : outcomeId,
        league,
        evidence: {
          strategy: "STRICT",
          observations,
          notes:
            target === "current"
              ? "User-entered manual current-item comparable listing evidence."
              : "User-entered manual outcome comparable listing evidence."
        }
      });
      setPreview(result);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to preview valuation evidence.");
    } finally {
      setPreviewBusy(false);
    }
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
        <button className="secondary-button" type="button" onClick={previewEvidence} disabled={previewBusy}>
          {previewBusy ? "Previewing..." : "Preview Valuation Evidence"}
        </button>
        {error && <p className="error-message compact">{error}</p>}
      </form>

      <EvidenceList
        title="Current item observations"
        observations={currentObservations}
        onUpdate={onUpdateCurrentObservation}
        onRemove={onRemoveCurrentObservation}
        onClear={currentObservations.length ? onClearCurrentObservations : undefined}
      />
      {Object.entries(outcomeObservations).map(([id, observations]) => (
        <EvidenceList
          key={id}
          title={`Outcome ${shortId(id)} observations`}
          observations={observations}
          onUpdate={(index, observation) => onUpdateOutcomeObservation(id, index, observation)}
          onRemove={(index) => onRemoveOutcomeObservation(id, index)}
          onClear={() => onClearOutcomeObservations(id)}
        />
      ))}
      {preview && <ValuationPreview preview={preview} />}
    </section>
  );
}

function EvidenceList({
  title,
  observations,
  onUpdate,
  onRemove,
  onClear
}: {
  title: string;
  observations: ManualListingObservation[];
  onUpdate: (index: number, observation: ManualListingObservation) => void;
  onRemove: (index: number) => void;
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
              <div className="evidence-row">
                <label>
                  Amount
                  <input
                    aria-label={`${title} amount ${index + 1}`}
                    inputMode="decimal"
                    value={observation.amount}
                    onChange={(event) => onUpdate(index, { ...observation, amount: event.target.value })}
                  />
                </label>
                <label>
                  Currency
                  <select
                    aria-label={`${title} currency ${index + 1}`}
                    value={observation.currency_asset_id}
                    onChange={(event) =>
                      onUpdate(index, { ...observation, currency_asset_id: event.target.value })
                    }
                  >
                    {CURRENCY_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Listing reference
                  <input
                    aria-label={`${title} listing reference ${index + 1}`}
                    value={observation.external_listing_id ?? ""}
                    onChange={(event) =>
                      onUpdate(index, { ...observation, external_listing_id: optionalText(event.target.value) })
                    }
                  />
                </label>
                <button className="secondary-button" type="button" onClick={() => onRemove(index)}>
                  Remove
                </button>
              </div>
              <small>
                {[observation.observed_at, observation.item_summary, observation.notes].filter(Boolean).join(" · ") ||
                  "manual observation"}
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

function ValuationPreview({ preview }: { preview: ManualValuationPreviewResponse }) {
  return (
    <div className="valuation-preview">
      <div className="section-heading compact-heading">
        <h3>
          {preview.subject_type === "CURRENT_ITEM" ? "Current Item" : `Outcome ${shortId(preview.outcome_id ?? preview.subject_id)}`} Valuation
        </h3>
        <span className="status-chip">{titleCase(preview.readiness)}</span>
      </div>
      <dl className="metric-grid">
        <div>
          <dt>Usable evidence</dt>
          <dd>
            {preview.usable_observation_count}/{preview.observation_count}
          </dd>
        </div>
        <div>
          <dt>Median estimate</dt>
          <dd>{preview.estimated_value ? formatEconomicValue(preview.estimated_value) : "Unavailable"}</dd>
        </div>
        <div>
          <dt>Plausible range</dt>
          <dd>
            {preview.plausible_low && preview.plausible_high
              ? `${formatEconomicValue(preview.plausible_low)} - ${formatEconomicValue(preview.plausible_high)}`
              : "Unavailable"}
          </dd>
        </div>
        <div>
          <dt>Confidence</dt>
          <dd>{preview.confidence ? titleCase(preview.confidence.level) : "Unknown"}</dd>
        </div>
      </dl>
      {preview.comparable_results.length > 0 && (
        <ul className="preview-list">
          {preview.comparable_results.map((result) => (
            <li key={result.comparable_id}>
              <span>
                {result.listing_price} {currencyLabel(result.listing_currency_asset_id)}
              </span>
              <strong>{result.normalized_value ? formatEconomicValue(result.normalized_value) : "Unconvertible"}</strong>
              {result.warnings.length > 0 && <small>{result.warnings.join(" ")}</small>}
            </li>
          ))}
        </ul>
      )}
      {preview.warnings.length > 0 && <p className="muted">{preview.warnings.join(" ")}</p>}
    </div>
  );
}

function optionalText(value: string): string | null {
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

function formatEconomicValue(value: { amount: string; unit: string }): string {
  return `${value.amount} Ex`;
}

function currencyLabel(assetId: string): string {
  return CURRENCY_OPTIONS.find((option) => option.value === assetId)?.label ?? assetId;
}

function titleCase(value: string): string {
  return value
    .toLowerCase()
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function shortId(id: string): string {
  return id.length > 18 ? `${id.slice(0, 10)}...${id.slice(-6)}` : id;
}
