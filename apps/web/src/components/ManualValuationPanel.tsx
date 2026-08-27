import { forwardRef, FormEvent, useEffect, useMemo, useState } from "react";
import {
  DIVINE_ASSET_ID,
  EXALTED_ASSET_ID,
  type ActionAnalysis,
  clearManualValuationWorkspaceSubject,
  deleteManualValuationWorkspaceEvidence,
  listManualValuationWorkspaceEvidence,
  previewManualValuation,
  saveManualValuationWorkspaceEvidence,
  type ManualListingObservation,
  type ManualValuationPreviewResponse,
  type ManualValuationWorkspaceRecord,
  updateManualValuationWorkspaceEvidence
} from "@/api/advisor";
import type { EditableManualListingObservation } from "./AdvisorWorkbench";

type OutcomeOption = {
  actionId: string;
  actionName: string;
  outcomeId: string;
};

type Props = {
  actions: ActionAnalysis[];
  league: string;
  clipboardText: string;
  currentObservations: EditableManualListingObservation[];
  outcomeObservations: Record<string, EditableManualListingObservation[]>;
  outcomeValuationTarget?: {
    actionId: string | null;
    actionName: string | null;
    outcomeId: string | null;
    outcomeIds: string[];
  } | null;
  currentValuationReadiness?: string | null;
  onAddCurrentObservation: (observation: EditableManualListingObservation) => void;
  onAddOutcomeObservation: (outcomeId: string, observation: EditableManualListingObservation) => void;
  onUpdateCurrentObservation: (index: number, observation: EditableManualListingObservation) => void;
  onUpdateOutcomeObservation: (outcomeId: string, index: number, observation: EditableManualListingObservation) => void;
  onRemoveCurrentObservation: (index: number) => void;
  onRemoveOutcomeObservation: (outcomeId: string, index: number) => void;
  onClearCurrentObservations: () => void;
  onClearOutcomeObservations: (outcomeId: string) => void;
  onReplaceCurrentObservations: (observations: EditableManualListingObservation[]) => void;
  onReplaceOutcomeObservations: (outcomeId: string, observations: EditableManualListingObservation[]) => void;
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
  comparable_clipboard_text: "",
  notes: ""
};

