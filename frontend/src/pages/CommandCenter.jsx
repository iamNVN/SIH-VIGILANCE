import { AnimatePresence, motion } from "framer-motion";
import {
  Calendar,
  ChevronDown,
  Clock,
  ExternalLink,
  FileText,
  IndianRupee,
  MapPin,
  Plus,
  Share2,
  Shield,
  X,
  Zap,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useApi } from "../api/useApi";
import { useAuth } from "../auth/AuthContext";
import AnimatedNumber from "../components/AnimatedNumber";
import { ConfidenceBadge, UrgencyBadge } from "../components/Badges";
import CashOutMap, { CashOutMapLegend, URGENCY_COLOR } from "../components/CashOutMap";
import { EmptyState, ErrorState, LoadingSpinner } from "../components/StateViews";
import { caseCode } from "../utils/caseCode";

const IST = "Asia/Kolkata";

// The 5 cities this dataset actually covers (see data/generator's
// AREAS_BY_CITY) -- used only to let an administrator (city=null,
// national scope) drill the hotspots panel into one city, matching the
// picker in the reference design. An investigator already has a single,
// fixed jurisdiction (enforced server-side, see stats.py's docstring), so
// they get a plain label here instead of a control that can't do anything.
const ALL_CITIES = ["Bengaluru", "Chennai", "Delhi", "Hyderabad", "Mumbai"];

// One dot color per real event type (see backend/app/core/event_log.py's
// docstring for what's genuinely logged vs simulated) -- "decision" is
// resolved to good/critical at render time based on the actual outcome
// word in its message, not a fixed color, since one event type covers both
// approve and reject.
const EVENT_COLOR = {
  complaint_received: "#3b82f6", // series-1
  ring_linked: "#9085e9", // series-7
  prediction_generated: "#199e70", // series-3
  ring_detected: "#c98500", // series-4
};

function eventColor(event) {
  if (event.type === "decision") {
    return event.message.toLowerCase().includes("rejected") ? "#d03b3b" : "#0ca30c";
  }
  return EVENT_COLOR[event.type] || "#6b7280";
}

function money(n) {
  return `₹${Number(n).toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}

function useLiveClock() {
  const [now, setNow] = useState(new Date());
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(t);
  }, []);
  return now;
}

// Ring size tiers -- same thresholds as pages/FraudRings.jsx, spelled out
// as complete literal class strings (not `text-${x}` interpolation) since
// Tailwind's JIT scanner can't see dynamically-built class names.
function ringRiskTier(size) {
  if (size >= 30) return { label: "HIGH", badge: "bg-status-critical/15 text-status-critical" };
  if (size >= 10) return { label: "MEDIUM", badge: "bg-status-warning/15 text-status-warning" };
  return { label: "LOW", badge: "bg-white/5 text-ink-muted" };
}

function StatCard({ icon: Icon, iconBg, iconColor, label, value, format, delay }) {
  // `value == null` means "still loading" (e.g. High Risk Cases waits on
  // the batch feed, not the fast DB stats) -- shown as a quiet pulse
  // instead of blocking the other cards, which have no such dependency.
  const isLoading = value === null || value === undefined;
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25, delay }}
      whileHover={{ y: -2 }}
      className="card p-4"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-medium text-ink-muted">{label}</p>
          {isLoading ? (
            <div className="mt-2 h-6 w-14 animate-pulse rounded-sm bg-white/10" />
          ) : (
            <p className="id-tag mt-1 text-2xl font-semibold tabular-nums text-ink-primary">
              <AnimatedNumber value={value} format={format} />
            </p>
          )}
        </div>
        <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-md ${iconBg}`}>
          <Icon className={`h-5 w-5 ${iconColor}`} strokeWidth={2} />
        </div>
      </div>
    </motion.div>
  );
}

