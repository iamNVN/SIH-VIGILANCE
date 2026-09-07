import { faCheck, faXmark } from "@fortawesome/free-solid-svg-icons";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { AnimatePresence, motion } from "framer-motion";
import { Calendar, Folder, Landmark, MapPin, Map as MapIcon } from "lucide-react";
import { useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import { useApi } from "../api/useApi";
import { useAuth } from "../auth/AuthContext";
import CashOutMap from "../components/CashOutMap";
import NotificationDispatchModal from "../components/NotificationDispatchModal";
import SectionHeader from "../components/SectionHeader";
import { ErrorState, LoadingSpinner } from "../components/StateViews";
import usePageTitle from "../hooks/usePageTitle";
import { caseCode } from "../utils/caseCode";
import { confidenceContext } from "../utils/confidence";

// Each tab keeps ONE color as its identity throughout the workspace (tab
// underline, active-state text) so "which section am I in" is answerable at
// a glance, not just by reading the label -- a second, color channel on top
// of text, the way the case-identity/prediction banners already work.
const TABS = [
  { to: "overview", label: "01 \u00A0 Case File", color: "series-1" },
  { to: "graph", label: "02 \u00A0 Fund Flow Trace", color: "series-7" },
  { to: "map", label: "03 \u00A0 Cash-out Prediction", color: "series-2" },
  { to: "brief", label: "04 \u00A0 Intervention Brief", color: "series-6" },
];

const TAB_ACTIVE_CLASS = {
  "series-1": "border-b-2 border-series-1 text-series-1",
  "series-7": "border-b-2 border-series-7 text-series-7",
  "series-2": "border-b-2 border-series-2 text-series-2",
  "series-6": "border-b-2 border-series-6 text-series-6",
};

const URGENCY_TONE = {
  HIGH: { dot: "bg-status-critical", text: "text-status-critical", bar: "bg-status-critical" },
  MEDIUM: { dot: "bg-status-warning", text: "text-status-warning", bar: "bg-status-warning" },
  LOW: { dot: "bg-ink-muted", text: "text-ink-muted", bar: "bg-ink-muted" },
};

export default function CaseWorkspace() {
  const { id } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const { user } = useAuth();
  const { data: complaint, error, loading } = useApi((signal) => api.getComplaint(id, signal), [id]);
  // Overrides Layout.jsx's generic "Cases" title with the specific case
  // once it loads -- a case workspace is really its own page, not a
  // sub-view of the Cases list.
  usePageTitle(complaint ? `Case #${caseCode(complaint.id)}` : "Cases");
  const { data: prediction, loading: predLoading, error: predError } = useApi(
    (signal) => api.predict(id, signal),
    [id]
  );
  const top = prediction?.predictions?.[0];
  const runnerUp = prediction?.predictions?.[1];
  const tone = URGENCY_TONE[top?.urgency] || URGENCY_TONE.LOW;
  const lift = top && prediction?.n_candidates > 0 ? confidenceContext(top.confidence, prediction.n_candidates) : null;
  // A 3-point-or-less gap between #1 and #2 means the model isn't
  // confidently distinguishing its top pick from the runner-up -- an
  // investigator acting on #1 alone here is trusting a coin-flip-ish
  // margin, not a clear signal. Absolute probability gap, not relative:
  // a 3-point gap means roughly the same thing whether the base rate is
  // 5% or 18%, unlike a percentage-of-percentage comparison.
  const isCloseCall = top && runnerUp && top.confidence - runnerUp.confidence < 0.03;

  // Lifted out of Brief.jsx (the last of 4 tabs) -- the actual investigator
  // decision on a case shouldn't require clicking through 3 other tabs
  // first to even find it, so it's surfaced here too, on the persistent
  // header every tab shares. Brief.jsx still shows its own copy (reading
  // the same state via context) alongside the full narrative it's a
  // decision about.
  //
  // A real, persisted decision (POST /complaints/{id}/decision), not just
  // local UI state -- it updates the complaint's actual status (reflected
  // in Cases/Command Center/stats too, see complaints.py) and returns an
  // honestly-labeled simulated next step, since this is a sign-off gate
  // ("not auto-executed"), not a real bank/account integration.
  const [localDecision, setLocalDecision] = useState(null);
  const [nextStep, setNextStep] = useState(null);
  const [deciding, setDeciding] = useState(false);
  const [showNotifications, setShowNotifications] = useState(false);
  const [feedbackLogged, setFeedbackLogged] = useState(false);
  const decision =
    localDecision || (complaint?.status === "action_approved" ? "approved" : complaint?.status === "action_rejected" ? "rejected" : null);

  const handleDecision = async (choice) => {
    setDeciding(true);
    try {
      const result = await api.decideComplaint(id, choice);
      setLocalDecision(choice);
      setNextStep(result.next_step);
      setFeedbackLogged(result.feedback_logged);
      // Live-updates Layout.jsx's sidebar label count (it fetches once on
      // mount, and Layout doesn't remount per route) -- both Approve and
      // Reject log a label (see complaints.py's apply_decision), unlike
      // the notification modal below which only fires on Approve.
      if (result.feedback_logged) window.dispatchEvent(new Event("predictrace:feedback-logged"));
      // Approving is the one decision with real parties to act on it --
      // rejecting closes the case out with nothing further to notify
      // anyone about (see complaints.py's own _NEXT_STEP text for the same
      // distinction).
      if (choice === "approved") setShowNotifications(true);
    } catch (e) {
      setNextStep(`Couldn't record this decision: ${e.message}`);
    } finally {
      setDeciding(false);
    }
  };

  return (
    <div className="mx-auto max-w-7xl px-8 py-8">
      <button onClick={() => navigate("/")} className="mb-3 text-xs font-medium text-series-1 hover:text-series-1/80">
        ← Back to Command Center
      </button>

      {loading && <LoadingSpinner label="Loading case…" />}
      {error && <ErrorState message={error} />}

      {complaint && (
        <>
          <div className="card mb-5 p-5">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div className="flex items-start gap-4">
                <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl border border-series-1/50 bg-gradient-to-br from-series-1/55 via-series-1/30 to-series-1/10 shadow-[0_4px_20px_-4px_rgba(59,130,246,0.3),inset_0_1px_0_rgba(255,255,255,0.15)]">
                  <Folder className="h-6 w-6 text-white drop-shadow-[0_0_6px_rgba(96,165,250,0.7)]" strokeWidth={2} />
                </div>
                <div>
                  <p className="id-tag text-xs font-semibold uppercase tracking-wide text-series-1 drop-shadow-[0_0_8px_rgba(59,130,246,0.5)]">Case #{caseCode(complaint.id)}</p>
                  <h1 className="text-2xl font-semibold text-ink-primary">{complaint.victim_name}</h1>
                  <div className="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-ink-muted">
                    <span className="flex items-center gap-1.5">
                      <MapPin className="h-3.5 w-3.5" strokeWidth={2} /> {complaint.victim_city}
                    </span>
                    <span className="flex items-center gap-1.5">
                      <Landmark className="h-3.5 w-3.5" strokeWidth={2} /> {complaint.bank_name}
                    </span>
                    <span className="flex items-center gap-1.5">
                      <Calendar className="h-3.5 w-3.5" strokeWidth={2} />
                      {new Date(complaint.filed_at).toLocaleDateString("en-IN", { month: "short", day: "numeric", year: "numeric" })}
                      {" · "}
                      {new Date(complaint.filed_at).toLocaleTimeString("en-IN", { hour: "numeric", minute: "2-digit" })}
                    </span>
                  </div>
                </div>
              </div>
              <div className="text-right">
                <p className="text-xs text-ink-muted">Amount at Risk</p>
                <p className="id-tag text-2xl font-semibold tabular-nums text-ink-primary">
                  ₹{Number(complaint.amount_lost).toLocaleString("en-IN", { maximumFractionDigits: 0 })}
                </p>
              </div>
            </div>
          </div>

          {user?.city && complaint.victim_city && complaint.victim_city !== user.city && (
            <div className="mb-5 flex items-center gap-2 rounded-md border border-status-warning/30 bg-status-warning/10 px-4 py-2.5 text-xs text-status-warning">
              <MapPin className="h-3.5 w-3.5 shrink-0" strokeWidth={2} />
              Outside your assigned jurisdiction ({user.city}) — this case is filed in {complaint.victim_city}, shown for reference only.
            </div>
          )}

          {/* Main Content Area */}
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_340px]">
            {/* Left Column */}
            <div className="flex min-w-0 flex-col">
              {/* Persistent headline: the single most actionable fact (where
                  cash-out is predicted, and how urgently) stays visible no
                  matter which tab is open. */}
              <motion.div
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.25 }}
                className="card mb-6 p-5"
              >
                {predLoading && <LoadingSpinner label="Scoring this case…" />}
                {predError && <ErrorState message={predError} />}
                {top && (
                  <div className="flex flex-wrap items-center justify-between gap-5">
                    <div className="min-w-0">
                      <p className="text-xs text-ink-muted">Top Predicted Cash-out Point</p>
                      <p className="mt-0.5 truncate text-xl font-semibold text-ink-primary">{top.name}</p>
                      {lift && (
                        <p className="mt-1.5 flex items-center gap-1.5 text-xs text-ink-muted">
                          <MapPin className="h-3.5 w-3.5 shrink-0" strokeWidth={2} /> {lift.sentence}
                        </p>
                      )}
                    </div>
                    <div className="shrink-0 text-right">
                      <p className={`mb-1.5 flex items-center justify-end gap-1.5 text-xs font-semibold uppercase tracking-wide ${tone.text}`}>
                        <span className={`h-1.5 w-1.5 rounded-full ${tone.dot}`} /> {top.urgency} risk
                      </p>
                      <div className="mb-1.5 h-1.5 w-40 overflow-hidden rounded-full bg-white/10">
                        <motion.div
                          initial={{ width: 0 }}
                          animate={{ width: `${Math.round(top.confidence * 100)}%` }}
                          transition={{ duration: 0.6, ease: "easeOut" }}
                          className={`h-full rounded-full ${tone.bar}`}
                        />
                      </div>
                      <p className="id-tag text-3xl font-bold leading-none text-ink-primary">{Math.round(top.confidence * 100)}%</p>
                      <p className="mt-1 text-[11px] text-ink-muted">Probability</p>
                    </div>
                  </div>
                )}
                {isCloseCall && (
                  <div className="mt-4 flex items-start gap-2 rounded-md border border-status-warning/30 bg-status-warning/10 px-3 py-2.5 text-xs text-status-warning">
                    <MapPin className="mt-0.5 h-3.5 w-3.5 shrink-0" strokeWidth={2} />
                    <span>
                      Closely contested — <strong>{runnerUp.name}</strong> is only {Math.round((top.confidence - runnerUp.confidence) * 100)}
                      &nbsp;points behind at {Math.round(runnerUp.confidence * 100)}%. Verify before acting on the top pick alone.
                    </span>
                  </div>
                )}
                {top && (
                  <div className="mt-4 border-t border-surface-border pt-4">
                    <div className="flex items-center gap-3">
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
                    {/* Visible on BOTH approve and reject (unlike the
                        notification modal, which only fires on approve) --
                        this is the one place a rejection shows anything at
                        all, and it's the direct answer to "where did my
                        decision go" for the feedback loop (see
                        complaints.py's apply_decision + api/feedback.py).
                        Gated on the backend's own feedback_logged flag, not
                        assumed -- a complaint outside the cached feed
                        (already closed, never revealed) genuinely has
                        nothing to label. */}
                    {decision && feedbackLogged && (
                      <motion.p
                        initial={{ opacity: 0, y: -4 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.15 }}
                        className="mt-2 flex items-center gap-1.5 text-[11px] text-status-good"
                      >
                        <FontAwesomeIcon icon={faCheck} className="h-2.5 w-2.5" />
                        Logged as an investigator training label — used the next time the model is retrained.
                      </motion.p>
                    )}
                  </div>
                )}
              </motion.div>

              {/* Tabs and Tab Content */}
              <div className="card p-6">
                <div className="mb-6 flex flex-wrap gap-8 border-b border-surface-border">
                  {TABS.map((tab) => (
                    <NavLink
                      key={tab.to}
                      to={tab.to}
                      className={({ isActive }) =>
                        `id-tag pb-3 text-sm font-medium transition-colors ${isActive ? TAB_ACTIVE_CLASS[tab.color] : "text-ink-muted hover:text-ink-primary"
                        }`
                      }
                    >
                      {({ isActive }) => (
                        <>
                          <span className={isActive ? TAB_ACTIVE_CLASS[tab.color].split(' ').find(c => c.startsWith('text-')) : "text-ink-muted"}>
                            {tab.label.split(" \u00A0 ")[0]}
                          </span>
                          {" \u00A0 "}
                          <span className={isActive ? "text-ink-primary" : "text-ink-muted"}>
                            {tab.label.split(" \u00A0 ")[1]}
                          </span>
                        </>
                      )}
                    </NavLink>
                  ))}
                </div>

                <AnimatePresence mode="wait">
                  {/* A small fade on tab switch -- now that Layout.jsx no
                      longer remounts this whole page per tab, switching tabs
                      needs its OWN, lighter transition so it doesn't feel
                      static, without re-animating the header/right column. */}
                  <motion.div
                    key={location.pathname}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    transition={{ duration: 0.15 }}
                  >
                    <Outlet context={{ complaint, prediction, predLoading, predError, decision, nextStep, deciding, handleDecision }} />
                  </motion.div>
                </AnimatePresence>
              </div>
            </div>

            {/* Right Column */}
            <div className="flex min-w-0 flex-col">
              <div className="card p-5">
                <SectionHeader>Top 5 Predicted Cash-out Locations</SectionHeader>
                {prediction?.predictions?.slice(0, 5).length > 0 ? (
                  <>
                    <div className="mb-4 mt-2 overflow-hidden rounded-xl">
                      <CashOutMap predictions={prediction.predictions.slice(0, 5)} height={240} />
                    </div>
                    <ul className="space-y-1">
                      {prediction.predictions.slice(0, 5).map((p) => (
                        <li key={p.withdrawal_point_id} className="flex items-center gap-3 py-2 text-xs">
                          <span className="id-tag flex h-5 w-5 shrink-0 items-center justify-center rounded-sm bg-white/5 text-[11px] font-bold text-ink-muted">
                            {p.rank}
                          </span>
                          <span className="min-w-0 flex-1 truncate text-sm text-ink-secondary">{p.name}</span>
                          <span className="id-tag shrink-0 font-semibold text-series-2">{Math.round(p.confidence * 100)}%</span>
                        </li>
                      ))}
                    </ul>
                    <button
                      onClick={() => navigate("map")}
                      className="mt-4 flex w-full items-center justify-center gap-1.5 rounded-md border border-surface-border bg-white/5 px-3 py-2.5 text-xs font-medium text-ink-secondary transition-colors hover:bg-white/10 hover:text-ink-primary"
                    >
                      <MapIcon className="h-4 w-4" strokeWidth={2} /> View Full Map
                    </button>
                  </>
                ) : (
                  <div className="mt-4">
                    <LoadingSpinner label="Scoring locations…" />
                  </div>
                )}
              </div>
            </div>
          </div>
        </>
      )}

      <NotificationDispatchModal
        open={showNotifications}
        onClose={() => setShowNotifications(false)}
        complaint={complaint}
        topPrediction={top}
      />
    </div>
  );
}
