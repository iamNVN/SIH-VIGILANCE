import { ArrowRight, Hash, IndianRupee, Landmark, Map as MapIcon, Tag } from "lucide-react";
import { useState } from "react";
import { useNavigate, useOutletContext } from "react-router-dom";
import { AccordionItem } from "../../components/Accordion";
import { api } from "../../api/client";
import { useApi } from "../../api/useApi";
import CashOutMap from "../../components/CashOutMap";
import SectionHeader from "../../components/SectionHeader";
import { EmptyState, ErrorState, LoadingSpinner } from "../../components/StateViews";

const LINKED_PREVIEW_COUNT = 4;

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

function EntityRow({ icon: Icon, label, children }) {
  return (
    <div className="flex items-start gap-3 border-b border-surface-border py-3 last:border-0">
      <Icon className="mt-0.5 h-4 w-4 shrink-0 text-ink-muted" strokeWidth={2} />
      <div className="min-w-0">
        <p className="text-xs text-ink-muted">{label}</p>
        <div className="mt-0.5 text-sm font-medium text-ink-primary">{children}</div>
      </div>
    </div>
  );
}

export default function Overview() {
  const { complaint, prediction } = useOutletContext();
  const navigate = useNavigate();
  const entities = complaint.extracted_entities || {};
  const [showAllLinked, setShowAllLinked] = useState(false);
  const { data: related, loading: relatedLoading, error: relatedError } = useApi(
    (signal) => api.related(complaint.id, signal),
    [complaint.id]
  );

  const complaintCode = `CMP-${new Date(complaint.filed_at).getFullYear()}-${String(complaint.id).padStart(6, "0")}`;
  const visibleLinked = related ? (showAllLinked ? related.related : related.related.slice(0, LINKED_PREVIEW_COUNT)) : [];
  const top5 = prediction?.predictions?.slice(0, 5) || [];

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1.5fr_1fr_1.1fr]">
      <div className="card p-5">
        <SectionHeader>Victim Narrative</SectionHeader>
        <p className="leading-relaxed text-ink-primary">{highlightNarrative(complaint.narrative_text, entities)}</p>

        <div className="mt-6 border-t border-surface-border pt-5">
          <SectionHeader>Linked Complaints</SectionHeader>
          {relatedLoading && <LoadingSpinner label="Finding linked complaints…" />}
          {relatedError && <ErrorState message={relatedError} />}
          {related && related.related.length === 0 && (
            <EmptyState message="No other complaints linked to this network yet." />
          )}
          {related && related.related.length > 0 && (
            <>
              <p className="mb-3 text-sm text-ink-muted">
                {related.related.length} other complaint(s) share this account's discovered network.
              </p>
              <div className="space-y-2">
                {visibleLinked.map((r) => (
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
              {related.related.length > LINKED_PREVIEW_COUNT && (
                <button
                  onClick={() => setShowAllLinked((v) => !v)}
                  className="mt-3 flex items-center gap-1.5 text-sm font-medium text-series-1 hover:text-series-1/80"
                >
                  {showAllLinked ? "Show fewer" : `View all ${related.related.length} linked complaints`}
                  <ArrowRight className="h-3.5 w-3.5" strokeWidth={2} />
                </button>
              )}
            </>
          )}
        </div>
      </div>

      <div className="card p-5">
        <SectionHeader>Extracted Entities</SectionHeader>
        <div>
          <EntityRow icon={Landmark} label="Bank">
            {entities.bank_name || "Not detected"}
          </EntityRow>
          <EntityRow icon={Tag} label="IFSC Code">
            <span className="id-tag text-status-warning">{entities.ifsc_code || "Not detected"}</span>
          </EntityRow>
          <EntityRow icon={IndianRupee} label="Amount Mentioned">
            <span className="id-tag">{entities.amount ? `₹${entities.amount.toLocaleString("en-IN")}` : "Not detected"}</span>
          </EntityRow>
          <EntityRow icon={() => <span className="mt-0.5 flex h-4 w-4 items-center justify-center"><span className="h-2 w-2 rounded-full bg-series-1" /></span>} label="Status">
            <span className="inline-flex items-center rounded-sm bg-series-1/15 px-2 py-0.5 text-xs font-medium uppercase tracking-wide text-series-1">
              {complaint.status}
            </span>
          </EntityRow>
          <EntityRow icon={Hash} label="Complaint ID">
            <span className="id-tag">{complaintCode}</span>
          </EntityRow>
        </div>
      </div>

      <div className="card p-5">
        <SectionHeader color="series-2">Top 5 Predicted Locations</SectionHeader>
        {top5.length > 0 ? (
          <>
            <div className="mb-3 overflow-hidden rounded-md">
              <CashOutMap predictions={top5} height={160} />
            </div>
            <ul className="space-y-1">
              {top5.map((p) => (
                <li key={p.withdrawal_point_id} className="flex items-center gap-2 py-1.5 text-xs">
                  <span className="id-tag flex h-4 w-4 shrink-0 items-center justify-center rounded-sm bg-white/10 text-[10px] font-bold text-ink-muted">
                    {p.rank}
                  </span>
                  <span className="min-w-0 flex-1 truncate text-ink-secondary">{p.name}</span>
                  <span className="id-tag shrink-0 font-semibold text-series-2">{Math.round(p.confidence * 100)}%</span>
                </li>
              ))}
            </ul>
            <button
              onClick={() => navigate("../map")}
              className="mt-3 flex w-full items-center justify-center gap-1.5 rounded-md border border-series-2/40 bg-series-2/10 px-3 py-2 text-xs font-medium text-series-2 hover:bg-series-2/20"
            >
              <MapIcon className="h-3.5 w-3.5" strokeWidth={2} /> View Full Map
            </button>
          </>
        ) : (
          <LoadingSpinner label="Scoring locations…" />
        )}
      </div>
    </div>
  );
}
