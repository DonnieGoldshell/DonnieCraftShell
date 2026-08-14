import { useState } from "react";
import {
  buildCuratedObservationDatasets,
  listEmpiricalDatasets,
  registerEmpiricalDataset,
  reviewCraftObservations,
  type CuratedObservationBuildResponse,
  type EmpiricalDatasetListResponse,
  type EmpiricalDatasetRegisterResponse,
  type ObservationReviewDecision,
  type ObservationReviewResponse
} from "@/api/advisor";

type DecisionState = Record<string, { status: string; note: string }>;

export function ObservationReviewPanel() {
  const [batchText, setBatchText] = useState("");
  const [review, setReview] = useState<ObservationReviewResponse | null>(null);
  const [decisions, setDecisions] = useState<DecisionState>({});
  const [acceptedJson, setAcceptedJson] = useState("");
  const [manifestJson, setManifestJson] = useState("");
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
      setDecisions(
        Object.fromEntries(response.records.map((record) => [record.raw_record_id, { status: record.status, note: "" }]))
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to load observation batch.");
    } finally {
      setBusy(false);
    }
  }

  async function exportAccepted() {
    if (!review) return;
    setError(null);
    try {
      const parsed = JSON.parse(batchText);
      const reviewDecisions: ObservationReviewDecision[] = review.records.map((record) => ({
        raw_record_id: record.raw_record_id,
        status: decisions[record.raw_record_id]?.status ?? "PENDING",
        note: optionalText(decisions[record.raw_record_id]?.note ?? null),
        reviewer_id: "browser-observation-review-session"
      }));
      setBusy(true);
      const response = await reviewCraftObservations({
        batches: [parsed],
        decisions: reviewDecisions
      });
      setReview(response);
      setAcceptedJson(JSON.stringify(response.accepted_export, null, 2));
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
        Review recorder JSON before empirical import. Accepted observations are exported unchanged; review decisions
        stay in a separate manifest.
      </p>
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
