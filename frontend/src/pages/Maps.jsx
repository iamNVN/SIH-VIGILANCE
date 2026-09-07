import { api } from "../api/client";
import { useApi } from "../api/useApi";
import { useAuth } from "../auth/AuthContext";
import CashOutMap, { URGENCY_COLOR } from "../components/CashOutMap";
import { EmptyState, ErrorState, LoadingSpinner } from "../components/StateViews";

export default function Maps() {
  const { user } = useAuth();
  const city = user?.city || null;
  // A dedicated map wants a fuller jurisdiction-wide picture than the 5
  // shown in Command Center's compact panel -- same endpoint, same
  // server-side city scope, just a bigger limit.
  const { data: hotspotsData, error, loading } = useApi((signal) => api.statsHotspots(20, city, signal), [city]);
  const hotspots = hotspotsData?.hotspots || [];

  const predictions = hotspots.map((h, i) => ({
    withdrawal_point_id: i,
    name: h.name,
    lat: h.lat,
    lon: h.lon,
    rank: i + 1,
    confidence: h.share_pct / 100,
    urgency: i === 0 ? "HIGH" : i <= 2 ? "MEDIUM" : "LOW",
    explanation: { narrative: `Top pick for ${h.count} of ${hotspotsData?.n_cases || 0} currently scored open cases.` },
  }));

  return (
    <div className="mx-auto max-w-6xl px-8 py-8">
      <div className="mb-6">
        <div className="flex items-center gap-2">
          <h1 className="text-2xl font-semibold text-ink-primary">Maps</h1>
          <span className="id-tag accent-series-1 rounded-sm px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-white">
            {city ? `${city} only` : "All India"}
          </span>
        </div>
        <p className="text-sm text-ink-muted">
          Every predicted cash-out location across {city ? `${city}'s` : "the nation's"} currently open cases, in one view.
        </p>
      </div>

      {loading && <LoadingSpinner label="Aggregating hotspots…" />}
      {error && <ErrorState message={error} />}
      {!loading && !error && predictions.length === 0 && <EmptyState message="No open cases scored yet." />}

      {!loading && predictions.length > 0 && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_320px]">
          <div className="card p-2">
            <CashOutMap predictions={predictions} height={640} />
          </div>

          <div className="card p-5">
            <h2 className="mb-3 text-sm font-semibold text-ink-primary">
              Ranked locations <span className="text-ink-muted">({predictions.length})</span>
            </h2>
            <ul className="max-h-[600px] space-y-1 overflow-y-auto">
              {hotspots.map((h, i) => {
                const urgency = predictions[i]?.urgency;
                const color = URGENCY_COLOR[urgency] || URGENCY_COLOR.LOW;
                return (
                  <li key={h.name} className="flex items-center gap-2 py-1.5 text-xs">
                    <span
                      className="id-tag flex h-4 w-4 shrink-0 items-center justify-center rounded-sm text-[10px] font-bold"
                      style={{ background: `${color}33`, color }}
                    >
                      {i + 1}
                    </span>
                    <span className="min-w-0 flex-1 truncate text-ink-secondary">{h.name}</span>
                    <span className="id-tag shrink-0 font-semibold" style={{ color }}>{h.share_pct}%</span>
                  </li>
                );
              })}
            </ul>
          </div>
        </div>
      )}
    </div>
  );
}
