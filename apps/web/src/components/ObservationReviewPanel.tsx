import { useState } from "react";
import {
  reviewCraftObservations,
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
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function loadBatch() {
    setError(null);
    setAcceptedJson("");
    setManifestJson("");
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
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to export accepted observations.");
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
