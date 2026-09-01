import { useState } from "react";
import { useOutletContext } from "react-router-dom";
import { api } from "../../api/client";
import { useApi } from "../../api/useApi";
import GraphVisualization, { GraphLegend } from "../../components/GraphVisualization";
import MoneyTrail from "../../components/MoneyTrail";
import { ErrorState, LoadingSpinner } from "../../components/StateViews";

export default function FundFlowGraph() {
  const { complaint } = useOutletContext();
  const { data: graphData, error, loading } = useApi((signal) => api.graph(complaint.id, 2, signal), [complaint.id]);
  const [showNetwork, setShowNetwork] = useState(false);

  return (
    <div className="space-y-6">
      <div className="card p-5">
        <div className="mb-4">
          <h3 className="text-sm font-semibold text-ink-secondary">This case's money trail</h3>
          <p className="text-xs text-ink-muted">
            Where the victim's money is known to have moved so far, one step at a time.
          </p>
        </div>

        {loading && <LoadingSpinner label="Tracing the money trail…" />}
        {error && <ErrorState message={error} />}
        {graphData && <MoneyTrail graphData={graphData} />}
      </div>

      <div className="card p-5">
        <div className="mb-3 flex items-start justify-between gap-4">
          <div>
            <h3 className="text-sm font-semibold text-ink-secondary">Wider discovered network</h3>
            <p className="text-xs text-ink-muted">
              Other accounts and cash-out points statistically clustered with this case -- useful for spotting a
              ring, but not part of this case's own confirmed trail above.
            </p>
          </div>
          {graphData?.community_id !== null && graphData && (
            <div className="shrink-0 text-right text-xs text-ink-muted">
              <p>{graphData.community_members_shown} of {graphData.community_size_total} linked accounts</p>
            </div>
          )}
        </div>

        <button
          onClick={() => setShowNetwork((v) => !v)}
          className="rounded-md border border-surface-border px-3 py-1.5 text-xs font-medium text-ink-secondary hover:bg-white/5"
        >
          {showNetwork ? "Hide wider network" : "Show wider network"}
        </button>

        {showNetwork && graphData && (
          <div className="mt-4">
            <GraphVisualization graphData={graphData} />
            <div className="mt-3">
              <GraphLegend />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
