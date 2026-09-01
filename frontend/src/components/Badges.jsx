// Status colors carry reserved meaning (urgency/state) and are never reused
// as chart series colors -- see the dataviz skill's status palette.
const URGENCY_STYLE = {
  HIGH: { text: "text-status-critical", bg: "bg-status-critical/15", ring: "ring-status-critical/30", dot: "bg-status-critical" },
  MEDIUM: { text: "text-status-warning", bg: "bg-status-warning/15", ring: "ring-status-warning/30", dot: "bg-status-warning" },
  LOW: { text: "text-ink-muted", bg: "bg-white/5", ring: "ring-white/10", dot: "bg-ink-muted" },
};

export function UrgencyBadge({ urgency }) {
  const s = URGENCY_STYLE[urgency] || URGENCY_STYLE.LOW;
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-sm px-2.5 py-1 text-xs font-semibold uppercase tracking-wide ring-1 ring-inset ${s.bg} ${s.text} ${s.ring}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${s.dot}`} />
      {urgency}
    </span>
  );
}

export function ConfidenceBadge({ confidence, compact = false }) {
  const pct = Math.round(confidence * 100);
  const color = pct >= 50 ? "bg-status-good" : pct >= 25 ? "bg-status-warning" : "bg-ink-muted";
  return (
    <div className="flex items-center gap-2">
      <div className={`h-1.5 overflow-hidden rounded-sm bg-white/10 ${compact ? "w-12" : "w-24"}`}>
        <div className={`h-full rounded-sm ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="id-tag text-sm font-semibold tabular-nums text-ink-primary">{pct}%</span>
    </div>
  );
}

export function StatusPill({ status }) {
  const styles = {
    open: "bg-series-1/15 text-series-1 ring-series-1/30",
    closed: "bg-white/5 text-ink-muted ring-white/10",
  };
  return (
    <span className={`inline-flex items-center rounded-sm px-2.5 py-1 text-xs font-medium uppercase tracking-wide ring-1 ring-inset ${styles[status] || styles.open}`}>
      {status}
    </span>
  );
}
