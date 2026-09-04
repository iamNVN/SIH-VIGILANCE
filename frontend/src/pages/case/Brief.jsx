import { faCheck, faXmark } from "@fortawesome/free-solid-svg-icons";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { motion } from "framer-motion";
import { useOutletContext } from "react-router-dom";
import { api } from "../../api/client";
import { useApi } from "../../api/useApi";
import SectionHeader from "../../components/SectionHeader";
import { ErrorState, LoadingSpinner } from "../../components/StateViews";

export default function Brief() {
  // decision/handleDecision come from CaseWorkspace (shared with the
  // Approve/Reject buttons on the persistent header, visible from every
  // tab, not just this one) -- one real, persisted decision, one source of
  // truth, not a separate local copy here.
  const { complaint, decision, nextStep, deciding, handleDecision } = useOutletContext();
  const { data: brief, error, loading } = useApi((signal) => api.brief(complaint.id, signal), [complaint.id]);

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

          <div>
            <div className="mt-4 flex items-center gap-3">
              <button
                onClick={() => handleDecision("approved")}
                disabled={deciding}
                className="flex items-center gap-2 rounded-md bg-status-good px-4 py-2 text-sm font-medium text-white hover:brightness-110 disabled:opacity-50"
              >
                <FontAwesomeIcon icon={faCheck} className="h-3.5 w-3.5" /> Approve for action
              </button>
              <button
                onClick={() => handleDecision("rejected")}
                disabled={deciding}
                className="flex items-center gap-2 rounded-md border border-surface-border px-4 py-2 text-sm font-medium text-ink-secondary hover:bg-white/5 disabled:opacity-50"
              >
                <FontAwesomeIcon icon={faXmark} className="h-3.5 w-3.5" /> Reject
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
            {nextStep && (
              <motion.p
                initial={{ opacity: 0, y: -4 }}
                animate={{ opacity: 1, y: 0 }}
                className="mt-3 text-xs text-ink-muted"
              >
                {nextStep}
              </motion.p>
            )}
          </div>
        </>
      )}
    </div>
  );
}
