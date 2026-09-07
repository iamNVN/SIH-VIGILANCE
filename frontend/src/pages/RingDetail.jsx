import { motion } from "framer-motion";
import { Building2, Calendar, MapPin, Share2 } from "lucide-react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import { useApi } from "../api/useApi";
import { StatusPill } from "../components/Badges";
import { EmptyState, ErrorState, LoadingSpinner } from "../components/StateViews";
import usePageTitle from "../hooks/usePageTitle";
import { caseCode } from "../utils/caseCode";

const IST = "Asia/Kolkata";

function money(n) {
  return `₹${Number(n).toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}

function fmtDate(iso) {
  if (!iso) return "unknown";
  return new Date(iso).toLocaleDateString("en-IN", { timeZone: IST, day: "numeric", month: "short", year: "numeric" });
}

// Same thresholds as FraudRings.jsx's sizeTier -- spelled out as complete
// literal class strings since Tailwind's JIT scanner can't see
// `border-l-${color}`-style interpolation.
function sizeTier(size) {
  if (size >= 30) return { label: "Large ring", badge: "bg-status-critical/15 text-status-critical", text: "text-status-critical" };
  if (size >= 10) return { label: "Medium ring", badge: "bg-status-warning/15 text-status-warning", text: "text-status-warning" };
  return { label: "Small ring", badge: "bg-series-1/15 text-series-1", text: "text-series-1" };
}

function StatCard({ label, value, sub }) {
  return (
    <div className="card p-4">
      <p className="id-tag text-2xl font-semibold text-ink-primary">{value}</p>
      <p className="text-xs uppercase tracking-wide text-ink-muted">{label}</p>
      {sub && <p className="mt-1 text-[11px] text-ink-muted">{sub}</p>}
    </div>
  );
}

export default function RingDetail() {
  const { communityId } = useParams();
  const navigate = useNavigate();
  const { data: ring, error, loading } = useApi((signal) => api.ringDetail(communityId, signal), [communityId]);
  usePageTitle(ring ? `Ring R-${ring.community_id}` : "Fraud Rings");

  return (
    <div className="mx-auto max-w-6xl px-8 py-8">
      <button onClick={() => navigate("/rings")} className="mb-3 text-xs font-medium text-series-1 hover:text-series-1/80">
        ← Back to Fraud Rings
      </button>

      {loading && <LoadingSpinner label="Loading ring…" />}
      {error && <ErrorState message={error} />}

      {ring && (
        <>
          {(() => {
            const tier = sizeTier(ring.size);
            return (
              <>
                <motion.div
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.25 }}
                  className="card mb-6 p-5"
                >
                  <div className="flex flex-wrap items-start justify-between gap-4">
                    <div className="flex items-start gap-4">
                      <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl border border-series-7/50 bg-gradient-to-br from-series-7/55 via-series-7/30 to-series-7/10 shadow-[0_4px_20px_-4px_rgba(144,133,233,0.35),inset_0_1px_0_rgba(255,255,255,0.15)]">
                        <Share2 className="h-6 w-6 text-white drop-shadow-[0_0_6px_rgba(144,133,233,0.7)]" strokeWidth={2} />
                      </div>
                      <div>
                        <span className={`id-tag inline-block rounded-sm px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${tier.badge}`}>
                          {tier.label}
                        </span>
                        <h1 className="mt-1.5 text-2xl font-semibold text-ink-primary">Ring R-{ring.community_id}</h1>
                        <div className="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-ink-muted">
                          <span className="flex items-center gap-1.5">
                            <MapPin className="h-3.5 w-3.5" strokeWidth={2} /> {ring.cities_touched?.join(", ") || "multiple cities"}
                          </span>
                          <span className="flex items-center gap-1.5">
                            <Building2 className="h-3.5 w-3.5" strokeWidth={2} /> {ring.top_bank || "multiple banks"}
                          </span>
                          <span className="flex items-center gap-1.5">
                            <Calendar className="h-3.5 w-3.5" strokeWidth={2} /> First correlated {fmtDate(ring.first_filed_at)}
                          </span>
                        </div>
                      </div>
                    </div>
                    <div className="text-right">
                      <p className="text-xs text-ink-muted">Total Amount at Risk</p>
                      <p className={`id-tag text-2xl font-semibold ${tier.text}`}>{money(ring.total_amount_at_risk)}</p>
                    </div>
                  </div>
                </motion.div>

                <div className="mb-6 grid grid-cols-2 gap-4 sm:grid-cols-4">
                  <StatCard label="Accounts" value={ring.size} />
                  <StatCard label="Linked Complaints" value={ring.num_complaints} />
                  <StatCard label="Cities Touched" value={ring.cities_touched?.length ?? 0} />
                  <StatCard label="Last Activity" value={fmtDate(ring.last_activity)} />
                </div>
              </>
            );
          })()}

          <div className="card">
            <div className="card-header flex items-center justify-between">
              <h2 className="text-sm font-semibold text-ink-primary">
                All Linked Complaints <span className="text-ink-muted">({ring.linked_complaints?.length ?? 0})</span>
              </h2>
            </div>
            {!ring.linked_complaints?.length ? (
              <div className="p-5"><EmptyState message="No linked complaints found for this ring." /></div>
            ) : (
              <ul className="divide-y divide-white/5">
                {ring.linked_complaints.map((c, i) => (
                  <motion.li
                    key={c.id}
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: Math.min(i, 15) * 0.02, duration: 0.2 }}
                  >
                    <button
                      onClick={() => navigate(`/cases/${c.id}`)}
                      className="flex w-full items-center gap-4 px-5 py-3 text-left transition hover:bg-white/5"
                    >
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-medium text-ink-primary">
                          <span className="id-tag text-ink-muted">#{caseCode(c.id)}</span> · {c.victim_name || "Unknown victim"} · {c.victim_city}
                        </p>
                        <p className="truncate text-xs text-ink-muted">{c.bank_name} · filed {fmtDate(c.filed_at)}</p>
                      </div>
                      <p className="id-tag shrink-0 text-sm font-semibold tabular-nums text-ink-primary">{money(c.amount_lost)}</p>
                      <StatusPill status={c.status} />
                    </button>
                  </motion.li>
                ))}
              </ul>
            )}
          </div>
        </>
      )}
    </div>
  );
}
