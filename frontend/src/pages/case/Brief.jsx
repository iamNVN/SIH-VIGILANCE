import { faCheck, faDownload, faXmark } from "@fortawesome/free-solid-svg-icons";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { motion } from "framer-motion";
import { useOutletContext } from "react-router-dom";
import { api } from "../../api/client";
import { useApi } from "../../api/useApi";
import SectionHeader from "../../components/SectionHeader";
import { ErrorState, LoadingSpinner } from "../../components/StateViews";
import { caseCode } from "../../utils/caseCode";

function escapeHtml(s) {
  return s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

// Opens a purpose-built, minimal print document in a new tab rather than
// printing the live dashboard itself -- the dashboard's sidebar/tabs/map
// have no sensible paper layout, and trying to hide them with print media
// queries scattered across Layout.jsx and CaseWorkspace.jsx would be
// fragile. This is what actually makes the brief a tangible artifact: an
// investigator can save it as a PDF or hand a printout to a bank's fraud
// team, not just read it off a screen.
function downloadBrief(complaint, briefText) {
  const w = window.open("", "_blank");
  if (!w) return;
  const generatedAt = new Date().toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" });
  w.document.write(`<!doctype html>
<html><head><title>VIGILANCE - Intervention Brief — Case #${caseCode(complaint.id)}</title>
<style>
  body { font-family: Georgia, 'Times New Roman', serif; max-width: 720px; margin: 48px auto; color: #1a1a1a; }
  h1 { font-family: Arial, sans-serif; font-size: 19px; margin: 0 0 4px; }
  .meta { font-family: Arial, sans-serif; font-size: 12px; color: #555; margin-bottom: 24px; padding-bottom: 16px; border-bottom: 2px solid #1a1a1a; }
  .body { white-space: pre-wrap; font-family: 'Courier New', monospace; font-size: 12.5px; line-height: 1.7; }
  .footer { margin-top: 32px; padding-top: 12px; border-top: 1px solid #ccc; font-family: Arial, sans-serif; font-size: 10.5px; color: #777; }
  @media print { body { margin: 0; } }
</style></head>
<body>
  <h1>VIGILANCE — Intervention Brief</h1>
  <div class="meta">Case #${caseCode(complaint.id)} · ${escapeHtml(complaint.victim_city || "")} · Generated ${generatedAt}</div>
  <div class="body">${escapeHtml(briefText)}</div>
  <div class="footer">Simulated recommendation — requires investigator sign-off, not an automated bank/account action.</div>
</body></html>`);
  w.document.close();
  w.focus();
  setTimeout(() => w.print(), 300);
}

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
        action={
          <div className="flex items-center gap-3">
            <span className="id-tag text-[10px] uppercase tracking-wide text-ink-muted">Requires sign-off · not auto-executed</span>
            {brief && (
              <button
                onClick={() => downloadBrief(complaint, brief.brief_text)}
                className="flex items-center gap-1.5 rounded-md border border-surface-border px-2.5 py-1.5 text-xs font-medium text-ink-secondary hover:bg-white/5"
              >
                <FontAwesomeIcon icon={faDownload} className="h-3 w-3" /> Download Brief
              </button>
            )}
          </div>
        }
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
