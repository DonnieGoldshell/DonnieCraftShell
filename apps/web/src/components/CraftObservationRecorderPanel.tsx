import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  DEFAULT_CRAFTING_DATASET,
  DEFAULT_GAME_DATA_DATASET,
  DEFAULT_LEAGUE,
  exportCraftObservations,
  recordCraftObservation,
  saveObservationWorkspaceRecord,
  type ActionAnalysis,
  type CraftObservationRecordResponse
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

export function CraftObservationRecorderPanel({
  actions,
  defaultBeforeText,
  league,
  craftingDatasetVersion,
  modifierDatasetVersion,
  targetActionId
}: Props) {
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
  const [manualOutcomeId, setManualOutcomeId] = useState("");
  const [manualReason, setManualReason] = useState("");
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
    if (!selectedAction) {
      setError("Choose an analyzed craft action with outcome IDs.");
      return;
    }
    if (!beforeText.trim() || !afterText.trim()) {
      setError("Before and after clipboard text are required.");
      return;
    }
    setBusy(true);
    try {
      const response = await recordCraftObservation({
        before_clipboard_text: beforeText,
        after_clipboard_text: afterText,
        action_id: selectedAction.actionId,
        source_outcome_set_id: selectedAction.sourceOutcomeSetId,
        item_class: "Quivers",
        league: league || DEFAULT_LEAGUE,
        observed_at: new Date().toISOString(),
        source_id: "browser-manual-recorder-session",
        game: "Path of Exile 2",
        crafting_dataset_version: craftingDatasetVersion || DEFAULT_CRAFTING_DATASET,
        modifier_dataset_version: modifierDatasetVersion || DEFAULT_GAME_DATA_DATASET,
        synthetic: false,
        manual_outcome_id: optionalText(manualOutcomeId),
        manual_reason: optionalText(manualReason),
        outcome_candidates: selectedAction.outcomeCandidates
      });
      const workspace = await saveObservationWorkspaceRecord({ record: response.export_record });
      setSaved((records) => [...records, response]);
      setExportJson("");
      setWorkspaceMessage(
        `${workspace.status}: ${workspace.raw_record_id}. Observation workspace ${workspace.persistence.persistence_enabled ? "persisted" : "in memory"}.`
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to record observation.");
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
    <section className="panel recorder-panel">
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
          recorded until you submit an observation.
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
          Manual outcome ID
          <select value={manualOutcomeId} onChange={(event) => setManualOutcomeId(event.target.value)}>
            <option value="">Auto classify or unclassified</option>
            {selectedAction?.outcomeCandidates.map((outcome) => (
              <option key={outcome.outcome_id} value={outcome.outcome_id}>
                {shortId(outcome.outcome_id)}
              </option>
            ))}
          </select>
        </label>
        <label className="wide-field">
          Manual classification reason
          <input
            value={manualReason}
            onChange={(event) => setManualReason(event.target.value)}
            placeholder="required context if manually selecting an outcome"
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
          {busy ? "Recording..." : "Record Observation"}
        </button>
        {error && <p className="error-message compact">{error}</p>}
      </form>
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
}

function optionalText(value: string): string | null {
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

function shortId(id: string): string {
  return id.length > 18 ? `${id.slice(0, 10)}...${id.slice(-6)}` : id;
}
