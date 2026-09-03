import { motion } from "framer-motion";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useApi } from "../api/useApi";
import { useAuth } from "../auth/AuthContext";
import AnimatedNumber from "../components/AnimatedNumber";
import { StatusPill } from "../components/Badges";
import { EmptyState, ErrorState, LoadingSpinner } from "../components/StateViews";

function StatCard({ tag, borderClass, textClass, label, value, format, hint }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      whileHover={{ y: -2 }}
      className={`card border-l-2 p-4 ${borderClass}`}
    >
      <div className={`mb-2 flex items-center gap-2 ${textClass}`}>
        <span className="id-tag rounded-sm border border-current/30 px-1.5 py-0.5 text-[10px] font-semibold">{tag}</span>
        <p className="text-xs font-medium uppercase tracking-wide text-ink-muted">{label}</p>
      </div>
      <p className="id-tag text-2xl font-semibold tabular-nums text-ink-primary">
        <AnimatedNumber value={value} format={format} />
      </p>
      {hint && <p className="mt-0.5 text-xs text-ink-muted">{hint}</p>}
    </motion.div>
  );
}

function money(n) {
  return `₹${Number(n).toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}

function initials(name) {
  if (!name) return "?";
  const parts = name.replace(/^(Insp\.|Mr\.|Ms\.|Mrs\.)\s*/, "").split(" ");
  return (parts[0]?.[0] || "").concat(parts[1]?.[0] || "").toUpperCase();
}

const PAGE_SIZE = 10;

export default function CommandCenter() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const city = user?.city || null;
  const [page, setPage] = useState(0);
  const { data: stats, loading: statsLoading, reload: reloadStats } = useApi((signal) => api.stats(city, signal), [city]);
  const { data: complaints, error, loading, reload } = useApi(
    (signal) => api.listComplaints(PAGE_SIZE, page * PAGE_SIZE, "", city, signal),
    [page, city]
  );
  const [triggering, setTriggering] = useState(false);
  const [flash, setFlash] = useState(null);

  const totalPages = stats ? Math.max(1, Math.ceil(stats.total_complaints / PAGE_SIZE)) : 1;

  const handleTrigger = async () => {
    setTriggering(true);
    setFlash(null);
    try {
      const result = await api.triggerNext();
      if (result.done) {
        setFlash({ type: "info", text: "All seeded complaints have already arrived — reset the stream to replay." });
      } else {
        setFlash({ type: "success", text: `New complaint #${result.complaint.id} just arrived.` });
        setPage(0);
        reload();
        reloadStats();
      }
    } catch (e) {
      setFlash({ type: "error", text: e.message });
    } finally {
      setTriggering(false);
    }
  };

  const handleReset = async () => {
    await api.resetStream();
    setFlash({ type: "info", text: "Live-stream replay cursor reset to the start." });
  };

  return (
    <div className="mx-auto max-w-6xl px-8 py-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-semibold text-ink-primary">Command Center</h1>
            <span className="id-tag rounded-sm bg-series-1/15 px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-series-1">
              {city ? `${city} only` : "All India"}
            </span>
          </div>
          <p className="text-sm text-ink-muted">Live overview of incoming complaints and detected fraud rings.</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={handleReset}
            className="rounded-md border border-surface-border px-3 py-2 text-sm font-medium text-ink-secondary hover:bg-white/5"
          >
            Reset replay
          </button>
          <button
            onClick={handleTrigger}
            disabled={triggering}
            className="rounded-md bg-series-1 px-4 py-2 text-sm font-medium text-white hover:bg-brand-600 disabled:opacity-50"
          >
            {triggering ? "Bringing in complaint…" : "▶ Simulate new complaint"}
          </button>
        </div>
      </div>

      {flash && (
        <div
          className={`mb-4 rounded-md px-4 py-2 text-sm ${
            flash.type === "success"
              ? "bg-status-good/15 text-status-good"
              : flash.type === "error"
                ? "bg-status-critical/15 text-status-critical"
                : "bg-white/5 text-ink-secondary"
          }`}
        >
          {flash.text}
        </div>
      )}

      {!statsLoading && stats && (
        <div className="mb-8 grid grid-cols-2 gap-4 sm:grid-cols-4">
          <StatCard tag="01" borderClass="border-l-series-1" textClass="text-series-1" label="Total complaints" value={stats.total_complaints} />
          <StatCard tag="02" borderClass="border-l-status-warning" textClass="text-status-warning" label="Open cases" value={stats.open_complaints} />
          <StatCard tag="03" borderClass="border-l-status-critical" textClass="text-status-critical" label="Amount at risk" value={stats.total_amount_at_risk} format={money} />
          <StatCard
            tag="04"
            borderClass="border-l-series-7"
            textClass="text-series-7"
            label="Suspected active rings"
            value={stats.suspected_active_rings}
            hint={`largest linked network: ${stats.largest_ring_size} accounts`}
          />
        </div>
      )}

      <div className="card">
        <div className="card-header flex items-center justify-between">
          <h2 className="text-sm font-semibold text-ink-primary">Complaints</h2>
          {stats && (
            <p className="id-tag text-xs text-ink-muted">
              {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, stats.total_complaints)} of {stats.total_complaints}
            </p>
          )}
        </div>
        {loading && <LoadingSpinner label="Loading complaints…" />}
        {error && <div className="p-5"><ErrorState message={error} /></div>}
        {!loading && !error && (!complaints || complaints.length === 0) && (
          <div className="p-5"><EmptyState message="No complaints yet. Simulate one to get started." /></div>
        )}
        {!loading && complaints && complaints.length > 0 && (
          <ul className="divide-y divide-white/5">
            {complaints.map((c, i) => (
              <motion.li
                key={c.id}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.03, duration: 0.2 }}
              >
                <button
                  onClick={() => navigate(`/cases/${c.id}`)}
                  className="flex w-full items-center gap-4 px-5 py-3 text-left transition hover:bg-white/5"
                >
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-series-1/15 text-xs font-semibold text-series-1">
                    {initials(c.victim_name)}
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-ink-primary">
                      <span className="id-tag text-ink-muted">#{c.id}</span> · {c.victim_name || "Unknown victim"} · {c.victim_city}
                    </p>
                    <p className="truncate text-xs text-ink-muted">{c.bank_name} · filed {new Date(c.filed_at).toLocaleString()}</p>
                  </div>
                  <p className="id-tag shrink-0 text-sm font-semibold tabular-nums text-ink-primary">{money(c.amount_lost)}</p>
                  <StatusPill status={c.status} />
                </button>
              </motion.li>
            ))}
          </ul>
        )}

        {stats && totalPages > 1 && (
          <div className="flex items-center justify-between border-t border-surface-border px-5 py-3">
            <button
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={page === 0}
              className="rounded-md border border-surface-border px-3 py-1.5 text-xs font-medium text-ink-secondary hover:bg-white/5 disabled:opacity-30"
            >
              ← Previous
            </button>
            <p className="id-tag text-xs text-ink-muted">Page {page + 1} of {totalPages}</p>
            <button
              onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
              disabled={page >= totalPages - 1}
              className="rounded-md border border-surface-border px-3 py-1.5 text-xs font-medium text-ink-secondary hover:bg-white/5 disabled:opacity-30"
            >
              Next →
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
