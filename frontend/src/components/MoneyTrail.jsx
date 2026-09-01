import { motion } from "framer-motion";

const ROLE_COLOR = { victim: "#3987e5", mule: "#d95926", normal: "#6b6a66" };
const ROLE_LABEL = { victim: "Victim account", mule: "Mule account", normal: "Account" };

function edgesBetween(edges, fromId, toId) {
  return edges.filter(
    (e) => (e.source === `acc_${fromId}` && e.target === `acc_${toId}`) || (e.source === `acc_${toId}` && e.target === `acc_${fromId}`)
  );
}

/**
 * The straight-line, step-by-step version of this case's own money trail --
 * no physics, no unrelated nodes, nothing to misread. This is the direct
 * answer to "the fund-flow graph is like grapes, I can't understand it":
 * for THIS case, the trail is a strict sequence (victim -> hop -> hop ->
 * ... -> frontier), so it's drawn as one, in order. The wider discovered
 * network (other accounts that share a cluster but aren't part of this
 * specific traced path) is a separate, opt-in view -- see GraphVisualization.
 */
export default function MoneyTrail({ graphData }) {
  const chainIds = graphData?.chain_account_ids || [];
  if (chainIds.length === 0) return null;

  const nodesById = Object.fromEntries((graphData.nodes || []).map((n) => [n.id, n]));
  const steps = chainIds.map((id) => nodesById[`acc_${id}`]).filter(Boolean);

  return (
    <div className="overflow-x-auto pb-2">
      <div className="flex min-w-max items-stretch gap-2">
        {steps.map((node, i) => {
          const isLast = i === steps.length - 1;
          const color = ROLE_COLOR[node.account_type] || ROLE_COLOR.normal;
          const between = !isLast ? edgesBetween(graphData.edges, chainIds[i], chainIds[i + 1]) : [];
          const totalAmount = between.reduce((s, e) => s + (e.amount || 0), 0);

          return (
            <motion.div
              key={node.id}
              initial={{ opacity: 0, x: -12 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.08, duration: 0.3 }}
              className="flex items-stretch"
            >
              <div
                className="flex w-44 shrink-0 flex-col justify-center rounded-md border p-3"
                style={{ borderColor: `${color}66`, background: `${color}14` }}
              >
                <p className="text-[10px] font-medium uppercase tracking-wide" style={{ color }}>
                  {i === 0 ? "Starts with" : isLast ? "Traced to (so far)" : `Hop ${i}`}
                </p>
                <p className="mt-0.5 text-sm font-semibold text-ink-primary">{ROLE_LABEL[node.account_type] || "Account"}</p>
                <p className="id-tag mt-1 text-xs text-ink-muted">acc_{chainIds[i]} · {node.bank_name}</p>
              </div>

              {!isLast && (
                <div className="flex w-16 shrink-0 flex-col items-center justify-center px-1">
                  <span className="text-ink-muted">→</span>
                  {totalAmount > 0 && (
                    <span className="id-tag mt-1 whitespace-nowrap text-[10px] text-ink-muted">
                      ₹{totalAmount.toLocaleString("en-IN", { maximumFractionDigits: 0 })}
                    </span>
                  )}
                </div>
              )}
            </motion.div>
          );
        })}

        <motion.div
          initial={{ opacity: 0, x: -12 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: steps.length * 0.08, duration: 0.3 }}
          className="flex items-stretch"
        >
          <div className="flex w-16 shrink-0 flex-col items-center justify-center px-1 text-ink-muted">→</div>
          <div className="flex w-44 shrink-0 flex-col justify-center rounded-md border border-dashed border-white/15 p-3">
            <p className="text-[10px] font-medium uppercase tracking-wide text-ink-muted">Next (predicted)</p>
            <p className="mt-0.5 text-sm font-semibold text-ink-primary">Cash-out point</p>
            <p className="mt-1 text-xs text-ink-muted">see Cash-Out Prediction tab</p>
          </div>
        </motion.div>
      </div>
    </div>
  );
}
