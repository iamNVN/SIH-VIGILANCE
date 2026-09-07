import { motion } from "framer-motion";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useApi } from "../api/useApi";
import { useAuth } from "../auth/AuthContext";
import AnimatedNumber from "../components/AnimatedNumber";
import { EmptyState, ErrorState, LoadingSpinner } from "../components/StateViews";

function money(n) {
  return `₹${Number(n).toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}

// Tailwind's JIT scanner only picks up classes that appear as complete
// literal strings in source -- so each tier's full class names are spelled
// out here rather than built via `border-l-${color}` template interpolation,
// which the scanner can't see and would silently produce no styles at all.
const TIERS = {
  large: {
    label: "Large ring",
    border: "border-l-status-critical",
    badge: "bg-status-critical/15 text-status-critical",
    text: "text-status-critical",
  },
  medium: {
    label: "Medium ring",
    border: "border-l-status-warning",
    badge: "bg-status-warning/15 text-status-warning",
    text: "text-status-warning",
  },
  small: {
    label: "Small ring",
    border: "border-l-series-1",
    badge: "bg-series-1/15 text-series-1",
    text: "text-series-1",
  },
};

function sizeTier(size) {
  if (size >= 30) return TIERS.large;
  if (size >= 10) return TIERS.medium;
  return TIERS.small;
}

function relativeTime(iso) {
  if (!iso) return "no recent activity";
  const days = Math.floor((Date.now() - new Date(iso).getTime()) / 86400000);
  if (days <= 0) return "active today";
  if (days === 1) return "active yesterday";
  return `active ${days}d ago`;
}

function RingCard({ ring, index }) {
  const navigate = useNavigate();
  const tier = sizeTier(ring.size);

  return (
    <motion.button
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: Math.min(index * 0.03, 0.4), duration: 0.25 }}
      whileHover={{ y: -3 }}
      onClick={() => navigate(`/rings/${ring.community_id}`)}
      className={`card border-l-2 p-4 text-left transition hover:bg-white/5 ${tier.border}`}
    >
      <div className="mb-3 flex items-center justify-between">
        <span className={`id-tag rounded-sm px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${tier.badge}`}>
          {tier.label}
        </span>
        <span className="id-tag text-[10px] text-ink-muted">ring #{ring.community_id}</span>
      </div>

      {/* "At risk" gets its own full-width row, not a 1/3 share of the
          card next to Accounts/Complaints -- a large ring's amount (e.g.
          ₹1,07,03,762) is a much longer string than a 2-3 digit count and
          was overflowing past its column into the card's edge at this
          card's width. A row of its own scales to any amount, not just
          today's data. */}
      <div className="mb-3 grid grid-cols-2 gap-2">
        <div>
          <p className="id-tag text-2xl font-semibold text-ink-primary">
            <AnimatedNumber value={ring.size} />
          </p>
          <p className="text-[10px] uppercase tracking-wide text-ink-muted">Accounts</p>
        </div>
        <div>
          <p className="id-tag text-2xl font-semibold text-ink-primary">
            <AnimatedNumber value={ring.num_complaints} />
          </p>
          <p className="text-[10px] uppercase tracking-wide text-ink-muted">Complaints</p>
        </div>
      </div>
      <div className="mb-3">
        <p className={`id-tag truncate text-lg font-semibold ${tier.text}`} title={money(ring.total_amount_at_risk)}>
          {money(ring.total_amount_at_risk)}
        </p>
        <p className="text-[10px] uppercase tracking-wide text-ink-muted">At risk</p>
      </div>

      <div className="flex items-center justify-between border-t border-surface-border pt-2 text-xs text-ink-muted">
        <span>{ring.top_city || "multiple cities"} · {ring.top_bank || "multiple banks"}</span>
        <span>{relativeTime(ring.last_activity)}</span>
      </div>
    </motion.button>
  );
}

export default function FraudRings() {
  const { user } = useAuth();
  const city = user?.city || null;
  const { data, error, loading } = useApi((signal) => api.rings(50, city, signal), [city]);
  const rings = data?.rings || [];

  const totals = rings.reduce(
    (acc, r) => ({
      accounts: acc.accounts + r.size,
      complaints: acc.complaints + r.num_complaints,
      amount: acc.amount + r.total_amount_at_risk,
    }),
    { accounts: 0, complaints: 0, amount: 0 }
  );

  return (
    <div className="mx-auto max-w-6xl px-8 py-8">
      <div className="mb-6">
        <div className="flex items-center gap-2">
          <h1 className="text-2xl font-semibold text-ink-primary">Fraud Rings</h1>
          <span className="id-tag rounded-sm bg-series-1/15 px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-series-1">
            {city ? `Touching ${city}` : "All India"}
          </span>
        </div>
        <p className="text-sm text-ink-muted">
          Clusters of accounts discovered by the graph engine (Louvain community detection) that are moving money
          together across multiple complaints -- the strongest signal that a case isn't a lone actor.
        </p>
      </div>

      {!loading && rings.length > 0 && (
        <div className="mb-8 grid grid-cols-3 gap-4">
          <div className="card border-l-2 border-l-series-7 p-4">
            <p className="id-tag text-2xl font-semibold text-ink-primary"><AnimatedNumber value={rings.length} /></p>
            <p className="text-xs uppercase tracking-wide text-ink-muted">Active rings</p>
          </div>
          <div className="card border-l-2 border-l-series-1 p-4">
            <p className="id-tag text-2xl font-semibold text-ink-primary"><AnimatedNumber value={totals.accounts} /></p>
            <p className="text-xs uppercase tracking-wide text-ink-muted">Accounts involved</p>
          </div>
          <div className="card border-l-2 border-l-status-critical p-4">
            <p className="id-tag text-2xl font-semibold text-status-critical">
              <AnimatedNumber value={totals.amount} format={money} />
            </p>
            <p className="text-xs uppercase tracking-wide text-ink-muted">Combined amount at risk</p>
          </div>
        </div>
      )}

      {loading && <LoadingSpinner label="Detecting active rings…" />}
      {error && <ErrorState message={error} />}
      {!loading && !error && rings.length === 0 && (
        <EmptyState message="No rings of 3+ linked accounts detected yet." />
      )}

      {!loading && rings.length > 0 && (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {rings.map((ring, i) => (
            <RingCard key={ring.community_id} ring={ring} index={i} />
          ))}
        </div>
      )}
    </div>
  );
}
