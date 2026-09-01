import { motion } from "framer-motion";
import { useState } from "react";
import { useOutletContext } from "react-router-dom";
import { api } from "../../api/client";
import { useApi } from "../../api/useApi";
import SectionHeader from "../../components/SectionHeader";
import { ErrorState, LoadingSpinner } from "../../components/StateViews";

export default function Brief() {
  const { complaint } = useOutletContext();
  const { data: brief, error, loading } = useApi((signal) => api.brief(complaint.id, signal), [complaint.id]);
  const [decision, setDecision] = useState(null);

  return (
    <div className="card p-5">
      <SectionHeader
        color="series-6"
        action={<span className="id-tag text-[10px] uppercase tracking-wide text-ink-muted">Requires sign-off · not auto-executed</span>}
      >
        Intervention brief
      </SectionHeader>

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
              <motion.span
                initial={{ opacity: 0, x: -6 }}
                animate={{ opacity: 1, x: 0 }}
                className={`rounded-sm px-2.5 py-1 text-xs font-semibold uppercase tracking-wide ${
                  decision === "approved" ? "bg-status-good/15 text-status-good" : "bg-status-critical/15 text-status-critical"
                }`}
              >
                {decision}
              </motion.span>
            )}
          </div>
        </>
      )}
    </div>
  );
}
