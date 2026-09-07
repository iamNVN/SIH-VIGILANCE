import { AnimatePresence, motion } from "framer-motion";
import { Building2, Check, Globe2, Landmark, MapPin, X } from "lucide-react";
import { useEffect, useState } from "react";

// Complete literal class strings, not `bg-${color}/15` interpolation --
// Tailwind's JIT scanner can't see dynamically-built class names (same
// reasoning as pages/CommandCenter.jsx's ringRiskTier).
const COLOR_CLASSES = {
  "series-1": { bg: "bg-series-1/15", text: "text-series-1" },
  "series-2": { bg: "bg-series-2/15", text: "text-series-2" },
  "series-3": { bg: "bg-series-3/15", text: "text-series-3" },
  "series-6": { bg: "bg-series-6/15", text: "text-series-6" },
  "series-7": { bg: "bg-series-7/15", text: "text-series-7" },
};

// Maps directly onto the PS's own "Alert & Notification System" deliverable
// ("Real-time notifications to law enforcements, banks, and I4C officers
// via SMS, email, API, or dashboard triggers") -- the one deliverable this
// prototype otherwise has nothing for. Recipients use REAL data from the
// case (its actual city, bank, predicted location) -- only the DELIVERY
// itself is simulated (no SMTP/Twilio/API client exists in this demo, see
// core/event_log.py's docstring for the same honesty pattern applied to
// the Live Feed). Fires only on "approved" -- a rejected case has no one
// to notify.
//
// Cross-bank routing: the predicted cash-out point carries its OWN
// bank_name (see predict.py) -- the model only ever ranks withdrawal
// points within the victim's own city, but candidates are NOT restricted
// to the victim's own bank, and empirically the top pick is almost always
// a DIFFERENT bank (funds move through a mule account elsewhere before
// withdrawal). The freeze action belongs to whichever bank actually holds
// that account, so a genuinely cross-bank case gets a second, distinct
// recipient rather than silently notifying only the bank that took the
// complaint (which can't freeze an account it doesn't hold).
function buildRecipients(complaint, topPrediction) {
  const city = complaint?.victim_city || "the local jurisdiction";
  const sourceBank = complaint?.bank_name || "Victim's bank";
  const destBank = topPrediction?.bank_name;
  const crossBank = Boolean(destBank && destBank !== sourceBank);

  const recipients = [
    {
      icon: Building2,
      color: COLOR_CLASSES["series-1"],
      title: `${city} Cyber Crime Cell`,
      detail: "Case escalated for field action",
    },
    {
      icon: Landmark,
      color: COLOR_CLASSES["series-2"],
      title: `${sourceBank} — Fraud Response Team`,
      detail: crossBank
        ? "Source account — fraud confirmed on this report"
        : "Freeze request logged against the linked account",
    },
  ];

  if (crossBank) {
    recipients.push({
      icon: Landmark,
      color: COLOR_CLASSES["series-3"],
      title: `${destBank} — Fraud Response Team`,
      detail: "Destination account — freeze request for the predicted cash-out point",
    });
  }

  recipients.push(
    {
      icon: MapPin,
      color: COLOR_CLASSES["series-6"],
      title: topPrediction?.name || "Predicted cash-out branch/ATM",
      detail: "On-site alert for the predicted withdrawal point",
    },
    {
      icon: Globe2,
      color: COLOR_CLASSES["series-7"],
      title: "I4C Central Dashboard",
      detail: crossBank ? `Cross-bank case flagged (${sourceBank} → ${destBank})` : "Case flagged for cross-jurisdiction visibility",
    }
  );

  return recipients;
}

function RecipientRow({ recipient, index, sent }) {
  const Icon = recipient.icon;
  return (
    <motion.li
      initial={{ opacity: 0, x: -12 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.15, duration: 0.3 }}
      className="flex items-center gap-3 py-2.5"
    >
      <div className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-md ${recipient.color.bg}`}>
        <Icon className={`h-4 w-4 ${recipient.color.text}`} strokeWidth={2} />
      </div>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-ink-primary">{recipient.title}</p>
        <p className="truncate text-xs text-ink-muted">{recipient.detail}</p>
      </div>
      <div className="shrink-0">
        {sent ? (
          <motion.span
            initial={{ scale: 0.5, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ type: "spring", stiffness: 400, damping: 15 }}
            className="flex items-center gap-1 rounded-full bg-status-good/15 px-2 py-1 text-[10px] font-semibold uppercase tracking-wide text-status-good"
          >
            <Check className="h-3 w-3" strokeWidth={3} /> Notified
          </motion.span>
        ) : (
          <span className="flex items-center gap-1.5 rounded-full bg-white/5 px-2 py-1 text-[10px] font-medium uppercase tracking-wide text-ink-muted">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-ink-muted" /> Sending
          </span>
        )}
      </div>
    </motion.li>
  );
}

export default function NotificationDispatchModal({ open, onClose, complaint, topPrediction }) {
  const recipients = buildRecipients(complaint, topPrediction);
  // Each recipient flips from "Sending" to "Notified" on its own staggered
  // timer once the modal opens -- purely a UI sequencing effect (the real,
  // single DB write already happened before this modal ever opens), not a
  // second decision or a fabricated delay in anything that matters.
  const [sentCount, setSentCount] = useState(0);

  useEffect(() => {
    if (!open) {
      setSentCount(0);
      return;
    }
    const timers = recipients.map((_, i) =>
      setTimeout(() => setSentCount((c) => Math.max(c, i + 1)), 350 + i * 450)
    );
    return () => timers.forEach(clearTimeout);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const allSent = sentCount >= recipients.length;

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
            className="w-full max-w-md rounded-lg border border-surface-border bg-surface-raised p-6 shadow-2xl"
          >
            <div className="mb-1 flex items-start justify-between gap-4">
              <div>
                <h2 className="text-lg font-semibold text-ink-primary">
                  {allSent ? "Alerts dispatched" : "Dispatching alerts…"}
                </h2>
                <p className="mt-0.5 text-xs text-ink-muted">Case approved — notifying every party that needs to act.</p>
              </div>
              <button onClick={onClose} className="shrink-0 text-ink-muted hover:text-ink-primary">
                <X className="h-4.5 w-4.5" strokeWidth={2} />
              </button>
            </div>

            <ul className="mt-4 divide-y divide-white/5">
              {recipients.map((r, i) => (
                <RecipientRow key={r.title} recipient={r} index={i} sent={i < sentCount} />
              ))}
            </ul>

            <div className="mt-4 rounded-md border border-status-warning/25 bg-status-warning/10 px-3 py-2.5 text-xs text-status-warning">
              Simulated dispatch — no real SMS/email/API integration exists in this demo. In production, these would
              route through the Citizen Financial Cyber Fraud Reporting and Management System via SMS, email or API,
              as I4C's own framework specifies.
            </div>

            <button onClick={onClose} className="btn-primary mt-4 w-full rounded-md py-2 text-sm font-medium">
              Done
            </button>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
