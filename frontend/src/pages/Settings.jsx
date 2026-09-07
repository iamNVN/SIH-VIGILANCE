import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useApi } from "../api/useApi";
import { useAuth } from "../auth/AuthContext";
import { ErrorState, LoadingSpinner } from "../components/StateViews";

function relativeTime(iso) {
  if (!iso) return "Never (this session)";
  const seconds = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (seconds < 60) return "Just now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  return `${Math.floor(seconds / 3600)}h ago`;
}

function Row({ label, value }) {
  return (
    <div className="flex items-center justify-between border-b border-surface-border py-3 last:border-0">
      <span className="text-sm text-ink-muted">{label}</span>
      <span className="id-tag text-sm font-medium text-ink-primary">{value}</span>
    </div>
  );
}

function Toggle({ checked, onChange, disabled }) {
  return (
    <button
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={`relative h-6 w-11 shrink-0 rounded-full transition-colors disabled:opacity-50 ${
        checked ? "bg-status-good" : "bg-white/10"
      }`}
    >
      <span
        className={`absolute top-0.5 h-5 w-5 rounded-full bg-white transition-transform ${
          checked ? "translate-x-[22px]" : "translate-x-0.5"
        }`}
      />
    </button>
  );
}

export default function Settings() {
  const { user } = useAuth();
  const { data, error, loading } = useApi((signal) => api.systemInfo(signal), []);
  const meta = data?.metadata;

  // Server-side, process-wide (see core/settings_state.py) -- this isn't a
  // per-browser preference, it gates whether the backend's activity
  // simulator injects real held-back complaints at all (see
  // core/activity_simulator.py), so it's read from and written to the
  // server, not localStorage.
  const { data: injectData, reload: reloadInject } = useApi((signal) => api.getInjectLiveCases(signal), []);
  const [injectSaving, setInjectSaving] = useState(false);
  const handleInjectToggle = async (enabled) => {
    setInjectSaving(true);
    try {
      await api.setInjectLiveCases(enabled);
      reloadInject();
    } finally {
      setInjectSaving(false);
    }
  };

  // Real automated retraining (core/retrain_manager.py) -- fires on its
  // own once enough investigator decisions accumulate (see the sidebar's
  // "labels logged for retraining" counter), but a live demo shouldn't
  // have to wait for that organically, so "Retrain Now" runs the exact
  // same real training pipeline on demand. Polled every 2s only while a
  // retrain is actually running (real one is a ~3s refit against cached
  // features -- see ml/train.py -- so a few polls is enough to see it land).
  const { data: retrain, reload: reloadRetrain } = useApi((signal) => api.retrainStatus(signal), []);
  const [retraining, setRetraining] = useState(false);
  useEffect(() => {
    if (!retrain?.in_progress) return undefined;
    const id = setInterval(reloadRetrain, 2000);
    return () => clearInterval(id);
  }, [retrain?.in_progress, reloadRetrain]);
  const handleRetrainNow = async () => {
    setRetraining(true);
    try {
      await api.triggerRetrain();
      reloadRetrain();
    } catch {
      // 409 = one's already running -- reload will show the real state either way
      reloadRetrain();
    } finally {
      setRetraining(false);
    }
  };

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

      <div className="mb-6 card p-5">
        <h3 className="mb-1 text-sm font-semibold text-ink-primary">Live Investigation Feed</h3>
        <p className="mb-3 text-xs text-ink-muted">
          Applies to everyone, not just this browser -- it's the backend's automatic case injection, not a display preference.
        </p>
        <div className="flex items-center justify-between border-t border-surface-border pt-3">
          <div>
            <p className="text-sm font-medium text-ink-primary">Inject Live Cases</p>
            <p className="text-xs text-ink-muted">
              Reveals one real held-back complaint roughly every 20-30 seconds (real case, real prediction -- see
              Command Center) so the feed keeps moving between investigator actions.
            </p>
          </div>
          <Toggle
            checked={injectData?.enabled ?? true}
            onChange={handleInjectToggle}
            disabled={injectData === null || injectSaving}
          />
        </div>
      </div>

      <div className="mb-6 card p-5">
        <h3 className="mb-1 text-sm font-semibold text-ink-primary">Automated Model Retraining</h3>
        <p className="mb-3 text-xs text-ink-muted">
          Every real Approve/Reject decision logs an investigator training label. Once{" "}
          {retrain?.threshold ?? 5} new labels accumulate since the last retrain, the full training pipeline
          re-runs automatically and the freshly-fit model is hot-swapped in — no restart needed.
        </p>
        <div className="space-y-3 border-t border-surface-border pt-3">
          <div className="flex items-center justify-between">
            <span className="text-sm text-ink-muted">Status</span>
            <span
              className={`id-tag flex items-center gap-1.5 text-sm font-medium ${
                retrain?.in_progress ? "text-status-warning" : retrain?.last_error ? "text-status-critical" : "text-ink-primary"
              }`}
            >
              {retrain?.in_progress && <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-status-warning" />}
              {retrain?.in_progress ? "Retraining…" : retrain?.last_error ? `Failed: ${retrain.last_error}` : "Idle"}
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-sm text-ink-muted">Last retrained</span>
            <span className="id-tag text-sm font-medium text-ink-primary">{relativeTime(retrain?.last_retrained_at)}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-sm text-ink-muted">Labels since last retrain</span>
            <span className="id-tag text-sm font-medium text-ink-primary">
              {retrain?.labels_since_last_retrain ?? 0} / {retrain?.threshold ?? 5}
            </span>
          </div>
          <button
            onClick={handleRetrainNow}
            disabled={retraining || retrain?.in_progress}
            className="btn-primary w-full rounded-md py-2 text-sm font-medium disabled:opacity-50"
          >
            {retrain?.in_progress ? "Retraining…" : "Retrain Now"}
          </button>
          <p className="text-[11px] text-ink-muted">
            Real training run against the current dataset (same pipeline as ml/train.py) — not a simulated
            progress bar. Retraining refits on the generator's own ground truth; investigator labels are the
            real trigger, not (yet) a training target — see api/feedback.py.
          </p>
        </div>
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
