import { ChevronDown, Flame, ListOrdered } from "lucide-react";
import { useState } from "react";
import { api } from "../api/client";
import { useApi } from "../api/useApi";
import { useAuth } from "../auth/AuthContext";
import CashOutMap, { URGENCY_COLOR } from "../components/CashOutMap";
import RiskHeatmapMap from "../components/RiskHeatmapMap";
import { EmptyState, ErrorState, LoadingSpinner } from "../components/StateViews";

const ALL_CITIES = ["Bengaluru", "Chennai", "Delhi", "Hyderabad", "Mumbai"];
const TIME_RANGES = [
  { value: "", label: "All time" },
  { value: "7", label: "Last 7 days" },
  { value: "30", label: "Last 30 days" },
  { value: "90", label: "Last 90 days" },
];

function FilterSelect({ value, onChange, children }) {
  return (
    <div className="relative">
      <select
        value={value}
        onChange={onChange}
        className="appearance-none rounded-md border border-surface-border bg-surface-raised py-1.5 pl-2.5 pr-7 text-xs font-medium text-ink-secondary focus:outline-none"
      >
        {children}
      </select>
      <ChevronDown className="pointer-events-none absolute right-2 top-1/2 h-3 w-3 -translate-y-1/2 text-ink-muted" strokeWidth={2} />
    </div>
  );
}

export default function Maps() {
  const { user } = useAuth();
  // An investigator's jurisdiction is fixed server-side (see stats.py's
  // docstring) -- only an administrator (fixedCity === null) gets a real
  // city picker, same rule Command Center's hotspots panel follows.
  const fixedCity = user?.city || null;
  const [pickedCity, setPickedCity] = useState("");
  const city = fixedCity || pickedCity || null;

  const [view, setView] = useState("heatmap");
  const [days, setDays] = useState("");
  const [category, setCategory] = useState("");

  // GIS density surface -- the PS deliverable itself ("real-time and
  // potential risk zones ... drill-down filters by time, location, and
  // crime category"). Real, currently-open, already-scored complaints only.
  const { data: heatData, loading: heatLoading, error: heatError } = useApi(
    (signal) => api.statsHeatmap(city, days, category, signal),
    [city, days, category]
  );
  const heatPoints = heatData?.points || [];
  const categories = heatData?.categories || {};

  // Ranked-location view -- same underlying feed, aggregated by location
  // instead of plotted per-case. A dedicated map wants a fuller
  // jurisdiction-wide picture than Command Center's compact panel -- same
  // endpoint, same server-side city scope, just a bigger limit.
  const { data: hotspotsData, loading: hotspotsLoading, error: hotspotsError } = useApi(
    (signal) => api.statsHotspots(20, city, signal), [city]
  );
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

  const loading = view === "heatmap" ? heatLoading : hotspotsLoading;
  const error = view === "heatmap" ? heatError : hotspotsError;
  const nCases = view === "heatmap" ? heatData?.n_cases ?? 0 : predictions.length;

  return (
    <div className="mx-auto max-w-6xl px-8 py-8">
      <div className="mb-6">
        <div className="flex items-center gap-2">
          <h1 className="text-2xl font-semibold text-ink-primary">Risk Heatmap Dashboard</h1>
          <span className="id-tag rounded-sm bg-series-1/15 px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-series-1">
            {city ? `${city} only` : "All India"}
          </span>
        </div>
        <p className="text-sm text-ink-muted">
          Real-time and potential cash-out risk zones across {city ? `${city}'s` : "the nation's"} currently open cases
          — drill down by time, location and crime category.
        </p>
      </div>

      <div className="card mb-6 flex flex-wrap items-center gap-3 p-4">
        <div className="flex overflow-hidden rounded-md border border-surface-border">
          <button
            onClick={() => setView("heatmap")}
            className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold transition ${
              view === "heatmap" ? "bg-series-1 text-white" : "bg-surface-raised text-ink-muted hover:text-ink-secondary"
            }`}
          >
            <Flame className="h-3.5 w-3.5" strokeWidth={2} /> Heatmap
          </button>
          <button
            onClick={() => setView("markers")}
            className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold transition ${
              view === "markers" ? "bg-series-1 text-white" : "bg-surface-raised text-ink-muted hover:text-ink-secondary"
            }`}
          >
            <ListOrdered className="h-3.5 w-3.5" strokeWidth={2} /> Ranked markers
          </button>
        </div>

        {!fixedCity && (
          <FilterSelect value={pickedCity} onChange={(e) => setPickedCity(e.target.value)}>
            <option value="">All India</option>
            {ALL_CITIES.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </FilterSelect>
        )}

        {view === "heatmap" && (
          <>
            <FilterSelect value={days} onChange={(e) => setDays(e.target.value)}>
              {TIME_RANGES.map((t) => (
                <option key={t.value} value={t.value}>{t.label}</option>
              ))}
            </FilterSelect>

            <FilterSelect value={category} onChange={(e) => setCategory(e.target.value)}>
              <option value="">All crime categories</option>
              {Object.entries(categories).map(([key, label]) => (
                <option key={key} value={key}>{label}</option>
              ))}
            </FilterSelect>
          </>
        )}

        <span className="ml-auto text-xs text-ink-muted">
          {nCases} case{nCases === 1 ? "" : "s"} plotted
        </span>
      </div>

      {loading && <LoadingSpinner label={view === "heatmap" ? "Building risk surface…" : "Aggregating hotspots…"} />}
      {error && <ErrorState message={error} />}
      {!loading && !error && nCases === 0 && <EmptyState message="No open cases match these filters." />}

      {!loading && !error && nCases > 0 && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_320px]">
          <div className="card p-2">
            {view === "heatmap" ? (
              <>
                <RiskHeatmapMap points={heatPoints} height={640} />
                <p className="px-2 pt-2 text-[12px] text-ink-muted">
                  Warmer colour = more cases cluster here, weighted by the model's confidence in each prediction.
                </p>
              </>
            ) : (
              <CashOutMap predictions={predictions} height={640} />
            )}
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
