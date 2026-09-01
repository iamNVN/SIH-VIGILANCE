import { motion } from "framer-motion";
import { useNavigate } from "react-router-dom";
import { PERSONAS, useAuth } from "../auth/AuthContext";

const ROLE_LABEL = { investigator: "Investigator", administrator: "Administrator" };

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();

  const handlePick = (personaId) => {
    login(personaId);
    navigate("/");
  };

  return (
    <div className="relative flex h-screen w-full items-center justify-center overflow-hidden bg-surface-page px-4">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_50%_0%,rgba(57,135,229,0.12),transparent_55%)]" />
      <div className="pointer-events-none absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-series-1 via-status-good to-series-1" />

      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: "easeOut" }}
        className="relative w-full max-w-2xl rounded-md border border-surface-border bg-surface-card p-8"
      >
        <div className="mb-6 border-b border-surface-border pb-6 text-center">
          <motion.div
            initial={{ scale: 0.6, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ duration: 0.4, delay: 0.1, ease: "backOut" }}
            className="relative mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-md bg-series-1 text-lg font-bold text-white"
          >
            PT
          </motion.div>
          <h1 className="text-xl font-semibold uppercase tracking-wide text-ink-primary">PredicTrace</h1>
          <p className="text-sm text-ink-muted">Predictive cash-out intelligence for cybercrime complaints</p>
          <p className="id-tag mt-2 text-[10px] uppercase tracking-wide text-ink-muted">
            Cyber-Fraud Cash-Out Interdiction System · Demo Build
          </p>
        </div>

        <p className="mb-3 text-center text-xs font-medium uppercase tracking-wide text-ink-muted">
          Choose a demo persona to continue
        </p>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {PERSONAS.map((p, i) => (
            <motion.button
              key={p.id}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3, delay: 0.15 + i * 0.06 }}
              whileHover={{ y: -2 }}
              whileTap={{ scale: 0.98 }}
              onClick={() => handlePick(p.id)}
              className="flex items-center gap-3 rounded-md border border-surface-border bg-surface-raised p-4 text-left transition hover:border-series-1/40 hover:bg-series-1/10"
            >
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-white/10 text-sm font-semibold text-ink-secondary">
                {p.initials}
              </div>
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-ink-primary">{p.name}</p>
                <p className="truncate text-xs text-ink-muted">{p.unit}</p>
                <span className="mt-1 inline-block rounded-sm bg-white/5 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-ink-secondary">
                  {ROLE_LABEL[p.role]}
                </span>
              </div>
            </motion.button>
          ))}
        </div>

        <p className="mt-6 text-center text-[11px] text-ink-muted">
          Demo-mode access control only — no password, no real accounts. Full role-based
          access control with audit logging is part of the national deployment roadmap,
          not this demo.
        </p>
      </motion.div>
    </div>
  );
}