export const ManualValuationPanel = forwardRef<HTMLElement, Props>(function ManualValuationPanel(
  {
    actions,
    league,
    clipboardText,
    currentObservations,
    outcomeObservations,
    outcomeValuationTarget,
    currentValuationReadiness,
    onAddCurrentObservation,
    onAddOutcomeObservation,
    onUpdateCurrentObservation,
    onUpdateOutcomeObservation,
    onRemoveCurrentObservation,
    onRemoveOutcomeObservation,
    onClearCurrentObservations,
    onClearOutcomeObservations,
    onReplaceCurrentObservations,
    onReplaceOutcomeObservations
  },
  ref
) {
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
  const [persistenceStatus, setPersistenceStatus] = useState<string | null>(null);
  const [persistenceBusy, setPersistenceBusy] = useState(false);
  const targetedOutcomeIsAvailable = Boolean(
    outcomeValuationTarget?.outcomeId &&
      outcomeOptions.some((option) => option.outcomeId === outcomeValuationTarget.outcomeId)
  );
  const targetedOutcomeProgress = useMemo(
    () => buildOutcomeProgress(outcomeValuationTarget, outcomeObservations),
    [outcomeValuationTarget, outcomeObservations]
  );

  useEffect(() => {
    if (targetedOutcomeIsAvailable && outcomeValuationTarget?.outcomeId) {
      setTarget("outcome");
      setOutcomeId(outcomeValuationTarget.outcomeId);
      setError(null);
      setPreview(null);
    }
  }, [outcomeValuationTarget?.outcomeId, targetedOutcomeIsAvailable]);

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
      comparable_clipboard_text: optionalText(draft.comparable_clipboard_text),
      notes: optionalText(draft.notes)
    };
    if (target === "current") {
      onAddCurrentObservation(observation);
    } else {
      onAddOutcomeObservation(outcomeId, observation);
    }
    setDraft({ ...emptyObservation, currency_asset_id: draft.currency_asset_id });
  }

  async function loadPersistedEvidence() {
    setError(null);
    setPersistenceStatus(null);
    if (target === "outcome" && !outcomeId) {
      setError("Choose an outcome ID before loading persisted evidence.");
      return;
    }
    setPersistenceBusy(true);
    try {
      const subjectId = currentSubjectId(target, outcomeId);
      const result = await listManualValuationWorkspaceEvidence(subjectId);
      const observations = result.records.map(workspaceRecordToObservation);
      if (target === "current") {
        onReplaceCurrentObservations(observations);
      } else {
        onReplaceOutcomeObservations(outcomeId, observations);
      }
      setPersistenceStatus(
        `Loaded ${observations.length} persisted observation${observations.length === 1 ? "" : "s"} from ${
          result.persistence.storage_mode
        } workspace.`
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to load persisted valuation evidence.");
    } finally {
      setPersistenceBusy(false);
    }
  }

  async function savePersistedEvidence() {
    setError(null);
    setPersistenceStatus(null);
    if (target === "outcome" && !outcomeId) {
      setError("Choose an outcome ID before saving persisted evidence.");
      return;
    }
    const observations = target === "current" ? currentObservations : outcomeObservations[outcomeId] ?? [];
    if (!observations.length) {
      setError("Add or load at least one observation before saving persisted evidence.");
      return;
    }

    setPersistenceBusy(true);
    try {
      const saved = await Promise.all(
        observations.map((observation) => {
          const record = observationToWorkspaceRecord(observation, target, outcomeId, league);
          return observation.evidence_id
            ? updateManualValuationWorkspaceEvidence(observation.evidence_id, { record })
            : saveManualValuationWorkspaceEvidence({ record });
        })
      );
      const records = saved.map((result) => result.record);
      if (records.some((record) => !record)) {
        throw new Error("Manual valuation workspace save response did not include all saved records.");
      }
      const persisted = records.map((record) => workspaceRecordToObservation(record as ManualValuationWorkspaceRecord));
      if (target === "current") {
        onReplaceCurrentObservations(persisted);
      } else {
        onReplaceOutcomeObservations(outcomeId, persisted);
      }
      setPersistenceStatus(`Saved ${persisted.length} observation${persisted.length === 1 ? "" : "s"} locally.`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to save persisted valuation evidence.");
    } finally {
      setPersistenceBusy(false);
    }
  }

  async function clearPersistedSubject() {
    setError(null);
    setPersistenceStatus(null);
    if (target === "outcome" && !outcomeId) {
      setError("Choose an outcome ID before clearing persisted evidence.");
      return;
    }
    setPersistenceBusy(true);
    try {
      const result = await clearManualValuationWorkspaceSubject(currentSubjectId(target, outcomeId));
      if (target === "current") {
        onClearCurrentObservations();
      } else {
        onClearOutcomeObservations(outcomeId);
      }
      setPersistenceStatus(`Cleared ${result.deleted_count} persisted observation${result.deleted_count === 1 ? "" : "s"}.`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to clear persisted valuation evidence.");
    } finally {
      setPersistenceBusy(false);
    }
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
        subject_clipboard_text: target === "current" ? optionalText(clipboardText) : null,
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
    <section ref={ref} className="panel evidence-panel" aria-label="Manual valuation evidence workflow" tabIndex={-1}>
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
      {outcomeValuationTarget && (
        <div className="evidence-target-callout" aria-label="Targeted outcome valuation progress">
          <strong>
            Targeted outcome evidence
            {outcomeValuationTarget.actionName ? `: ${outcomeValuationTarget.actionName}` : ""}
          </strong>
          {targetedOutcomeIsAvailable && outcomeValuationTarget.outcomeId ? (
            <p>
              Outcome {shortId(outcomeValuationTarget.outcomeId)} selected. {targetedOutcomeProgress.saved}/
              {targetedOutcomeProgress.total} blocked outcomes have saved local evidence;{" "}
              {targetedOutcomeProgress.missing} still need outcome valuation evidence. Current item valuation:{" "}
              {currentValuationReadiness ? titleCase(currentValuationReadiness) : "Unknown"}.
            </p>
          ) : (
            <p>
              The selected readiness target is no longer present in the current analysis. Re-run analysis before saving
              outcome evidence for it.
            </p>
          )}
          <small>
            Preview and save are explicit steps. Saved manual evidence is still inactive until it is submitted with a
            deliberate Advisor rerun.
          </small>
        </div>
      )}
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
          Comparable Advanced Copy
          <textarea
            value={draft.comparable_clipboard_text}
            onChange={(event) => setDraft({ ...draft, comparable_clipboard_text: event.target.value })}
            placeholder="optional full Advanced Copy text from the comparable listing"
            rows={7}
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
        <button className="secondary-button" type="button" onClick={loadPersistedEvidence} disabled={persistenceBusy}>
          Load Persisted Evidence
        </button>
        <button className="secondary-button" type="button" onClick={savePersistedEvidence} disabled={persistenceBusy}>
          Save Subject Evidence
        </button>
        <button className="secondary-button" type="button" onClick={clearPersistedSubject} disabled={persistenceBusy}>
          Clear Persisted Subject
        </button>
        {error && <p className="error-message compact">{error}</p>}
        {persistenceStatus && <p className="muted compact">{persistenceStatus}</p>}
      </form>

      <EvidenceList
        title="Current item observations"
        observations={currentObservations}
        onUpdate={onUpdateCurrentObservation}
        onRemove={(index) => removePersistedCurrent(index, currentObservations[index], onRemoveCurrentObservation, setError)}
        onClear={currentObservations.length ? onClearCurrentObservations : undefined}
      />
      {Object.entries(outcomeObservations).map(([id, observations]) => (
        <EvidenceList
          key={id}
          title={`Outcome ${shortId(id)} observations`}
          observations={observations}
          onUpdate={(index, observation) => onUpdateOutcomeObservation(id, index, observation)}
          onRemove={(index) =>
            removePersistedOutcome(id, index, observations[index], onRemoveOutcomeObservation, setError)
          }
          onClear={() => onClearOutcomeObservations(id)}
        />
      ))}
      {preview && <ValuationPreview preview={preview} />}
    </section>
  );
});

function EvidenceList({
  title,
  observations,
  onUpdate,
  onRemove,
  onClear
}: {
  title: string;
  observations: EditableManualListingObservation[];
  onUpdate: (index: number, observation: EditableManualListingObservation) => void;
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
              {observation.comparable_item ? (
                <ComparableItemSummary comparable={observation.comparable_item} />
              ) : observation.comparable_clipboard_text ? (
                <small>Comparable item text attached; preview or save parses and verifies the structured item state.</small>
              ) : (
                <small>Price-only evidence; not structurally verified against parsed comparable item state.</small>
              )}
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
              {" "}
              <strong>{result.normalized_value ? formatEconomicValue(result.normalized_value) : "Unconvertible"}</strong>
              {result.comparable_item && <ComparableItemSummary comparable={result.comparable_item} />}
              {result.comparable_relevance && <ComparableRelevanceSummary relevance={result.comparable_relevance} />}
              {result.comparable_quality_delta && <ComparableQualityDeltaSummary qualityDelta={result.comparable_quality_delta} />}
              {result.warnings.length > 0 && <small>{result.warnings.join(" ")}</small>}
            </li>
          ))}
        </ul>
      )}
      {preview.warnings.length > 0 && <p className="muted">{preview.warnings.join(" ")}</p>}
    </div>
  );
}

