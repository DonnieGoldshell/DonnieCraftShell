import { useState } from "react";
import {
  buildCuratedObservationDatasets,
  exportObservationWorkspaceBackup,
  exportObservationWorkspaceAccepted,
  listEmpiricalDatasets,
  listObservationWorkspace,
  registerEmpiricalDataset,
  restoreObservationWorkspaceBackup,
  reviewCraftObservations,
  reviewObservationWorkspace,
  type CuratedObservationBuildResponse,
  type EmpiricalDatasetListResponse,
  type EmpiricalDatasetRegisterResponse,
  type ObservationReviewDecision,
  type ObservationReviewResponse,
  type ObservationWorkspaceListResponse
} from "@/api/advisor";

type DecisionState = Record<string, { status: string; note: string }>;

export function ObservationReviewPanel() {
  const [batchText, setBatchText] = useState("");
  const [review, setReview] = useState<ObservationReviewResponse | null>(null);
  const [workspace, setWorkspace] = useState<ObservationWorkspaceListResponse | null>(null);
  const [workspaceLoaded, setWorkspaceLoaded] = useState(false);
  const [decisions, setDecisions] = useState<DecisionState>({});
  const [acceptedJson, setAcceptedJson] = useState("");
  const [manifestJson, setManifestJson] = useState("");
  const [backupJson, setBackupJson] = useState("");
  const [restoreText, setRestoreText] = useState("");
  const [restoreMode, setRestoreMode] = useState("MERGE");
  const [restoreSummary, setRestoreSummary] = useState("");
  const [buildResult, setBuildResult] = useState<CuratedObservationBuildResponse | null>(null);
  const [datasetJson, setDatasetJson] = useState("");
  const [registryResult, setRegistryResult] = useState<EmpiricalDatasetRegisterResponse | null>(null);
  const [registeredDatasets, setRegisteredDatasets] = useState<EmpiricalDatasetListResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function loadBatch() {
    setError(null);
    setAcceptedJson("");
    setManifestJson("");
    setBuildResult(null);
    setDatasetJson("");
    setRegistryResult(null);
    setRegisteredDatasets(null);
    try {
      const payload = JSON.parse(batchText);
      setBusy(true);
      const response = await reviewCraftObservations({ batches: [payload], decisions: [] });
      setReview(response);
      setWorkspaceLoaded(false);
      setDecisions(
        Object.fromEntries(response.records.map((record) => [record.raw_record_id, { status: record.status, note: "" }]))
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to load observation batch.");
    } finally {
      setBusy(false);
    }
  }

  async function loadWorkspace() {
    setError(null);
    setAcceptedJson("");
    setManifestJson("");
    setBuildResult(null);
    setDatasetJson("");
    setRegistryResult(null);
    setRegisteredDatasets(null);
    try {
      setBusy(true);
      const listed = await listObservationWorkspace();
      setWorkspace(listed);
      setWorkspaceLoaded(true);
      setBatchText(JSON.stringify({ observations: listed.entries.map((entry) => entry.record) }, null, 2));
      const response = await reviewCraftObservations({
        observations: listed.entries.map((entry) => entry.record),
        decisions: listed.entries.map((entry) => entry.decision)
      });
      setReview(response);
      setDecisions(
        Object.fromEntries(
          listed.entries.map((entry) => [
            entry.raw_record_id,
            { status: entry.decision.status, note: entry.decision.note ?? "" }
          ])
        )
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to load observation workspace.");
    } finally {
      setBusy(false);
    }
  }

  async function exportAccepted() {
    if (!review) return;
    setError(null);
    try {
      const reviewDecisions: ObservationReviewDecision[] = review.records.map((record) => ({
        raw_record_id: record.raw_record_id,
        status: decisions[record.raw_record_id]?.status ?? "PENDING",
        note: optionalText(decisions[record.raw_record_id]?.note ?? null),
        reviewer_id: "browser-observation-review-session"
      }));
      setBusy(true);
      const response = workspaceLoaded
        ? (await reviewObservationWorkspace({ decisions: reviewDecisions })).review
        : await reviewCraftObservations({
            batches: [JSON.parse(batchText)],
            decisions: reviewDecisions
          });
      const acceptedExport = workspaceLoaded
        ? (await exportObservationWorkspaceAccepted()).accepted_export
        : response.accepted_export;
      setReview(response);
      setAcceptedJson(JSON.stringify(acceptedExport, null, 2));
      setManifestJson(JSON.stringify(response.review_manifest, null, 2));
      setBuildResult(null);
      setDatasetJson("");
      setRegistryResult(null);
      setRegisteredDatasets(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to export accepted observations.");
    } finally {
      setBusy(false);
    }
  }

  async function exportBackup() {
    setError(null);
    setRestoreSummary("");
    try {
      setBusy(true);
      const response = await exportObservationWorkspaceBackup();
      setBackupJson(JSON.stringify(response.backup, null, 2));
      setRestoreText(JSON.stringify(response.backup, null, 2));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to export workspace backup.");
    } finally {
      setBusy(false);
    }
  }

  async function restoreBackup() {
    setError(null);
    setRestoreSummary("");
    try {
      const backup = JSON.parse(restoreText);
      if (
        restoreMode === "REPLACE" &&
        !window.confirm("Replace the current local observation workspace with this validated backup?")
      ) {
        return;
      }
      setBusy(true);
      const response = await restoreObservationWorkspaceBackup({ backup, mode: restoreMode });
      setWorkspace({
        workspace_version: response.workspace_version,
        entries: response.entries,
        persistence: response.persistence,
        warnings: response.warnings
      });
      setRestoreSummary(
        `${response.restore.status}: ${response.restore.records_imported} records imported, ${response.restore.records_already_present} already present, ${response.restore.records_conflicting} conflicting, ${response.restore.decisions_imported} decisions imported.`
      );
      if (response.restore.status === "RESTORED") {
        setWorkspaceLoaded(true);
        setBatchText(JSON.stringify({ observations: response.entries.map((entry) => entry.record) }, null, 2));
        const reviewResponse = await reviewCraftObservations({
          observations: response.entries.map((entry) => entry.record),
          decisions: response.entries.map((entry) => entry.decision)
        });
        setReview(reviewResponse);
        setDecisions(
          Object.fromEntries(
            response.entries.map((entry) => [
              entry.raw_record_id,
              { status: entry.decision.status, note: entry.decision.note ?? "" }
            ])
          )
        );
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to restore workspace backup.");
    } finally {
      setBusy(false);
    }
  }

  async function buildDatasets() {
    if (!acceptedJson) return;
    setError(null);
    try {
      const acceptedExport = JSON.parse(acceptedJson);
      setBusy(true);
      const response = await buildCuratedObservationDatasets({
        accepted_export: acceptedExport,
        dataset_id_prefix: "empirical-probability"
      });
      setBuildResult(response);
      setDatasetJson(JSON.stringify(response.datasets, null, 2));
      setRegistryResult(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to build empirical datasets.");
    } finally {
      setBusy(false);
    }
  }

  async function registerFirstDataset() {
    if (!buildResult?.datasets.length) return;
    setError(null);
    try {
      setBusy(true);
      const response = await registerEmpiricalDataset({ dataset: buildResult.datasets[0] });
      setRegistryResult(response);
      setRegisteredDatasets(await listEmpiricalDatasets());
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to register empirical dataset.");
    } finally {
      setBusy(false);
    }
  }

  async function refreshRegisteredDatasets() {
    setError(null);
    try {
      setBusy(true);
      setRegisteredDatasets(await listEmpiricalDatasets());
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to list empirical datasets.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel recorder-panel">
      <div className="section-heading">
        <h2>Observation Review</h2>
        <span className="count">{review?.records.length ?? 0}</span>
      </div>
      <p className="muted">
        Review persisted or pasted recorder evidence before empirical import. Accepted observations are exported
        unchanged; review decisions stay in a separate manifest.
      </p>
      <button className="secondary-button" type="button" onClick={loadWorkspace} disabled={busy}>
        {busy ? "Loading..." : "Load Persisted Workspace"}
      </button>
      {workspace && (
        <p className="muted">
          Workspace persistence: {workspace.persistence.storage_mode}
          {workspace.persistence.persistence_enabled ? " active" : " disabled"} -{" "}
          {workspace.persistence.loaded_record_count} records - {workspace.persistence.loaded_decision_count} decisions
          {workspace.persistence.skipped_entry_count ? ` - ${workspace.persistence.skipped_entry_count} skipped` : ""}
        </p>
      )}
      <div className="backup-controls">
        <button className="secondary-button" type="button" onClick={exportBackup} disabled={busy}>
          {busy ? "Working..." : "Export Workspace Backup"}
        </button>
        <label>
          Restore mode
          <select value={restoreMode} onChange={(event) => setRestoreMode(event.target.value)}>
            <option value="MERGE">Merge</option>
            <option value="REPLACE">Replace</option>
          </select>
        </label>
      </div>
      <p className="muted">
        Backups copy raw workspace evidence and review decisions only. Replace validates the whole backup before changing
        local evidence.
      </p>
      {backupJson && (
        <label className="wide-field">
          Workspace backup JSON
          <textarea readOnly value={backupJson} rows={6} />
        </label>
      )}
      <label className="wide-field">
        Restore backup JSON
        <textarea
          value={restoreText}
          onChange={(event) => setRestoreText(event.target.value)}
          rows={6}
          placeholder="Paste a workspace backup JSON envelope"
        />
      </label>
      <button className="secondary-button" type="button" onClick={restoreBackup} disabled={busy || !restoreText.trim()}>
        Restore Workspace Backup
      </button>
      {restoreSummary && <p className="muted">{restoreSummary}</p>}
      <label className="wide-field">
        Recorder export JSON
        <textarea
          value={batchText}
          onChange={(event) => setBatchText(event.target.value)}
          rows={8}
          placeholder="Paste a Craft Observation Recorder export payload"
        />
      </label>
      <button className="secondary-button" type="button" onClick={loadBatch} disabled={busy || !batchText.trim()}>
        {busy ? "Reviewing..." : "Load Review Batch"}
      </button>
      {error && <p className="error-message compact">{error}</p>}

      {review && (
        <>
          <ul className="evidence-list">
            {review.records.map((record) => (
              <li key={record.raw_record_id}>
                <strong>{shortId(record.raw_record_id)}</strong>
                <small>
                  {[record.classification_method, record.unclassified ? "UNCLASSIFIED" : record.outcome_id && shortId(record.outcome_id)]
                    .filter(Boolean)
                    .join(" · ")}
                </small>
                <select
                  aria-label={`Review status ${record.raw_record_id}`}
                  value={decisions[record.raw_record_id]?.status ?? "PENDING"}
                  onChange={(event) =>
                    setDecisions((current) => ({
                      ...current,
                      [record.raw_record_id]: {
                        status: event.target.value,
                        note: current[record.raw_record_id]?.note ?? ""
                      }
                    }))
                  }
                >
                  <option value="PENDING">Pending</option>
                  <option value="ACCEPTED">Accepted</option>
                  <option value="REJECTED">Rejected</option>
                </select>
                <input
                  aria-label={`Review note ${record.raw_record_id}`}
                  value={decisions[record.raw_record_id]?.note ?? ""}
                  onChange={(event) =>
                    setDecisions((current) => ({
                      ...current,
                      [record.raw_record_id]: {
                        status: current[record.raw_record_id]?.status ?? "PENDING",
                        note: event.target.value
                      }
                    }))
                  }
                  placeholder="review note"
                />
                {record.warnings.length > 0 && <small>{record.warnings.join(" ")}</small>}
              </li>
            ))}
          </ul>
          {review.warnings.length > 0 && <p className="muted">{review.warnings.join(" ")}</p>}
          <button className="secondary-button" type="button" onClick={exportAccepted} disabled={busy}>
            Export Accepted JSON
          </button>
          {acceptedJson && (
            <label className="wide-field">
              Accepted export
              <textarea readOnly value={acceptedJson} rows={8} />
            </label>
          )}
          {manifestJson && (
            <label className="wide-field">
              Review manifest
              <textarea readOnly value={manifestJson} rows={8} />
            </label>
          )}
          {acceptedJson && (
            <button className="secondary-button" type="button" onClick={buildDatasets} disabled={busy}>
              Build Empirical Datasets
            </button>
          )}
          {buildResult && (
            <div className="evidence-list-block">
              <div className="section-heading compact-heading">
                <h3>Curated Import Build</h3>
                <span className="count">{buildResult.dataset_count}</span>
              </div>
              <p className="muted">
                Building datasets does not activate probability evidence or make Advisor EV-ready by itself.
              </p>
              <ul className="evidence-list">
                <li>
                  <strong>{buildResult.accepted_record_count} imported</strong>
                  <small>
                    {buildResult.duplicate_record_count} duplicate · {buildResult.unclassified_record_count} unclassified ·{" "}
                    {buildResult.invalid_record_count} invalid
                  </small>
                </li>
                {buildResult.dataset_ids.map((datasetId) => (
                  <li key={datasetId}>
                    <strong>{shortId(datasetId)}</strong>
                    <small>{datasetId}</small>
                  </li>
                ))}
              </ul>
              {buildResult.warnings.length > 0 && <p className="muted">{buildResult.warnings.join(" ")}</p>}
              <button
                className="secondary-button"
                type="button"
                onClick={registerFirstDataset}
                disabled={busy || buildResult.datasets.length === 0}
              >
                Register First Dataset
              </button>
              <button className="secondary-button" type="button" onClick={refreshRegisteredDatasets} disabled={busy}>
                List Registered Evidence
              </button>
              {registryResult && (
                <p className="muted">
                  {registryResult.status}: {registryResult.dataset_id}. Paste this ID into Empirical evidence dataset
                  before running Advisor analysis.
                </p>
              )}
              {registeredDatasets && (
                <>
                  <p className="muted">
                    Registry persistence: {registeredDatasets.persistence.storage_mode}
                    {registeredDatasets.persistence.persistence_enabled ? " active" : " disabled"} -{" "}
                    {registeredDatasets.persistence.loaded_dataset_count} loaded
                    {registeredDatasets.persistence.skipped_dataset_count
                      ? ` - ${registeredDatasets.persistence.skipped_dataset_count} skipped`
                      : ""}
                  </p>
                  <ul className="evidence-list">
                    {registeredDatasets.datasets.map((dataset) => (
                      <li key={dataset.dataset_id}>
                        <strong>{shortId(dataset.dataset_id)}</strong>
                        <small>
                          {dataset.synthetic ? "SYNTHETIC - " : ""}
                          {dataset.league} - sample {dataset.sample_size} - {dataset.dataset_id}
                        </small>
                      </li>
                    ))}
                  </ul>
                </>
              )}
              <label className="wide-field">
                Built empirical datasets
                <textarea readOnly value={datasetJson} rows={8} />
              </label>
            </div>
          )}
        </>
      )}
    </section>
  );
}

function optionalText(value: string | null): string | null {
  const trimmed = value?.trim() ?? "";
  return trimmed ? trimmed : null;
}

function shortId(id: string): string {
  return id.length > 18 ? `${id.slice(0, 10)}...${id.slice(-6)}` : id;
}
