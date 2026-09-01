import { api } from "../api/client";
import { useApi } from "../api/useApi";
import { useAuth } from "../auth/AuthContext";
import { ErrorState, LoadingSpinner } from "../components/StateViews";

function Row({ label, value }) {
  return (
    <div className="flex items-center justify-between border-b border-surface-border py-3 last:border-0">
      <span className="text-sm text-ink-muted">{label}</span>
      <span className="id-tag text-sm font-medium text-ink-primary">{value}</span>
    </div>
  );
}

export default function Settings() {
  const { user } = useAuth();
  const { data, error, loading } = useApi((signal) => api.systemInfo(signal), []);
  const meta = data?.metadata;

  return (
    <div className="mx-auto max-w-3xl px-8 py-8">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-ink-primary">Settings</h1>
        <p className="text-sm text-ink-muted">Session, model and system information.</p>
      </div>

      <div className="mb-6 card p-5">
        <h3 className="mb-3 text-sm font-semibold text-ink-primary">Signed in as</h3>
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-series-1/20 text-sm font-semibold text-series-1">
            {user?.initials}
          </div>
          <div>
            <p className="text-sm font-medium text-ink-primary">{user?.name}</p>
            <p className="text-xs capitalize text-ink-muted">{user?.role} · {user?.unit}</p>
          </div>
        </div>
        <p className="mt-4 rounded-md bg-white/5 px-3 py-2 text-xs text-ink-muted">
          Demo-mode access control only — no password, no real accounts. Full role-based access control with audit
          logging is part of the national deployment roadmap, not this demo.
        </p>
      </div>

      <div className="card p-5">
        <h3 className="mb-3 text-sm font-semibold text-ink-primary">Model &amp; system</h3>
        {loading && <LoadingSpinner label="Loading system info…" />}
        {error && <ErrorState message={error} />}
        {meta && (
          <div>
            <Row label="Models ready" value={data.models_ready ? "Yes" : "No"} />
            <Row label="Baseline model" value={meta.baseline_model_version} />
            <Row label="Advanced model" value={meta.advanced_model_version} />
            <Row label="Training complaints" value={meta.n_train_complaints} />
            <Row label="Held-out test complaints" value={meta.n_test_complaints} />
            <Row label="Advanced model features" value={meta.advanced_features?.length} />
            <Row label="Random seed" value={meta.seed} />
          </div>
        )}
      </div>
    </div>
  );
}
