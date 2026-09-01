import { AnimatePresence, motion } from "framer-motion";
import { useState } from "react";

/**
 * A single expandable row. Collapsed shows only `summary` (must stay
 * scannable at a glance); expanded reveals `children` (the full,
 * readable explanation) -- so a list of these never dumps everything on
 * screen at once, but nothing is more than one click from a plain-English
 * answer to "why".
 */
export function AccordionItem({ summary, children, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className="overflow-hidden rounded-md border border-surface-border bg-surface-card">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-3 px-4 py-3 text-left transition hover:bg-white/5"
        aria-expanded={open}
      >
        <motion.span
          animate={{ rotate: open ? 90 : 0 }}
          transition={{ duration: 0.18 }}
          className="shrink-0 text-ink-muted"
        >
          ▸
        </motion.span>
        <div className="min-w-0 flex-1">{summary}</div>
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.22, ease: "easeInOut" }}
            className="overflow-hidden"
          >
            <div className="border-t border-surface-border px-4 py-4">{children}</div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
