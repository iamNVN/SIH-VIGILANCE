import { AnimatePresence, motion } from "framer-motion";
import { FileSearch, GitBranch, Network, ScanSearch, ShieldCheck, X } from "lucide-react";

// The exact 5-stage pipeline that actually runs (see backend/app/graph_engine
// and ml/ -- this isn't a simplified marketing version, it's the real steps
// in order). Kept in-app rather than only in a slide deck, since a judge
// exploring the product alone (without the team narrating) should still be
// able to answer "what am I actually looking at" for themselves.
// Complete literal class strings, not `bg-${color}/15` interpolation --
// Tailwind's JIT scanner can't see dynamically-built class names (same
// reasoning as pages/CommandCenter.jsx's ringRiskTier).
const STEPS = [
  {
    icon: FileSearch,
    iconBg: "bg-series-1/15",
    iconColor: "text-series-1",
    title: "A complaint arrives",
    body: "NLP entity extraction pulls the bank, account and narrative details out of the raw complaint text.",
  },
  {
    icon: GitBranch,
    iconBg: "bg-series-7/15",
    iconColor: "text-series-7",
    title: "Point-in-time transaction graph",
    body: "The fund-flow graph is rebuilt cut strictly at this complaint's own filed time — the model never sees money movement that hadn't happened yet.",
  },
  {
    icon: Network,
    iconBg: "bg-series-2/15",
    iconColor: "text-series-2",
    title: "Ring detection",
    body: "Louvain community detection over the mule-account graph surfaces the fraud ring this complaint belongs to, if any.",
  },
  {
    icon: ScanSearch,
    iconBg: "bg-series-6/15",
    iconColor: "text-series-6",
    title: "Ranked cash-out prediction",
    body: "Graph, temporal and geographic features feed a calibrated model that ranks every candidate withdrawal point — with SHAP explaining exactly why each one ranked where it did.",
  },
  {
    icon: ShieldCheck,
    iconBg: "bg-series-3/15",
    iconColor: "text-series-3",
    title: "Investigator sign-off",
    body: "Nothing is auto-executed. An investigator reviews the ranked shortlist and explanation, then approves or rejects — that decision is what's logged as real action.",
  },
];

export default function HowItWorksModal({ open, onClose }) {
  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={onClose}
          className="fixed inset-0 z-[2000] flex items-center justify-center bg-black/60 p-4"
        >
          <motion.div
            initial={{ opacity: 0, y: 16, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 16, scale: 0.97 }}
            transition={{ type: "spring", stiffness: 340, damping: 30 }}
            onClick={(e) => e.stopPropagation()}
            className="max-h-[85vh] w-full max-w-xl overflow-y-auto rounded-lg border border-surface-border bg-surface-raised p-6 shadow-2xl"
          >
            <div className="mb-1 flex items-start justify-between gap-4">
              <div>
                <h2 className="text-lg font-semibold text-ink-primary">How VIGILANCE works</h2>
                <p className="mt-0.5 text-xs text-ink-muted">
                  From a filed complaint to a ranked, explainable cash-out shortlist — the real pipeline, in order.
                </p>
              </div>
              <button onClick={onClose} className="shrink-0 text-ink-muted hover:text-ink-primary">
                <X className="h-4.5 w-4.5" strokeWidth={2} />
              </button>
            </div>

            <div className="mt-5 space-y-0">
              {STEPS.map((step, i) => {
                const Icon = step.icon;
                return (
                  <motion.div
                    key={step.title}
                    initial={{ opacity: 0, x: -14 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: i * 0.08, duration: 0.35, ease: "easeOut" }}
                    className="relative flex gap-4 pb-6 last:pb-0"
                  >
                    {i < STEPS.length - 1 && (
                      <span className="absolute left-[19px] top-10 h-[calc(100%-2.25rem)] w-px bg-surface-border" />
                    )}
                    <div className={`z-10 flex h-10 w-10 shrink-0 items-center justify-center rounded-full ${step.iconBg}`}>
                      <Icon className={`h-4.5 w-4.5 ${step.iconColor}`} strokeWidth={2} />
                    </div>
                    <div className="min-w-0 pt-1.5">
                      <p className="text-sm font-semibold text-ink-primary">
                        <span className="id-tag mr-1.5 text-ink-muted">{i + 1}.</span>
                        {step.title}
                      </p>
                      <p className="mt-1 text-xs leading-relaxed text-ink-muted">{step.body}</p>
                    </div>
                  </motion.div>
                );
              })}
            </div>

            <div className="mt-2 rounded-md border border-status-warning/25 bg-status-warning/10 px-3 py-2.5 text-xs text-status-warning">
              The complaint/transaction dataset is structurally realistic synthetic data (real NCRP/bank data is
              access-restricted). Every step above runs live on it — none of it is pre-canned.
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
