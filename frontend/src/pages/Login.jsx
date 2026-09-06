import { motion } from "framer-motion";
import { ArrowRight } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { PERSONAS, useAuth } from "../auth/AuthContext";
import usePageTitle from "../hooks/usePageTitle";

const ROLE_LABEL = { investigator: "Investigator", administrator: "Administrator" };

// Investigator vs administrator gets its own accent here (blue vs neutral)
// regardless of hover state -- a real distinction (jurisdiction-scoped vs
// national oversight, see AuthContext.jsx's own docstring), not decoration.
const ROLE_BADGE = {
  investigator: "bg-series-1/15 text-series-1 ring-1 ring-inset ring-series-1/30",
  administrator: "bg-white/5 text-ink-secondary ring-1 ring-inset ring-white/10",
};

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  usePageTitle("Login");

  const handlePick = (personaId) => {
    login(personaId);
    navigate("/");
  };

  return (
    <div className="relative flex h-screen w-full items-center justify-center overflow-hidden bg-[#050810]">
      {/* loginbg.png already bakes in the header labels, VIGILANCE
          logo/wordmark/tagline, the India map, and the footer strap --
          real DOM text would only duplicate what's already drawn there.
          This page overlays just the one genuinely interactive part: the
          persona picker, positioned in the image's own empty middle band. */}
      {/* <img src="/loginbg.jpeg" alt="VIGILANCE — Predictive Cash-Out Intelligence" className="absolute inset-0 h-full w-full object-cover" /> */}
<video
  autoPlay
  loop
  muted
  playsInline
  preload="auto"
  className="absolute inset-0 h-full w-full object-cover"
>
  <source src="/loginbg.mp4" type="video/mp4" />
</video>

      <div className="relative z-10 flex h-full w-full flex-col items-center px-4 pt-[42vh]">
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.15, ease: "easeOut" }}
          className="mb-6 text-center"
        >
          <h2 className="text-lg font-semibold uppercase tracking-[0.15em] text-white">Choose Your Profile</h2>
          <p className="mt-1 text-xs text-white/50">Access the demo environment with a role-based account</p>
        </motion.div>

        <div className="grid w-full max-w-4xl grid-cols-2 gap-4 md:grid-cols-4">
          {PERSONAS.map((p, i) => (
            <motion.button
              key={p.id}
              initial={{ opacity: 0, y: 14 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.35, delay: 0.25 + i * 0.07, ease: "easeOut" }}
              whileTap={{ scale: 0.97 }}
              onClick={() => handlePick(p.id)}
              className="group flex flex-col items-center gap-3 rounded-lg border border-white/10 bg-black/40 px-4 py-6 text-center backdrop-blur-sm transition-colors hover:border-series-1/50 hover:bg-series-1/10"
            >
              <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-white/10 text-base font-semibold text-white/70 transition-colors group-hover:bg-series-1 group-hover:text-white">
                {p.initials}
              </div>
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-white">{p.name}</p>
                <p className="truncate text-xs text-white/50">{p.unit}</p>
              </div>
              <span
                className={`rounded-full px-2.5 py-0.5 text-[10px] font-medium uppercase tracking-wide ${ROLE_BADGE[p.role]}`}
              >
                {ROLE_LABEL[p.role]}
              </span>
              <span className="flex h-6 w-6 items-center justify-center rounded-full border border-white/15 text-white/40 transition-colors group-hover:border-series-1 group-hover:text-series-1">
                <ArrowRight className="h-3 w-3" strokeWidth={2} />
              </span>
            </motion.button>
          ))}
        </div>

        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.4, delay: 0.6 }}
          className="mt-5 max-w-lg text-center text-[10.5px] leading-relaxed text-white/35"
        >
          Demo-mode access control only. Full role-based access
          control is part of the future enhancement.
        </motion.p>
      </div>
    </div>
  );
}
