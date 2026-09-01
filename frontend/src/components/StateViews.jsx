export function LoadingSpinner({ label = "Loading..." }) {
  return (
    <div className="flex items-center justify-center gap-3 py-16 text-ink-muted">
      <div className="h-5 w-5 animate-spin rounded-full border-2 border-white/10 border-t-series-1" />
      <span className="text-sm">{label}</span>
    </div>
  );
}

export function ErrorState({ message }) {
  return (
    <div className="rounded-md border border-status-critical/30 bg-status-critical/10 p-4 text-sm text-status-critical">
      Something went wrong: {message}
    </div>
  );
}

export function EmptyState({ message }) {
  return (
    <div className="rounded-md border border-dashed border-white/10 p-8 text-center text-sm text-ink-muted">
      {message}
    </div>
  );
}
