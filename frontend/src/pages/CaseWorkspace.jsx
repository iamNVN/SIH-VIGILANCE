import { motion } from "framer-motion";
import { Calendar, Folder, Landmark, MapPin } from "lucide-react";
import { NavLink, Outlet, useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import { useApi } from "../api/useApi";
import { ErrorState, LoadingSpinner } from "../components/StateViews";
import { confidenceContext } from "../utils/confidence";

// Each tab keeps ONE color as its identity throughout the workspace (tab
// underline, active-state text) so "which section am I in" is answerable at
// a glance, not just by reading the label -- a second, color channel on top
// of text, the way the case-identity/prediction banners already work.
const TABS = [
  { to: "overview", label: "01 · Case File", color: "series-1" },
  { to: "graph", label: "02 · Fund-Flow Trace", color: "series-7" },
  { to: "map", label: "03 · Cash-Out Prediction", color: "series-2" },
  { to: "brief", label: "04 · Intervention Brief", color: "series-6" },
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
  const { data: complaint, error, loading } = useApi((signal) => api.getComplaint(id, signal), [id]);
  const { data: prediction, loading: predLoading, error: predError } = useApi(
    (signal) => api.predict(id, signal),
    [id]
  );
  const top = prediction?.predictions?.[0];
  const tone = URGENCY_TONE[top?.urgency] || URGENCY_TONE.LOW;
  const lift = top && prediction?.n_candidates > 0 ? confidenceContext(top.confidence, prediction.n_candidates) : null;

  return (
    <div className="mx-auto max-w-6xl px-8 py-8">
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
                <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-lg bg-series-1">
                  <Folder className="h-6 w-6 text-white" strokeWidth={2} />
                </div>
                <div>
                  <p className="id-tag text-xs font-semibold uppercase tracking-wide text-series-1">Case #{complaint.id}</p>
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
          </motion.div>

          <div className="mb-6 flex flex-wrap gap-1 border-b border-surface-border">
            {TABS.map((tab) => (
              <NavLink
                key={tab.to}
                to={tab.to}
                className={({ isActive }) =>
                  `id-tag rounded-t-md px-4 py-2 text-xs font-medium uppercase tracking-wide transition ${
                    isActive ? TAB_ACTIVE_CLASS[tab.color] : "text-ink-muted hover:text-ink-primary"
                  }`
                }
              >
                {tab.label}
              </NavLink>
            ))}
          </div>

          <Outlet context={{ complaint, prediction, predLoading, predError }} />
        </>
      )}
    </div>
  );
}
