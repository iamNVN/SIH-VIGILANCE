import { NavLink, Outlet, useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import { useApi } from "../api/useApi";
import { ConfidenceBadge, UrgencyBadge } from "../components/Badges";
import { ErrorState, LoadingSpinner } from "../components/StateViews";
import { confidenceContext } from "../utils/confidence";

const TABS = [
  { to: "overview", label: "01 · Case File" },
  { to: "graph", label: "02 · Fund-Flow Trace" },
  { to: "map", label: "03 · Cash-Out Prediction" },
  { to: "brief", label: "04 · Intervention Brief" },
];

export default function CaseWorkspace() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { data: complaint, error, loading } = useApi((signal) => api.getComplaint(id, signal), [id]);
  const { data: prediction, loading: predLoading, error: predError } = useApi(
    (signal) => api.predict(id, signal),
    [id]
  );
  const top = prediction?.predictions?.[0];

  return (
    <div className="mx-auto max-w-6xl px-8 py-8">
      <button onClick={() => navigate("/")} className="mb-3 text-xs font-medium text-ink-muted hover:text-ink-primary">
        ← Back to Command Center
      </button>

      {loading && <LoadingSpinner label="Loading case…" />}
      {error && <ErrorState message={error} />}

      {complaint && (
        <>
          <div className="mb-5 flex items-start justify-between border-b border-surface-border pb-5">
            <div>
              <p className="id-tag text-xs uppercase tracking-wide text-ink-muted">Case #{complaint.id}</p>
              <h1 className="text-2xl font-semibold text-ink-primary">{complaint.victim_name}</h1>
              <p className="text-sm text-ink-muted">
                {complaint.victim_city} · {complaint.bank_name} · filed {new Date(complaint.filed_at).toLocaleString()}
              </p>
            </div>
            <p className="id-tag text-2xl font-semibold tabular-nums text-ink-primary">
              ₹{Number(complaint.amount_lost).toLocaleString("en-IN", { maximumFractionDigits: 0 })}
            </p>
          </div>

          {/* Persistent headline: the single most actionable fact (where cash-out is
              predicted, and how urgently) stays visible no matter which tab is open,
              instead of being one more panel competing for attention inside a tab. */}
          <div className="card mb-6 border-l-2 border-series-1 p-4">
            {predLoading && <LoadingSpinner label="Scoring this case…" />}
            {predError && <ErrorState message={predError} />}
            {top && (
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-[11px] font-medium uppercase tracking-wide text-ink-muted">Top predicted cash-out point</p>
                  <p className="truncate text-base font-semibold text-ink-primary">{top.name}</p>
                  {prediction?.n_candidates > 0 && (
                    <p className="mt-0.5 text-xs text-ink-muted">
                      {confidenceContext(top.confidence, prediction.n_candidates)?.sentence}
                    </p>
                  )}
                </div>
                <div className="flex items-center gap-3">
                  <ConfidenceBadge confidence={top.confidence} />
                  <UrgencyBadge urgency={top.urgency} />
                </div>
              </div>
            )}
          </div>

          <div className="mb-6 flex flex-wrap gap-1 border-b border-surface-border">
            {TABS.map((tab) => (
              <NavLink
                key={tab.to}
                to={tab.to}
                className={({ isActive }) =>
                  `id-tag rounded-t-md px-4 py-2 text-xs font-medium uppercase tracking-wide transition ${
                    isActive ? "border-b-2 border-series-1 text-series-1" : "text-ink-muted hover:text-ink-primary"
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
