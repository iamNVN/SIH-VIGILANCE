import { useState } from "react";
import { useOutletContext } from "react-router-dom";
import { api } from "../../api/client";
import { useApi } from "../../api/useApi";
import { ErrorState, LoadingSpinner } from "../../components/StateViews";

export default function Brief() {
  const { complaint } = useOutletContext();
  const { data: brief, error, loading } = useApi((signal) => api.brief(complaint.id, signal), [complaint.id]);
  const [decision, setDecision] = useState(null);

  return (
    <div className="card p-5">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-ink-secondary">Intervention brief</h3>
          <p className="text-xs text-ink-muted">
            Auto-generated, deterministic template — nothing here is auto-executed. Requires investigator sign-off.
          </p>
        </div>
      </div>

      {loading && <LoadingSpinner label="Generating brief…" />}
      {error && <ErrorState message={error} />}

      {brief && (
        <>
          <pre className="whitespace-pre-wrap rounded-md border border-surface-border bg-surface-raised p-4 font-mono text-xs leading-relaxed text-ink-secondary">
            {brief.brief_text}
          </pre>

          <div className="mt-4 flex items-center gap-3">
            <button
              onClick={() => setDecision("approved")}
              className="rounded-md bg-status-good px-4 py-2 text-sm font-medium text-white hover:brightness-110"
            >
              ✓ Approve for action
            </button>
            <button
              onClick={() => setDecision("rejected")}
              className="rounded-md border border-surface-border px-4 py-2 text-sm font-medium text-ink-secondary hover:bg-white/5"
            >
              ✗ Reject
            </button>
            {decision && (
              <span className="text-sm text-ink-muted">
                Recorded as <strong className="text-ink-primary">{decision}</strong> by this investigator (demo — not wired to a real dispatch system).
              </span>
            )}
          </div>
        </>
      )}
    </div>
  );
}
