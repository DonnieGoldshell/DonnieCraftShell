import { forwardRef, FormEvent, useEffect, useMemo, useState } from "react";
import {
  DEFAULT_CRAFTING_DATASET,
  DEFAULT_GAME_DATA_DATASET,
  DEFAULT_LEAGUE,
  confirmGuidedCraftObservation,
  exportCraftObservations,
  previewGuidedCraftObservation,
  type ActionAnalysis,
  type CraftObservationRecordResponse,
  type GuidedTrialConfirmRequest,
  type GuidedTrialPreviewRequest,
  type GuidedTrialPreviewResponse
} from "@/api/advisor";

type Props = {
  actions: ActionAnalysis[];
  defaultBeforeText: string;
  league: string;
  craftingDatasetVersion: string;
  modifierDatasetVersion: string;
  targetActionId?: string | null;
};

type SavedObservation = CraftObservationRecordResponse;

export const CraftObservationRecorderPanel = forwardRef<HTMLElement, Props>(function CraftObservationRecorderPanel(
  {
    actions,
    defaultBeforeText,
    league,
    craftingDatasetVersion,
    modifierDatasetVersion,
    targetActionId
  },
  ref
) {
  const actionOptions = useMemo(
    () =>
      actions
        .filter((action) => action.outcome_ids.length > 0)
        .map((action) => ({
          actionId: action.action_id,
          label: action.display_name,
          sourceOutcomeSetId: action.probability?.source_outcome_set_id ?? `manual-recorder:${action.action_id}`,
          outcomeCandidates: action.outcome_ids.map((outcomeId) => ({ outcome_id: outcomeId }))
        })),
    [actions]
  );
  const [actionId, setActionId] = useState("");
  const [beforeText, setBeforeText] = useState(defaultBeforeText);
  const [afterText, setAfterText] = useState("");
  const [gameVersion, setGameVersion] = useState("");
  const [sourceUri, setSourceUri] = useState("local://browser/guided-craft-observation");
  const [confirmationNote, setConfirmationNote] = useState("");
  const [preview, setPreview] = useState<GuidedTrialPreviewResponse | null>(null);
  const [previewRequest, setPreviewRequest] = useState<GuidedTrialPreviewRequest | null>(null);
  const [saved, setSaved] = useState<SavedObservation[]>([]);
  const [exportJson, setExportJson] = useState("");
  const [workspaceMessage, setWorkspaceMessage] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const selectedAction = actionOptions.find((action) => action.actionId === actionId);
  const targetedAction = targetActionId
    ? actionOptions.find((action) => action.actionId === targetActionId)
    : undefined;

  useEffect(() => {
    if (targetActionId && actionOptions.some((action) => action.actionId === targetActionId)) {
      setActionId(targetActionId);
    }
  }, [targetActionId, actionOptions]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setPreview(null);
    setWorkspaceMessage("");
    if (!selectedAction) {
      setError("Choose an analyzed craft action with outcome IDs.");
      return;
    }
    if (!beforeText.trim() || !afterText.trim()) {
      setError("Before and after clipboard text are required.");
      return;
    }
    if (!gameVersion.trim()) {
      setError("Game or patch version is required for guided real-trial provenance.");
      return;
    }
    if (!sourceUri.trim()) {
      setError("Source URI is required for guided real-trial provenance.");
      return;
    }
    setBusy(true);
    try {
      const request: GuidedTrialPreviewRequest = {
        before_clipboard_text: beforeText,
        after_clipboard_text: afterText,
        observed_at: new Date().toISOString(),
        session: {
          action_id: selectedAction.actionId,
          item_class: "Quivers",
          league: league || DEFAULT_LEAGUE,
          game: "Path of Exile 2",
          game_version: gameVersion.trim(),
          crafting_dataset_version: craftingDatasetVersion || DEFAULT_CRAFTING_DATASET,
          modifier_dataset_version: modifierDatasetVersion || DEFAULT_GAME_DATA_DATASET,
          source_id: "browser-guided-real-trial-session",
          source_uri: sourceUri.trim(),
          collection_method: "MANUAL_BEFORE_AFTER_PASTE",
          notes: "Browser guided real-trial capture; operator confirmation required before classification."
        }
      };
      const response = await previewGuidedCraftObservation(request);
      setPreview(response);
      setPreviewRequest(request);
      setExportJson("");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to preview guided observation.");
    } finally {
      setBusy(false);
    }
  }

  async function confirm(confirmUnclassified: boolean) {
    setError(null);
    if (!preview || !previewRequest) {
      setError("Preview the before/after diff before confirming a guided trial.");
      return;
    }
    if (!confirmUnclassified && !preview.proposed_outcome_id) {
      setError("No proposed outcome is available. Save as unclassified instead.");
      return;
    }
    setBusy(true);
    try {
      const request: GuidedTrialConfirmRequest = {
        ...previewRequest,
        operator_confirmed: true,
        confirmed_outcome_id: confirmUnclassified ? null : preview.proposed_outcome_id,
        confirm_unclassified: confirmUnclassified,
        confirmation_note: optionalText(confirmationNote)
      };
      const response = await confirmGuidedCraftObservation(request);
      setSaved((records) => [...records, response.recorded]);
      setPreview(response.preview);
      setExportJson("");
      setWorkspaceMessage(
        `${response.workspace.status}: ${response.workspace.raw_record_id}. Observation workspace ${
          response.workspace.persistence.persistence_enabled ? "persisted" : "in memory"
        }.`
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to confirm guided observation.");
    } finally {
      setBusy(false);
    }
  }

  async function exportRecords() {
    setError(null);
    try {
      const payload = await exportCraftObservations({
        observations: saved.map((record) => record.export_record)
      });
      setExportJson(JSON.stringify(payload, null, 2));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to export observations.");
    }
  }

  return (
    <section ref={ref} className="panel recorder-panel" aria-label="Probability evidence workflow" tabIndex={-1}>
      <div className="section-heading">
        <h2>Craft Observation Recorder</h2>
        <span className="count">{saved.length}</span>
      </div>
      <p className="muted">
        Record real before/after craft observations manually. Recorded evidence is saved to the local observation
        workspace, but it does not affect probability readiness until reviewed, imported, registered, and explicitly selected.
      </p>
      {targetedAction && (
        <p className="muted">
          Targeted from Evidence Readiness: collect probability evidence for {targetedAction.label}. Nothing is
          recorded until you preview the diff and explicitly confirm it.
        </p>
      )}
      <form className="recorder-form" onSubmit={submit}>
        <label>
          Craft action
          <select value={actionId} onChange={(event) => setActionId(event.target.value)}>
            <option value="">Choose analyzed action</option>
            {actionOptions.map((action) => (
              <option key={action.actionId} value={action.actionId}>
                {action.label}
              </option>
            ))}
          </select>
        </label>
        <label>
          Game / patch version
          <input
            value={gameVersion}
            onChange={(event) => setGameVersion(event.target.value)}
            placeholder="required, for example 0.3.0"
          />
        </label>
        <label className="wide-field">
          Source URI
          <input
            value={sourceUri}
            onChange={(event) => setSourceUri(event.target.value)}
            placeholder="local://operator/session-note or source document URI"
          />
        </label>
        <label className="wide-field">
          Operator confirmation note
          <input
            value={confirmationNote}
            onChange={(event) => setConfirmationNote(event.target.value)}
            placeholder="optional note recorded with confirmed or unclassified trial"
          />
        </label>
        <label className="wide-field">
          Before craft clipboard text
          <textarea value={beforeText} onChange={(event) => setBeforeText(event.target.value)} rows={7} />
        </label>
        <label className="wide-field">
          After craft clipboard text
          <textarea
            value={afterText}
            onChange={(event) => setAfterText(event.target.value)}
            rows={7}
            placeholder="Paste the resulting item after performing the craft outside DonnieCraftShell"
          />
        </label>
        <button type="submit" disabled={busy}>
          {busy ? "Previewing..." : "Preview Trial Diff"}
        </button>
        {error && <p className="error-message compact">{error}</p>}
      </form>
      {preview && (
        <div className="result-card">
          <h3>Guided Trial Preview</h3>
          <p className="muted">
            {preview.status}: {preview.classification_reason}
          </p>
          <dl className="summary-list">
            <div>
              <dt>Trial</dt>
              <dd>{shortId(preview.trial_id)}</dd>
            </div>
            <div>
              <dt>Proposed outcome</dt>
              <dd>{preview.proposed_outcome_id ? shortId(preview.proposed_outcome_id) : "Unclassified"}</dd>
            </div>
            <div>
              <dt>Removed modifiers</dt>
              <dd>
                {preview.diff.removed_modifiers.length
                  ? preview.diff.removed_modifiers.map((modifier) => modifier.display_name ?? modifier.raw_text).join(", ")
                  : "None"}
              </dd>
            </div>
            <div>
              <dt>Added modifiers</dt>
              <dd>
                {preview.diff.added_modifiers.length
                  ? preview.diff.added_modifiers.map((modifier) => modifier.display_name ?? modifier.raw_text).join(", ")
                  : "None"}
              </dd>
            </div>
          </dl>
          {preview.warnings.length > 0 && (
            <ul className="warning-list">
              {preview.warnings.map((warning) => (
                <li key={warning}>{warning}</li>
              ))}
            </ul>
          )}
          <div className="button-row">
            <button type="button" onClick={() => confirm(false)} disabled={busy || !preview.proposed_outcome_id}>
              {busy ? "Confirming..." : "Confirm Proposed Outcome"}
            </button>
            <button className="secondary-button" type="button" onClick={() => confirm(true)} disabled={busy}>
              Save as Unclassified
            </button>
          </div>
        </div>
      )}
      {workspaceMessage && <p className="muted">{workspaceMessage}</p>}

      {saved.length ? (
        <>
          <ul className="evidence-list">
            {saved.map((record) => (
              <li key={record.raw_record_id}>
                <strong>{record.classification.method}</strong>
                <small>
                  {[shortId(record.raw_record_id), record.classification.outcome_id && shortId(record.classification.outcome_id)]
                    .filter(Boolean)
                    .join(" · ")}
                </small>
              </li>
            ))}
          </ul>
          <button className="secondary-button" type="button" onClick={exportRecords}>
            Export JSON
          </button>
          {exportJson && (
            <label className="wide-field">
              Export payload
              <textarea readOnly value={exportJson} rows={8} />
            </label>
          )}
        </>
      ) : (
        <p className="muted">No craft observations recorded in this browser session. Use Observation Review to reload persisted workspace evidence.</p>
      )}
    </section>
  );
});

function optionalText(value: string): string | null {
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

function shortId(id: string): string {
  return id.length > 18 ? `${id.slice(0, 10)}...${id.slice(-6)}` : id;
}