type StructuredComparableItem = NonNullable<ManualListingObservation["comparable_item"]>;
type ComparableRelevance = NonNullable<ManualValuationPreviewResponse["comparable_results"][number]["comparable_relevance"]>;
type ComparableQualityDelta = NonNullable<ManualValuationPreviewResponse["comparable_results"][number]["comparable_quality_delta"]>;

function ComparableItemSummary({ comparable }: { comparable: StructuredComparableItem }) {
  const item = comparable.item;
  const explicitCount =
    ((item.prefixes as unknown[] | undefined)?.length ?? 0) + ((item.suffixes as unknown[] | undefined)?.length ?? 0);
  return (
    <div className="comparable-item-summary" aria-label="Parsed comparable item state">
      <strong>
        {[item.item_name, item.base_type].filter(Boolean).join(", ") || "Parsed comparable item"}
      </strong>
      <small>
        {[item.rarity, item.item_class, item.item_level ? `ilvl ${item.item_level}` : null, `${explicitCount} explicit modifiers`]
          .filter(Boolean)
          .join(" · ")}
      </small>
      {comparable.warnings.length > 0 && <small>{comparable.warnings.join(" ")}</small>}
    </div>
  );
}

function ComparableRelevanceSummary({ relevance }: { relevance: ComparableRelevance }) {
  const differenceCount = relevance.differing_modifiers.length + relevance.missing_modifiers.length + relevance.extra_modifiers.length;
  const firstDifference =
    relevance.differing_modifiers[0] ?? relevance.missing_modifiers[0] ?? relevance.extra_modifiers[0] ?? null;
  return (
    <div className="comparable-relevance-summary" aria-label="Comparable relevance assessment">
      <strong>
        {relevance.band} relevance{relevance.score ? ` (${relevance.score})` : ""}
      </strong>
      <small>
        {relevance.matched_modifiers.length} matched modifier{relevance.matched_modifiers.length === 1 ? "" : "s"} ·{" "}
        {differenceCount} structural difference{differenceCount === 1 ? "" : "s"}
      </small>
      {firstDifference && (
        <small>
          {firstDifference.relationship}:{" "}
          {[firstDifference.current_display_name, firstDifference.comparable_display_name].filter(Boolean).join(" vs ")}
        </small>
      )}
      {relevance.warnings.length > 0 && <small>{relevance.warnings.join(" ")}</small>}
    </div>
  );
}

