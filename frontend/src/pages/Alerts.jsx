import { motion } from "framer-motion";
import { AlertTriangle } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useApi } from "../api/useApi";
import { useAuth } from "../auth/AuthContext";
import { EmptyState, ErrorState, LoadingSpinner } from "../components/StateViews";
import { caseCode } from "../utils/caseCode";
import { confidenceContext } from "../utils/confidence";

function money(n) {
  return `₹${Number(n).toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}

export default function Alerts() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const city = user?.city || null;
  const { data, error, loading } = useApi((signal) => api.alertsFeed(40, city, signal), [city]);
  const items = data?.items || [];

  return (
    <div className="mx-auto max-w-6xl px-8 py-8">
      <div className="mb-6">
        <div className="flex items-center gap-2">
          <h1 className="text-2xl font-semibold text-ink-primary">Alerts</h1>
          <span className="id-tag accent-series-1 rounded-sm px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-white">
            {city ? `${city} only` : "All India"}
          </span>
        </div>
        <p className="text-sm text-ink-muted">
          Open cases where the model's top pick stands out sharply from chance -- worth a look first.
        </p>
      </div>

      {loading && <LoadingSpinner label="Checking open cases for standout predictions…" />}
      {error && <ErrorState message={error} />}
      {!loading && !error && items.length === 0 && (
        <EmptyState message="No cases currently clear the alert threshold (5x+ lift over random chance)." />
      )}

      {!loading && items.length > 0 && (
        <div className="space-y-3">
          {items.map((it, i) => {
            const ctx = confidenceContext(it.top_prediction.confidence, it.top_prediction.n_candidates);
            return (
              <motion.button
                key={it.complaint_id}
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: Math.min(i * 0.03, 0.4), duration: 0.2 }}
                onClick={() => navigate(`/cases/${it.complaint_id}`)}
                className="flex w-full items-center gap-4 rounded-md border border-status-critical/30 bg-status-critical/5 p-4 text-left transition hover:bg-status-critical/10"
              >
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-status-critical/15 text-status-critical">
                  <AlertTriangle className="h-5 w-5" strokeWidth={2} />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-semibold text-ink-primary">
                    <span className="id-tag text-ink-muted">#{caseCode(it.complaint_id)}</span> {it.victim_name} · {it.victim_city}
                  </p>
                  <p className="truncate text-xs text-ink-secondary">Likely cash-out: {it.top_prediction.name}</p>
                  {ctx && <p className="mt-0.5 text-xs text-status-critical">{ctx.sentence}</p>}
                </div>
                <div className="shrink-0 text-right">
                  <p className="id-tag text-lg font-bold text-status-critical">{Math.round(it.top_prediction.confidence * 100)}%</p>
                  <p className="id-tag text-xs text-ink-muted">{money(it.amount_lost)}</p>
                </div>
              </motion.button>
            );
          })}
        </div>
      )}
    </div>
  );
}
