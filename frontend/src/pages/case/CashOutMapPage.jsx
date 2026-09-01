import { useState } from "react";
import { useOutletContext } from "react-router-dom";
import { AccordionItem } from "../../components/Accordion";
import { api } from "../../api/client";
import { useApi } from "../../api/useApi";
import { ConfidenceBadge, UrgencyBadge } from "../../components/Badges";
import CashOutMap from "../../components/CashOutMap";
import ExplanationPanel from "../../components/ExplanationPanel";
import { ErrorState, LoadingSpinner } from "../../components/StateViews";
import { confidenceContext } from "../../utils/confidence";
import { explainToSentences } from "../../utils/featureLabels";

function ReasonList({ prediction }) {
  const reasons = explainToSentences(prediction.explanation.top_features);
  return (
    <ul className="space-y-2">
      {reasons.map((r) => (
        <li key={r.technicalName} className="flex items-start gap-2 text-sm">
          <span
            className={`mt-0.5 shrink-0 rounded-sm px-1 text-[10px] font-bold ${
              r.direction === "positive" ? "bg-status-good/20 text-status-good" : "bg-status-critical/20 text-status-critical"
            }`}
            title={`${r.technicalName}=${r.value}`}
          >
            {r.direction === "positive" ? "UP" : "DOWN"}
          </span>
          <span className="text-ink-secondary">{r.text}</span>
        </li>
      ))}
    </ul>
  );
}

function PredictionRow({ p, nCandidates, defaultOpen }) {
  const ctx = confidenceContext(p.confidence, nCandidates);
  return (
    <AccordionItem
      defaultOpen={defaultOpen}
      summary={
        <div className="flex items-center justify-between gap-3">
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-ink-primary">
              <span className="id-tag text-ink-muted">#{p.rank}</span> {p.name}
            </p>
          </div>
          <div className="flex shrink-0 items-center gap-3">
            <ConfidenceBadge confidence={p.confidence} compact />
            <UrgencyBadge urgency={p.urgency} />
          </div>
        </div>
      }
    >
      <div className="space-y-3">
        <p className="text-sm text-ink-primary">{p.explanation.narrative}</p>
        {ctx && (
          <p className="rounded-sm bg-series-1/10 px-3 py-2 text-sm font-medium text-series-1">
            {Math.round(p.confidence * 100)}% confidence is {ctx.sentence}
          </p>
        )}
        <div>
          <p className="mb-2 text-xs font-medium uppercase tracking-wide text-ink-muted">Why this location, in plain terms</p>
          <ReasonList prediction={p} />
        </div>
      </div>
    </AccordionItem>
  );
}

export default function CashOutMapPage() {
  const { complaint, prediction, predLoading, predError } = useOutletContext();
  const [showTechnical, setShowTechnical] = useState(false);
  const { data: explanation, loading: explLoading, error: explError } = useApi(
    (signal) => api.explain(complaint.id, undefined, signal),
    [complaint.id]
  );

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <div className="card p-5">
            <h3 className="mb-3 text-sm font-semibold text-ink-secondary">Predicted cash-out locations</h3>
            {predLoading && <LoadingSpinner label="Scoring candidate locations…" />}
            {predError && <ErrorState message={predError} />}
            {prediction && <CashOutMap predictions={prediction.predictions} />}
          </div>
        </div>

        <div className="space-y-3">
          <div>
            <h3 className="text-sm font-semibold text-ink-secondary">Ranked list</h3>
            <p className="text-xs text-ink-muted">Click any location to see why it was ranked here.</p>
          </div>
          {prediction?.predictions.map((p) => (
            <PredictionRow
              key={p.withdrawal_point_id}
              p={p}
              nCandidates={prediction.n_candidates}
              defaultOpen={p.rank === 1}
            />
          ))}
        </div>
      </div>

      <div className="card p-5">
        <button
          onClick={() => setShowTechnical((v) => !v)}
          className="flex w-full items-center justify-between text-left"
        >
          <div>
            <h3 className="text-sm font-semibold text-ink-secondary">Technical detail: model feature weights (SHAP)</h3>
            <p className="text-xs text-ink-muted">For anyone who wants to verify the numbers behind the #1 prediction, not just read the summary.</p>
          </div>
          <span className="id-tag shrink-0 text-xs text-ink-muted">{showTechnical ? "Hide" : "Show"}</span>
        </button>
        {showTechnical && (
          <div className="mt-4 border-t border-surface-border pt-4">
            {explLoading && <LoadingSpinner label="Computing explanation…" />}
            {explError && <ErrorState message={explError} />}
            {explanation && <ExplanationPanel explanation={explanation} height={280} />}
          </div>
        )}
      </div>
    </div>
  );
}
