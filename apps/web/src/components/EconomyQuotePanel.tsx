import { FormEvent, useMemo, useState } from "react";
import {
  EXALTED_ASSET_ID,
  type AdvisorAnalyzeResponse,
  type EconomyQuoteWorkspaceRecord,
  deleteEconomyQuoteWorkspaceQuote,
  listEconomyQuoteWorkspaceQuotes,
  saveEconomyQuoteWorkspaceQuote,
  updateEconomyQuoteWorkspaceQuote
} from "@/api/advisor";
import { displayStatus } from "@/lib/format";

type EconomyTarget = {
  assetId: string;
  actionName?: string | null;
  reason: string;
};

type Props = {
  analysis: AdvisorAnalyzeResponse | null;
  league: string;
};

const emptyDraft = {
  asset_id: "",
  amount: "",
  observed_at: "",
  source_reference: "",
  notes: ""
};

export function EconomyQuotePanel({ analysis, league }: Props) {
  const targets = useMemo(() => economyTargets(analysis), [analysis]);
  const firstTarget = targets[0]?.assetId ?? "";
  const [draft, setDraft] = useState({ ...emptyDraft, asset_id: firstTarget });
  const [records, setRecords] = useState<EconomyQuoteWorkspaceRecord[]>([]);
  const [selectedEvidenceId, setSelectedEvidenceId] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const effectiveAssetId = draft.asset_id || firstTarget;

  async function loadQuotes(assetId = effectiveAssetId) {
    setError(null);
    setStatus(null);
    setBusy(true);
    try {
      const result = await listEconomyQuoteWorkspaceQuotes(league, assetId || undefined);
      setRecords(result.records);
      setStatus(`Loaded ${result.records.length} local quote${result.records.length === 1 ? "" : "s"}.`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to load local economy quotes.");
    } finally {
      setBusy(false);
    }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setStatus(null);
    const assetId = effectiveAssetId.trim();
    const amount = draft.amount.trim();
    if (!assetId) {
      setError("Choose or enter an economy asset ID.");
      return;
    }
    if (!amount) {
      setError("Quote amount is required.");
      return;
    }
    setBusy(true);
    try {
      const record: EconomyQuoteWorkspaceRecord = {
        evidence_id: selectedEvidenceId || null,
        league,
        asset_id: assetId,
        amount,
        currency_asset_id: EXALTED_ASSET_ID,
        observed_at: optionalText(draft.observed_at),
        source_type: "MANUAL_RESEARCH",
        source_reference: optionalText(draft.source_reference),
        notes: optionalText(draft.notes)
      };
      const result = selectedEvidenceId
        ? await updateEconomyQuoteWorkspaceQuote(selectedEvidenceId, { record })
        : await saveEconomyQuoteWorkspaceQuote({ record });
      setSelectedEvidenceId(result.evidence_id ?? "");
      await loadQuotes(assetId);
      setStatus("Saved local economy quote. Re-run analysis to apply it to Advisor costs.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to save local economy quote.");
    } finally {
      setBusy(false);
    }
  }

  async function removeQuote(evidenceId: string) {
    setError(null);
    setStatus(null);
    setBusy(true);
    try {
      await deleteEconomyQuoteWorkspaceQuote(evidenceId);
      if (selectedEvidenceId === evidenceId) {
        setSelectedEvidenceId("");
      }
      setStatus("Deleted local economy quote. Re-run analysis to update Advisor costs.");
      await loadQuotes(effectiveAssetId);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to delete local economy quote.");
    } finally {
      setBusy(false);
    }
  }

  function loadRecord(record: EconomyQuoteWorkspaceRecord) {
    setSelectedEvidenceId(record.evidence_id ?? "");
    setDraft({
      asset_id: record.asset_id,
      amount: record.amount,
      observed_at: record.observed_at ?? "",
      source_reference: record.source_reference ?? "",
      notes: record.notes ?? ""
    });
    setStatus("Loaded quote into the form. Save updates it; analysis is unchanged until re-run.");
  }

  return (
    <section className="tool-card" aria-label="Local economy quote workflow">
      <div className="section-heading">
        <div>
          <h3>Local Economy Quotes</h3>
          <p className="muted">
            Store explicit operator-supplied Exalted-unit prices for missing crafting materials. Saving does not re-run
            analysis.
          </p>
        </div>
      </div>

      {targets.length > 0 && (
        <div className="target-strip" aria-label="Missing economy quote targets">
          {targets.map((target) => (
            <button
              key={`${target.actionName ?? "global"}:${target.assetId}`}
              type="button"
              className="chip-button"
              onClick={() => {
                setDraft((current) => ({ ...current, asset_id: target.assetId }));
                void loadQuotes(target.assetId);
              }}
            >
              {target.actionName ? `${target.actionName}: ` : ""}
              {displayAsset(target.assetId)}
            </button>
          ))}
        </div>
      )}

      <form className="compact-form" onSubmit={submit}>
        <label>
          League
          <input value={league} disabled />
        </label>
        <label>
          Needed asset
          <input
            value={effectiveAssetId}
            onChange={(event) => setDraft((current) => ({ ...current, asset_id: event.target.value }))}
            placeholder="dc:poe2:economy-asset:currency:orb-of-annulment"
          />
        </label>
        <label>
          Quote in Exalted units
          <input
            value={draft.amount}
            onChange={(event) => setDraft((current) => ({ ...current, amount: event.target.value }))}
            placeholder="7.5"
            inputMode="decimal"
          />
        </label>
        <label>
          Observed at
          <input
            value={draft.observed_at}
            onChange={(event) => setDraft((current) => ({ ...current, observed_at: event.target.value }))}
            placeholder="2026-08-21T12:00:00+00:00"
          />
        </label>
        <label>
          Source reference
          <input
            value={draft.source_reference}
            onChange={(event) => setDraft((current) => ({ ...current, source_reference: event.target.value }))}
            placeholder="manual note, trade search, or URL"
          />
        </label>
        <label>
          Notes
          <input
            value={draft.notes}
            onChange={(event) => setDraft((current) => ({ ...current, notes: event.target.value }))}
            placeholder="optional provenance note"
          />
        </label>
        <div className="button-row">
          <button type="submit" disabled={busy}>
            {selectedEvidenceId ? "Update Local Quote" : "Save Local Quote"}
          </button>
          <button type="button" className="secondary-button" onClick={() => void loadQuotes()} disabled={busy}>
            Load Stored Quotes
          </button>
        </div>
      </form>

      {records.length > 0 && (
        <ul className="workspace-list">
          {records.map((record) => (
            <li key={record.evidence_id ?? `${record.league}:${record.asset_id}:${record.observed_at}`}>
              <div>
                <strong>{displayAsset(record.asset_id)}</strong>
                <small>
                  {record.amount} Ex in {record.league}
                  {record.observed_at ? ` observed ${record.observed_at}` : ""}
                </small>
              </div>
              <div className="button-row">
                <button type="button" className="secondary-button" onClick={() => loadRecord(record)} disabled={busy}>
                  Edit
                </button>
                {record.evidence_id && (
                  <button
                    type="button"
                    className="secondary-button danger"
                    onClick={() => void removeQuote(record.evidence_id as string)}
                    disabled={busy}
                  >
                    Delete
                  </button>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}

      {status && <p className="success-message">{status}</p>}
      {error && <p className="error-message">{error}</p>}
    </section>
  );
}

function economyTargets(analysis: AdvisorAnalyzeResponse | null): EconomyTarget[] {
  const items = analysis?.evidence_readiness?.items ?? [];
  return items
    .filter((item) => item.category === "ECONOMY_CRAFTING_COST")
    .flatMap((item) =>
      item.targets
        .filter((target) => target.asset_id)
        .map((target) => ({
          assetId: target.asset_id as string,
          actionName: target.action_display_name,
          reason: target.reason
        }))
    );
}

function optionalText(value: string): string | null {
  const trimmed = value.trim();
  return trimmed || null;
}

function displayAsset(assetId: string): string {
  const slug = assetId.split(":").pop() ?? assetId;
  return displayStatus(slug);
}