function ComparableQualityDeltaSummary({ qualityDelta }: { qualityDelta: ComparableQualityDelta }) {
  const firstDirectional =
    qualityDelta.modifier_deltas.find((delta) => delta.relationship === "CURRENT_BETTER" || delta.relationship === "COMPARABLE_BETTER") ??
    qualityDelta.modifier_deltas.find((delta) => delta.relationship === "ROUGHLY_EQUIVALENT" || delta.origin_difference) ??
    qualityDelta.modifier_deltas[0] ??
    null;
  return (
    <div className="comparable-quality-summary" aria-label="Comparable modifier quality delta">
      <strong>Modifier quality delta</strong>
      <small>
        Current better {qualityDelta.current_better_count} · Comparable better {qualityDelta.comparable_better_count} · Equivalent{" "}
        {qualityDelta.roughly_equivalent_count} · Unknown {qualityDelta.unknown_count}
      </small>
      {firstDirectional && (
        <small>
          {firstDirectional.relationship}:{" "}
          {[firstDirectional.current_display_name, firstDirectional.comparable_display_name].filter(Boolean).join(" vs ")}
          {firstDirectional.current_tier || firstDirectional.comparable_tier
            ? ` (T${firstDirectional.current_tier ?? "?"} vs T${firstDirectional.comparable_tier ?? "?"})`
            : ""}
          {firstDirectional.origin_difference ? " · origin differs" : ""}
        </small>
      )}
      {qualityDelta.warnings.length > 0 && <small>{qualityDelta.warnings.join(" ")}</small>}
    </div>
  );
}

function optionalText(value: string): string | null {
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

function currentSubjectId(target: "current" | "outcome", outcomeId: string): string {
  return target === "current" ? "current" : `outcome:${outcomeId}`;
}

function workspaceRecordToObservation(record: ManualValuationWorkspaceRecord): EditableManualListingObservation {
  return {
    evidence_id: record.evidence_id,
    amount: record.amount,
    currency_asset_id: record.currency_asset_id,
    external_listing_id: record.external_listing_id,
    observed_at: record.observed_at,
    item_summary: record.item_summary,
    comparable_clipboard_text: record.comparable_clipboard_text,
    comparable_item: record.comparable_item,
    notes: record.notes
  };
}

function observationToWorkspaceRecord(
  observation: EditableManualListingObservation,
  target: "current" | "outcome",
  outcomeId: string,
  league: string
): ManualValuationWorkspaceRecord {
  return {
    evidence_id: observation.evidence_id,
    subject_id: currentSubjectId(target, outcomeId),
    subject_type: target === "current" ? "CURRENT_ITEM" : "HYPOTHETICAL_OUTCOME",
    outcome_id: target === "current" ? null : outcomeId,
    league,
    strategy: "STRICT",
    amount: observation.amount,
    currency_asset_id: observation.currency_asset_id,
    external_listing_id: observation.external_listing_id ?? null,
    observed_at: observation.observed_at ?? null,
    item_summary: observation.item_summary ?? null,
    comparable_clipboard_text: observation.comparable_clipboard_text ?? null,
    comparable_item: observation.comparable_item ?? null,
    notes: observation.notes ?? null,
    created_at: null,
    updated_at: null
  };
}

async function removePersistedCurrent(
  index: number,
  observation: EditableManualListingObservation | undefined,
  removeLocal: (index: number) => void,
  setError: (message: string | null) => void
) {
  await removePersistedObservation(index, observation, removeLocal, setError);
}

async function removePersistedOutcome(
  outcomeId: string,
  index: number,
  observation: EditableManualListingObservation | undefined,
  removeLocal: (outcomeId: string, index: number) => void,
  setError: (message: string | null) => void
) {
  await removePersistedObservation(
    index,
    observation,
    (removedIndex) => removeLocal(outcomeId, removedIndex),
    setError
  );
}

async function removePersistedObservation(
  index: number,
  observation: EditableManualListingObservation | undefined,
  removeLocal: (index: number) => void,
  setError: (message: string | null) => void
) {
  setError(null);
  try {
    if (observation?.evidence_id) {
      await deleteManualValuationWorkspaceEvidence(observation.evidence_id);
    }
    removeLocal(index);
  } catch (caught) {
    setError(caught instanceof Error ? caught.message : "Unable to remove persisted valuation evidence.");
  }
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

function buildOutcomeProgress(
  target:
    | {
        outcomeIds: string[];
      }
    | null
    | undefined,
  outcomeObservations: Record<string, EditableManualListingObservation[]>
): { total: number; saved: number; missing: number } {
  const outcomeIds = target?.outcomeIds ?? [];
  const saved = outcomeIds.filter((outcomeId) =>
    (outcomeObservations[outcomeId] ?? []).some((observation) => Boolean(observation.evidence_id))
  ).length;
  return {
    total: outcomeIds.length,
    saved,
    missing: Math.max(outcomeIds.length - saved, 0)
  };
}
