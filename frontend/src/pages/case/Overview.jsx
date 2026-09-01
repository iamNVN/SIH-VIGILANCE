import { useOutletContext } from "react-router-dom";
import { AccordionItem } from "../../components/Accordion";
import { api } from "../../api/client";
import { useApi } from "../../api/useApi";
import { EmptyState, ErrorState, LoadingSpinner } from "../../components/StateViews";

function whyLinkedReasons(r) {
  const reasons = [];
  for (const acc of r.shared_accounts || []) {
    reasons.push(`Shares mule account ${acc.account_number_fake} (${acc.bank_name}) with this case.`);
  }
  for (const wp of r.shared_withdrawal_points || []) {
    reasons.push(`Money from both complaints was cashed out at the same location: ${wp.name}.`);
  }
  if (r.same_bank) {
    reasons.push(`Filed against the same bank (${r.bank_name}) as this complaint.`);
  }
  if (reasons.length === 0) {
    reasons.push("Linked through this case's wider discovered account network.");
  }
  return reasons;
}

function highlightNarrative(text, entities) {
  const needles = [entities.bank_name, entities.ifsc_code].filter(Boolean);
  if (needles.length === 0) return text;

  const pattern = new RegExp(`(${needles.map((n) => n.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|")})`, "g");
  return text.split(pattern).map((part, i) =>
    needles.includes(part) ? (
      <mark key={i} className="rounded bg-status-warning/20 px-1 py-0.5 font-medium text-status-warning">
        {part}
      </mark>
    ) : (
      <span key={i}>{part}</span>
    )
  );
}

export default function Overview() {
  const { complaint } = useOutletContext();
  const entities = complaint.extracted_entities || {};
  const { data: related, loading: relatedLoading, error: relatedError } = useApi(
    (signal) => api.related(complaint.id, signal),
    [complaint.id]
  );

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
      <div className="card p-5 lg:col-span-2">
        <h3 className="mb-2 text-sm font-semibold text-ink-secondary">Victim narrative</h3>
        <p className="leading-relaxed text-ink-primary">{highlightNarrative(complaint.narrative_text, entities)}</p>
        <p className="mt-3 text-xs text-ink-muted">
          Highlighted terms were pulled out automatically via regex-based entity extraction (Blueprint Section 4) —
          the bank name and IFSC code are read straight from the complaint text, live.
        </p>

        <div className="mt-6 border-t border-surface-border pt-5">
          <h3 className="mb-3 text-sm font-semibold text-ink-secondary">Linked complaints</h3>
          {relatedLoading && <LoadingSpinner label="Finding linked complaints…" />}
          {relatedError && <ErrorState message={relatedError} />}
          {related && related.related.length === 0 && (
            <EmptyState message="No other complaints linked to this network yet." />
          )}
          {related && related.related.length > 0 && (
            <>
              <p className="mb-2 text-xs text-ink-muted">
                {related.related.length} other complaint(s) share this account's discovered network (size {related.community_size}).
              </p>
              <div className="max-h-[420px] space-y-2 overflow-y-auto pr-1">
                {related.related.map((r) => (
                  <AccordionItem
                    key={r.complaint_id}
                    summary={
                      <div className="flex items-center justify-between gap-3 text-xs">
                        <span className="id-tag font-medium text-ink-primary">#{r.complaint_id}</span>
                        <span className="id-tag text-ink-muted">
                          ₹{Number(r.amount_lost).toLocaleString("en-IN")} · {new Date(r.filed_at).toLocaleDateString()}
                        </span>
                      </div>
                    }
                  >
                    <div>
                      <p className="mb-2 text-xs font-medium uppercase tracking-wide text-ink-muted">Why this complaint is linked</p>
                      <ul className="space-y-1.5 text-sm text-ink-secondary">
                        {whyLinkedReasons(r).map((reason, i) => (
                          <li key={i} className="flex items-start gap-2">
                            <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-series-1" />
                            {reason}
                          </li>
                        ))}
                      </ul>
                    </div>
                  </AccordionItem>
                ))}
              </div>
            </>
          )}
        </div>
      </div>

      <div className="card p-5">
        <h3 className="mb-3 text-sm font-semibold text-ink-secondary">Extracted entities</h3>
        <dl className="space-y-3 text-sm">
          <div>
            <dt className="text-xs text-ink-muted">Bank</dt>
            <dd className="font-medium text-ink-primary">{entities.bank_name || "Not detected"}</dd>
          </div>
          <div>
            <dt className="text-xs text-ink-muted">IFSC code</dt>
            <dd className="id-tag font-medium text-ink-primary">{entities.ifsc_code || "Not detected"}</dd>
          </div>
          <div>
            <dt className="text-xs text-ink-muted">Amount mentioned</dt>
            <dd className="id-tag font-medium text-ink-primary">
              {entities.amount ? `₹${entities.amount.toLocaleString("en-IN")}` : "Not detected"}
            </dd>
          </div>
          <div>
            <dt className="text-xs text-ink-muted">Status</dt>
            <dd className="font-medium capitalize text-ink-primary">{complaint.status}</dd>
          </div>
        </dl>
      </div>
    </div>
  );
}
