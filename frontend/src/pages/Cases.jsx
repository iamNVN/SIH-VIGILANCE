import { motion } from "framer-motion";
import { ArrowUpDown, Search } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useApi } from "../api/useApi";
import { useAuth } from "../auth/AuthContext";
import { StatusPill } from "../components/Badges";
import { EmptyState, ErrorState, LoadingSpinner } from "../components/StateViews";
import { caseCode, decodeCaseCode } from "../utils/caseCode";

function money(n) {
  return `₹${Number(n).toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}

function initials(name) {
  if (!name) return "?";
  const parts = name.replace(/^(Insp\.|Mr\.|Ms\.|Mrs\.)\s*/, "").split(" ");
  return (parts[0]?.[0] || "").concat(parts[1]?.[0] || "").toUpperCase();
}

const PAGE_SIZE = 15;

const SORT_OPTIONS = [
  { value: "newest", label: "Newest first" },
  { value: "oldest", label: "Oldest first" },
  { value: "risk", label: "Highest risk" },
  { value: "confidence", label: "Highest confidence" },
];

export default function Cases() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const city = user?.city || null;
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(0);
  const [sort, setSort] = useState("newest");

  // Case codes (see utils/caseCode.js) are a scrambled display-only encoding
  // of the real id -- the backend only knows how to search by that real id,
  // so a typed code ("BD4K", short + has a digit -- real names/cities/banks
  // don't look like that) gets decoded back to it before the search fires.
  const decodedId = /^[0-9A-Za-z]{1,4}$/.test(query.trim()) && /\d/.test(query.trim())
    ? decodeCaseCode(query.trim())
    : null;
  const effectiveQuery = decodedId !== null ? String(decodedId) : query;

  const { data: complaints, error, loading } = useApi(
    (signal) => api.listComplaints(PAGE_SIZE, page * PAGE_SIZE, effectiveQuery, city, signal, sort),
    [page, effectiveQuery, city, sort]
  );
  const { data: countData } = useApi((signal) => api.countComplaints(effectiveQuery, city, signal), [effectiveQuery, city]);
  const total = countData?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="mx-auto max-w-6xl px-8 py-8">
      <div className="mb-6">
        <div className="flex items-center gap-2">
          <h1 className="text-2xl font-semibold text-ink-primary">Cases</h1>
          <span className="id-tag rounded-sm bg-series-1/15 px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-series-1">
            {city ? `${city} only` : "All India"}
          </span>
        </div>
        <p className="text-sm text-ink-muted">Search and browse every complaint {city ? `in ${city}` : "on file"}.</p>
      </div>

      <div className="mb-4 flex items-center gap-3">
        <div className="flex flex-1 items-center gap-2 rounded-md border border-surface-border bg-surface-card px-3 py-2.5">
          <Search className="h-4 w-4 shrink-0 text-ink-muted" strokeWidth={2} />
          <input
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setPage(0);
            }}
            placeholder="Search by victim name, city, bank, or case #…"
            className="w-full bg-transparent text-sm text-ink-primary placeholder:text-ink-muted focus:outline-none"
          />
        </div>
        <div className="flex shrink-0 items-center gap-2 rounded-md border border-surface-border bg-surface-card px-3 py-2.5">
          <ArrowUpDown className="h-4 w-4 shrink-0 text-ink-muted" strokeWidth={2} />
          <select
            value={sort}
            onChange={(e) => {
              setSort(e.target.value);
              setPage(0);
            }}
            className="bg-surface-card text-sm text-ink-primary focus:outline-none"
          >
            {SORT_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </div>
      </div>

      <div className="card">
        <div className="card-header flex items-center justify-between">
          <h2 className="text-sm font-semibold text-ink-primary">{query ? `Results for "${query}"` : "All complaints"}</h2>
          {total > 0 && (
            <p className="id-tag text-xs text-ink-muted">
              {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, total)} of {total}
            </p>
          )}
        </div>

        {loading && <LoadingSpinner label="Loading cases…" />}
        {error && <div className="p-5"><ErrorState message={error} /></div>}
        {!loading && !error && (!complaints || complaints.length === 0) && (
          <div className="p-5"><EmptyState message="No matching cases found." /></div>
        )}
        {!loading && complaints && complaints.length > 0 && (
          <ul className="divide-y divide-white/5">
            {complaints.map((c, i) => (
              <motion.li
                key={c.id}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.02, duration: 0.2 }}
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
                      <span className="id-tag text-ink-muted">#{caseCode(c.id)}</span> · {c.victim_name || "Unknown victim"} · {c.victim_city}
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

        {totalPages > 1 && (
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
