import { motion } from "framer-motion";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useApi } from "../api/useApi";
import { ConfidenceBadge, UrgencyBadge } from "../components/Badges";
import { EmptyState, ErrorState, LoadingSpinner } from "../components/StateViews";
import { confidenceContext } from "../utils/confidence";

function money(n) {
  return `₹${Number(n).toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}

export default function Predictions() {
  const navigate = useNavigate();
  const { data, error, loading } = useApi((signal) => api.predictionsFeed(40, signal), []);
  const items = data?.items || [];

  return (
    <div className="mx-auto max-w-6xl px-8 py-8">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-ink-primary">Predictions</h1>
        <p className="text-sm text-ink-muted">
          The top cash-out call across every open case right now, ranked by how much better than random chance it is.
        </p>
      </div>

      {loading && <LoadingSpinner label="Scoring open cases…" />}
      {error && <ErrorState message={error} />}
      {!loading && !error && items.length === 0 && <EmptyState message="No open cases to score yet." />}

      {!loading && items.length > 0 && (
        <div className="card">
          <ul className="divide-y divide-white/5">
            {items.map((it, i) => {
              const ctx = confidenceContext(it.top_prediction.confidence, it.top_prediction.n_candidates);
              return (
                <motion.li
                  key={it.complaint_id}
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: Math.min(i * 0.02, 0.4), duration: 0.2 }}
                >
                  <button
                    onClick={() => navigate(`/cases/${it.complaint_id}`)}
                    className="flex w-full items-center gap-4 px-5 py-3 text-left transition hover:bg-white/5"
                  >
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-ink-primary">
                        <span className="id-tag text-ink-muted">#{it.complaint_id}</span> {it.victim_name} · {it.victim_city}
                      </p>
                      <p className="truncate text-xs text-ink-muted">
                        → {it.top_prediction.name}
                        {ctx && <span className="text-series-1"> · {ctx.lift.toFixed(1)}x lift</span>}
                      </p>
                    </div>
                    <p className="id-tag hidden shrink-0 text-sm text-ink-secondary sm:block">{money(it.amount_lost)}</p>
                    <ConfidenceBadge confidence={it.top_prediction.confidence} compact />
                    <UrgencyBadge urgency={it.top_prediction.urgency} />
                  </button>
                </motion.li>
              );
            })}
          </ul>
        </div>
      )}
    </div>
  );
}
