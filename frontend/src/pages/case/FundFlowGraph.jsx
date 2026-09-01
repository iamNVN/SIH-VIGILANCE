import { useState } from "react";
import { useOutletContext } from "react-router-dom";
import { api } from "../../api/client";
import { useApi } from "../../api/useApi";
import GraphVisualization, { GraphLegend } from "../../components/GraphVisualization";
import MoneyTrail from "../../components/MoneyTrail";
import SectionHeader from "../../components/SectionHeader";
import { ErrorState, LoadingSpinner } from "../../components/StateViews";

export default function FundFlowGraph() {
  const { complaint } = useOutletContext();
  const { data: graphData, error, loading } = useApi((signal) => api.graph(complaint.id, 2, signal), [complaint.id]);
  const [showNetwork, setShowNetwork] = useState(false);

  return (
    <div className="space-y-6">
      <div className="card p-5">
        <SectionHeader color="series-7">This case's money trail</SectionHeader>
        {loading && <LoadingSpinner label="Tracing the money trail…" />}
        {error && <ErrorState message={error} />}
        {graphData && <MoneyTrail graphData={graphData} />}
      </div>

      <div className="card p-5">
        <SectionHeader
          color="series-7"
          action={
            graphData?.community_id !== null &&
            graphData && (
              <span className="id-tag shrink-0 rounded-sm bg-series-7/10 px-2 py-1 text-xs text-series-7">
                {graphData.community_members_shown} of {graphData.community_size_total} linked accounts
              </span>
            )
          }
        >
          Wider discovered network
        </SectionHeader>
        <p className="mb-3 text-xs text-ink-muted">
          Other accounts statistically clustered with this case -- useful for spotting a ring, not part of the
          confirmed trail above.
        </p>

        <button
          onClick={() => setShowNetwork((v) => !v)}
          className="rounded-md border border-series-7/40 bg-series-7/10 px-3 py-1.5 text-xs font-medium text-series-7 hover:bg-series-7/20"
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