export default function CommandCenter() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const city = user?.city || null;
  const now = useLiveClock();
  // Administrators (city=null) can drill the hotspots panel into one city
  // (matching the reference design's city picker); an investigator already
  // has one fixed jurisdiction, so this just starts on it and never
  // changes for them (no dropdown rendered -- see the panel below).
  const [hotspotCity, setHotspotCity] = useState(city || ALL_CITIES[0]);

  const { data: stats, reload: reloadStats } = useApi((signal) => api.stats(city, signal), [city]);
  const { data: eventsData, reload: reloadEvents } = useApi((signal) => api.events(city, 30, signal), [city]);
  const [showAllEvents, setShowAllEvents] = useState(false);
  const { data: hotspotsData, reload: reloadHotspots } = useApi((signal) => api.statsHotspots(5, hotspotCity, signal), [hotspotCity]);
  const { data: recentAlerts, loading: alertsLoading, reload: reloadAlerts } = useApi(
    (signal) => api.alertsFeed(5, city, signal, "recent"),
    [city]
  );
  const { data: ringsData, loading: ringsLoading, reload: reloadRings } = useApi((signal) => api.rings(5, city, signal), [city]);
  const { data: streamStatus, reload: reloadStreamStatus } = useApi((signal) => api.streamStatus(city, signal), [city]);

  const [triggering, setTriggering] = useState(false);
  const [arrival, setArrival] = useState(null); // { complaint, prediction | null, error | null }

  const reloadEverything = () => {
    reloadStats();
    reloadEvents();
    reloadHotspots();
    reloadAlerts();
    reloadRings();
    reloadStreamStatus();
  };

  // Command Center is meant to feel like it's actually running, not just
  // refresh on Simulate Complaint -- core/activity_simulator.py injects
  // real complaints/predictions in the background on its own schedule
  // (see Settings' "Inject Live Cases"), which is a real DB write that
  // should move Total Complaints/High Risk Cases/hotspots/rings here
  // without the viewer manually reloading the page. Polling everything,
  // not just the event feed -- a real stat/table lagging behind the very
  // events describing that change is its own kind of "not live".
  useEffect(() => {
    const t = setInterval(reloadEverything, 8000);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [city]);

  const handleTrigger = async () => {
    setTriggering(true);
    try {
      const result = await api.triggerNext(city);
      if (result.done) {
        setArrival({ done: true });
      } else {
        // Score it for real so the notification shows more than a name --
        // this is the same /predict every case page uses, not a separate,
        // lighter-weight guess.
        let prediction = null;
        let predictError = null;
        try {
          prediction = await api.predict(result.complaint.id);
        } catch (e) {
          predictError = e.message;
        }
        setArrival({ complaint: result.complaint, prediction, predictError });
        reloadEverything();
      }
    } catch (e) {
      setArrival({ error: e.message });
    } finally {
      setTriggering(false);
    }
  };

  const hotspots = hotspotsData?.hotspots || [];
  // Memoized on `hotspots` itself (not recomputed every render): Command
  // Center's live clock re-renders this component every second, and an
  // unmemoized .map() here would hand CashOutMap a brand-new array (and new
  // object literals) each time even though the underlying data hadn't
  // changed -- which made the map's fitBounds effect (keyed on this array's
  // reference) re-fire every second, snapping any zoom/pan the user had
  // just done back to the fitted view. Verified: this is exactly what made
  // the map feel unresponsive to scroll/drag.
  const hotspotPredictions = useMemo(
    () =>
      hotspots.map((h, i) => ({
        withdrawal_point_id: i,
        name: h.name,
        lat: h.lat,
        lon: h.lon,
        rank: i + 1,
        confidence: h.share_pct / 100,
        urgency: i === 0 ? "HIGH" : i <= 2 ? "MEDIUM" : "LOW",
        explanation: { narrative: `Top pick for ${h.count} of ${hotspotsData?.n_cases || 0} currently scored open cases.` },
      })),
    [hotspots, hotspotsData?.n_cases]
  );

  const events = eventsData?.events || [];
  const visibleEvents = showAllEvents ? events : events.slice(0, 6);

  return (
    <div className="mx-auto max-w-7xl px-8 py-8">
      {/* Header: title/subtitle left, live status + actions right */}
      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <h1 className="text-2xl font-semibold text-ink-primary">Command Center</h1>
            <span className="id-tag rounded-sm bg-series-1/15 px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-series-1">
              {city ? `${city} only` : "All India"}
            </span>
          </div>
          <p className="text-sm text-ink-muted">Real-time overview of cybercrime complaints and cash-out intelligence.</p>
        </div>

        <div className="flex flex-col items-end gap-3">
          <div className="flex items-center gap-3 text-xs text-ink-muted">
            <span className="flex items-center gap-1.5 text-status-good">
              <span className="h-1.5 w-1.5 rounded-full bg-status-good" /> System Online
            </span>
            <span className="flex items-center gap-1.5">
              <Calendar className="h-3.5 w-3.5" strokeWidth={2} />
              {now.toLocaleDateString("en-IN", { timeZone: IST, day: "numeric", month: "short", year: "numeric" })}
            </span>
            <span className="flex items-center gap-1.5">
              <Clock className="h-3.5 w-3.5" strokeWidth={2} />
              {now.toLocaleTimeString("en-IN", { timeZone: IST, hour: "numeric", minute: "2-digit" })} IST
            </span>
          </div>
          <div className="flex items-center gap-3">
            {/* {streamStatus && (
              <span className="id-tag text-xs text-ink-muted">{streamStatus.revealed} / {streamStatus.total} arrived</span>
            )} */}
            <button
              onClick={handleTrigger}
              disabled={triggering || streamStatus?.done}
              className="flex items-center gap-1.5 rounded-md bg-series-1 px-4 py-2 text-sm font-medium text-white hover:bg-brand-600 disabled:opacity-50"
            >
              <Plus className="h-3.5 w-3.5" strokeWidth={2.5} />
              {triggering ? "Bringing in complaint…" : streamStatus?.done ? "All complaints have arrived" : "Simulate Complaint"}
            </button>
          </div>
        </div>
      </div>

      {/* Simulate Complaint's real result: the actual complaint that just
          arrived, actually scored (same /predict every case uses), with a
          direct way to open it -- not a one-line toast that says something
          happened without showing what. */}
      <AnimatePresence>
        {arrival && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="mb-6 overflow-hidden"
          >
            {arrival.done && (
              <div className="flex items-center justify-between rounded-md bg-white/5 px-4 py-3 text-sm text-ink-secondary">
                All {streamStatus?.total ?? ""} seeded complaints have already arrived — nothing left to simulate.
                <button onClick={() => setArrival(null)}><X className="h-4 w-4" strokeWidth={2} /></button>
              </div>
            )}
            {arrival.error && <ErrorState message={arrival.error} />}
            {arrival.complaint && (
              <div className="card border-l-2 border-l-series-1 p-4">
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <p className="id-tag text-[11px] font-semibold uppercase tracking-wide text-series-1">
                      New complaint arrived · #{caseCode(arrival.complaint.id)}
                    </p>
                    <p className="mt-0.5 truncate text-base font-semibold text-ink-primary">
                      {arrival.complaint.victim_name || "Unknown victim"} · {arrival.complaint.victim_city || city || "—"}
                    </p>
                    <p className="text-xs text-ink-muted">
                      {arrival.complaint.bank_name} · {money(arrival.complaint.amount_lost)} · filed{" "}
                      {new Date(arrival.complaint.filed_at).toLocaleString("en-IN", { timeZone: IST })}
                    </p>

                    {arrival.prediction && (
                      <div className="mt-3 flex flex-wrap items-center gap-3 border-t border-surface-border pt-3">
                        <span className="flex items-center gap-1.5 text-xs text-ink-secondary">
                          <MapPin className="h-3.5 w-3.5 shrink-0 text-series-2" strokeWidth={2} />
                          Predicted: {arrival.prediction.predictions?.[0]?.name}
                        </span>
                        <ConfidenceBadge confidence={arrival.prediction.predictions?.[0]?.confidence ?? 0} compact />
                        <UrgencyBadge urgency={arrival.prediction.predictions?.[0]?.urgency} />
                      </div>
                    )}
                    {arrival.predictError && (
                      <p className="mt-2 text-xs text-ink-muted">Couldn't score this one yet: {arrival.predictError}</p>
                    )}
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    <button
                      onClick={() => navigate(`/cases/${arrival.complaint.id}`)}
                      className="rounded-md bg-series-1 px-3 py-1.5 text-xs font-medium text-white hover:bg-brand-600"
                    >
                      View Case
                    </button>
                    <button onClick={() => setArrival(null)} className="text-ink-muted hover:text-ink-primary">
                      <X className="h-4 w-4" strokeWidth={2} />
                    </button>
                  </div>
                </div>
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Stat cards -- every number below is real, computed from the live
          DB/model/graph, never a placeholder. Deliberately no "vs
          yesterday" deltas: there's no real historical baseline to compare
          against, and inventing one would be exactly the kind of fabricated
          number this project has avoided everywhere else. Gated to what's
          "arrived" so far in the replay (see backend/core/replay_state.py) --
          Simulate Complaint moves these for real. */}
      {/* Always mounted, even while loading -- StatCard already has its own
          skeleton for a null/undefined value (see below), but gating this
          whole block behind `stats` loading meant these 4 cards were
          completely ABSENT for however long /stats took, then popped in all
          at once, pushing the chart/hotspots row down a beat later -- a
          real layout shift, not just a slow number. Rendering the shells
          immediately keeps the page's height stable from first paint; each
          card fills in independently as its own data resolves. */}
      <div className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard icon={FileText} iconBg="bg-series-1/15" iconColor="text-series-1" label="Total Complaints" value={stats?.total_complaints} delay={0} />
        <StatCard icon={Shield} iconBg="bg-status-critical/15" iconColor="text-status-critical" label="High Risk Cases" value={recentAlerts?.total ?? stats?.high_risk_cases} delay={0.03} />
        <StatCard icon={Share2} iconBg="bg-series-7/15" iconColor="text-series-7" label="Active Fraud Rings" value={stats?.suspected_active_rings} delay={0.06} />
        <StatCard icon={IndianRupee} iconBg="bg-status-warning/15" iconColor="text-status-warning" label="Amount at Risk" value={stats?.total_amount_at_risk} format={money} delay={0.09} />
      </div>

      {/* Middle section -- Predicted Cash-out Hotspots (map + ranked list
          side by side) and the Live Investigation Feed, replacing the old
          "Complaints Over Time" line chart: with this dataset's small,
          synthetic complaint volume that chart's day-to-day line
          (0→4→3→0→4→0→2) didn't communicate anything -- these two panels
          are directly about the same cash-out intelligence the rest of
          this screen is for. */}
      <div className="mb-6 grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="card lg:col-span-2  p-5">
          <div className="mb-1 flex items-start justify-between gap-3">
            <div className="flex items-center gap-2.5">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-series-1/15">
                <MapPin className="h-4 w-4 text-series-1" strokeWidth={2} />
              </div>
              <h2 className="text-sm font-semibold text-ink-primary">Predicted Cash-out Hotspots</h2>
            </div>
            {/* Only an administrator (national scope) gets a real picker --
                an investigator's jurisdiction is fixed server-side (see
                stats.py's docstring), so a dropdown that can't change
                anything would just be misleading chrome. */}
            {city ? (
              <span className="id-tag shrink-0 rounded-sm bg-white/5 px-2 py-1 text-xs font-medium text-ink-secondary">{city}</span>
            ) : (
              <div className="relative shrink-0">
                <select
                  value={hotspotCity}
                  onChange={(e) => setHotspotCity(e.target.value)}
                  className="appearance-none rounded-md border border-surface-border bg-surface-raised py-1 pl-2.5 pr-7 text-xs font-medium text-ink-secondary focus:outline-none"
                >
                  {ALL_CITIES.map((c) => (
                    <option key={c} value={c}>{c}</option>
                  ))}
                </select>
                <ChevronDown className="pointer-events-none absolute right-2 top-1/2 h-3 w-3 -translate-y-1/2 text-ink-muted" strokeWidth={2} />
              </div>
            )}
          </div>
          <p className="mb-3 text-xs text-ink-muted">Top locations where stolen funds are likely to be withdrawn.</p>

          {hotspots.length > 0 ? (
            <>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-[1.3fr_1fr]">
                <div>
                  <CashOutMap predictions={hotspotPredictions} height={280} hideLegend />
                  <p className="mt-2 text-[11px] text-ink-muted">Larger circle = higher probability</p>
                  <div className="mt-2 border-t border-surface-border pt-2">
                    <CashOutMapLegend />
                  </div>
                </div>

                <div className="flex flex-col">
                  <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-ink-muted">Top Predicted Locations</h3>
                  <ul className="flex-1 space-y-3">
                    {hotspots.map((h, i) => {
                      const urgency = hotspotPredictions[i]?.urgency;
                      const color = URGENCY_COLOR[urgency] || URGENCY_COLOR.LOW;
                      const [place, ...rest] = h.name.split(", ");
                      const area = rest.join(", ");
                      return (
                        <li key={h.name} className="flex items-center gap-2.5">
                          <span
                            className="id-tag flex h-8 w-6 shrink-0 items-center justify-center rounded-sm text-xs font-bold"
                            style={{ background: `${color}26`, color }}
                          >
                            {i + 1}
                          </span>
                          <div className="min-w-0 flex-1">
                            <p className="truncate text-sm  font-medium text-ink-primary">{place}</p>
                            {area && <p className="truncate text-xs text-ink-muted">{area}</p>}
                          </div>
                          <span className="id-tag shrink-0 text-sm font-semibold" style={{ color }}>{h.share_pct}%</span>
                        </li>
                      );
                    })}
                  </ul>
                  <button
                    onClick={() => navigate("/maps")}
                    className="mt-4 flex w-full items-center justify-center gap-1.5 rounded-md bg-series-1 px-3 py-2 text-xs font-medium text-white hover:bg-brand-600"
                  >
                    View Full Map <ExternalLink className="h-3 w-3" strokeWidth={2} />
                  </button>
                </div>
              </div>
            </>
          ) : (
            <LoadingSpinner label="Aggregating hotspots…" />
          )}
        </div>

        <div className="card flex flex-col p-5">
          <div className="mb-3 flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-status-good/15">
                <Zap className="h-4 w-4 text-status-good" strokeWidth={2} />
              </div>
              <h2 className="text-sm font-semibold text-ink-primary">Live Investigation Feed</h2>
            </div>
            <span className="flex shrink-0 items-center gap-1.5 rounded-full bg-status-good/15 px-2.5 py-1 text-[11px] font-semibold text-status-good">
              <span className="relative flex h-1.5 w-1.5">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-status-good opacity-75" />
                <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-status-good" />
              </span>
              Live
            </span>
          </div>

          {/* Every entry below is a real, timestamped thing that actually
              happened in this backend process (see core/event_log.py) --
              never a synthetic timeline. Between real user actions,
              core/activity_simulator.py keeps this moving on a synthetic
              cadence, but always built from real sampled data (a real
              complaint's amount/city, a real cached prediction, a real
              detected ring's stats). */}
          <div className="min-h-[260px] max-h-[420px] flex-1 overflow-y-auto">
            {events.length === 0 ? (
              <LoadingSpinner label="Loading activity…" />
            ) : (
              <ul className="divide-y divide-white/5">
                {visibleEvents.map((ev) => (
                  <li key={ev.id} className="flex gap-3 py-2.5 first:pt-0">
                    <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full" style={{ background: eventColor(ev) }} />
                    <div className="min-w-0 flex-1">
                      <p className="flex items-baseline gap-2">
                        <span className="id-tag bg-white/5 shrink-0 text-xs font-semibold text-ink-secondary px-1">
                          {new Date(ev.timestamp).toLocaleTimeString("en-IN", { timeZone: IST, hour: "numeric", minute: "2-digit" })}
                        </span>
                        <span className="min-w-0 truncate text-sm font-medium text-ink-primary">{ev.message}</span>
                      </p>
                      {ev.detail && <p className="mt-0.5 truncate text-xs text-ink-muted">{ev.detail}</p>}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
          {events.length > 6 && (
            <button
              onClick={() => setShowAllEvents((v) => !v)}
              className="mt-3 flex items-center gap-1 border-t border-surface-border pt-3 text-xs font-medium text-series-1 hover:text-series-1/80"
            >
              {showAllEvents ? "Show fewer" : "View All Activity"} <ExternalLink className="h-3 w-3" strokeWidth={2} />
            </button>
          )}
        </div>
      </div>

      {/* Tables row */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div className="card">
          <div className="card-header flex items-center justify-between">
            <h2 className="text-sm font-semibold text-ink-primary">Recent High Risk Complaints</h2>
            <button onClick={() => navigate("/alerts")} className="text-xs font-medium text-series-1 hover:text-series-1/80">
              View All
            </button>
          </div>
          {alertsLoading && <LoadingSpinner label="Loading…" />}
          {!alertsLoading && (!recentAlerts?.items || recentAlerts.items.length === 0) && (
            <div className="p-5"><EmptyState message="No high-risk cases right now." /></div>
          )}
          {!alertsLoading && recentAlerts?.items?.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-surface-border text-left text-xs text-ink-muted">
                    <th className="px-5 py-2 font-medium">Case</th>
                    <th className="px-3 py-2 font-medium">Victim</th>
                    <th className="px-3 py-2 font-medium">Amount</th>
                    <th className="px-3 py-2 font-medium">Predicted Location</th>
                    <th className="px-3 py-2 font-medium">Risk</th>
                  </tr>
                </thead>
                <tbody>
                  {recentAlerts.items.map((it) => (
                    <tr
                      key={it.complaint_id}
                      onClick={() => navigate(`/cases/${it.complaint_id}`)}
                      className="cursor-pointer border-b border-white/5 last:border-0 hover:bg-white/5"
                    >
                      <td className="id-tag px-5 py-2.5 text-ink-muted">#{caseCode(it.complaint_id)}</td>
                      <td className="px-3 py-2.5 font-medium text-ink-primary">{it.victim_name}</td>
                      <td className="id-tag px-3 py-2.5 text-ink-secondary">{money(it.amount_lost)}</td>
                      <td className="max-w-[160px] truncate px-3 py-2.5 text-ink-secondary">{it.top_prediction.name}</td>
                      <td className="px-3 py-2.5"><UrgencyBadge urgency={it.top_prediction.urgency} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="card">
          <div className="card-header flex items-center justify-between">
            <h2 className="text-sm font-semibold text-ink-primary">Active Fraud Rings</h2>
            <button onClick={() => navigate("/rings")} className="text-xs font-medium text-series-1 hover:text-series-1/80">
              View All
            </button>
          </div>
          {ringsLoading && <LoadingSpinner label="Loading…" />}
          {!ringsLoading && (!ringsData?.rings || ringsData.rings.length === 0) && (
            <div className="p-5"><EmptyState message="No rings of 3+ linked accounts detected yet." /></div>
          )}
          {!ringsLoading && ringsData?.rings?.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-surface-border text-left text-xs text-ink-muted">
                    <th className="px-5 py-2 font-medium">Ring</th>
                    <th className="px-3 py-2 font-medium">Accounts</th>
                    <th className="px-3 py-2 font-medium">Complaints</th>
                    <th className="px-3 py-2 font-medium">Amount Flowed</th>
                    <th className="px-3 py-2 font-medium">Risk</th>
                  </tr>
                </thead>
                <tbody>
                  {ringsData.rings.map((r) => {
                    const tier = ringRiskTier(r.size);
                    return (
                      <tr
                        key={r.community_id}
                        onClick={() => navigate(`/cases/${r.sample_complaint_id}`)}
                        className="cursor-pointer border-b border-white/5 last:border-0 hover:bg-white/5"
                      >
                        <td className="id-tag px-5 py-2.5 text-ink-muted">R-{r.community_id}</td>
                        <td className="id-tag px-3 py-2.5 text-ink-primary">{r.size}</td>
                        <td className="id-tag px-3 py-2.5 text-ink-secondary">{r.num_complaints}</td>
                        <td className="id-tag px-3 py-2.5 text-ink-secondary">{money(r.total_amount_at_risk)}</td>
                        <td className="px-3 py-2.5">
                          <span className={`inline-flex rounded-sm px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide ${tier.badge}`}>
                            {tier.label}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      <p className="mt-8 text-center text-xs text-ink-muted">
        PredicTrace v0.1.0 · Data is simulated for demonstration · All times shown in IST
      </p>
    </div>
  );
}
