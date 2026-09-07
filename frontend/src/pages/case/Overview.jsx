import { ArrowRight, Calendar, Hash, IndianRupee, Landmark, MapPin, Tag, User } from "lucide-react";
import { useState } from "react";
import { useOutletContext } from "react-router-dom";
import { AccordionItem } from "../../components/Accordion";
import { api } from "../../api/client";
import { useApi } from "../../api/useApi";
import SectionHeader from "../../components/SectionHeader";
import { EmptyState, ErrorState, LoadingSpinner } from "../../components/StateViews";
import { caseCode } from "../../utils/caseCode";

const LINKED_PREVIEW_COUNT = 4;
function whyLinkedReasons(r) {
  const reasons = [];

  for (const acc of r.shared_accounts || []) {
    reasons.push(
      <>
        Shares mule account{" "}
        <span className="text-status-warning">
          {acc.account_number_fake}
        </span>{" "}
        ({acc.bank_name}) with this case.
      </>
    );
  }

  for (const wp of r.shared_withdrawal_points || []) {
    reasons.push(
      <>
        Money from both complaints was cashed out at the same location:{" "}
        <span className="text-status-warning">{wp.name}</span>.
      </>
    );
  }

  if (r.same_bank) {
    reasons.push(
      <>
        Filed against the same bank ({" "}
        <span className="text-status-warning">{r.bank_name}</span>
        ) as this complaint.
      </>
    );
  }

  if (reasons.length === 0) {
    reasons.push(
      <>Linked through this case's wider discovered account network.</>
    );
  }

  return reasons;
}

function highlightNarrative(text, entities) {
  const needles = [entities.bank_name, entities.ifsc_code, entities.utr, entities.beneficiary, entities.location].filter(Boolean);
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
  const { complaint } = useOutletContext();
  const entities = complaint.extracted_entities || {};
  const [showAllLinked, setShowAllLinked] = useState(false);
  const { data: related, loading: relatedLoading, error: relatedError } = useApi(
    (signal) => api.related(complaint.id, signal),
    [complaint.id]
  );

  const complaintCode = `CMP-${caseCode(complaint.id)}`;
  const visibleLinked = related ? (showAllLinked ? related.related : related.related.slice(0, LINKED_PREVIEW_COUNT)) : [];

  return (
    <div className="grid grid-cols-1 gap-12 lg:grid-cols-[1.5fr_1fr]">
      <div className="flex flex-col">
        <div>
          <SectionHeader>Victim Narrative</SectionHeader>
          <p className="leading-relaxed text-ink-primary">{highlightNarrative(complaint.narrative_text, entities)}</p>
        </div>

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
                        <span className="id-tag font-medium text-ink-primary">#{caseCode(r.complaint_id)}</span>
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
                            <span>{reason}</span>
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

      <div className="rounded-xl border border-surface-border p-5">
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
          {/* Real regex patterns (nlp/entity_extraction.py), not stubs --
              they correctly return null on every complaint in this demo
              because the synthetic generator's own narrative templates
              never mention a UTR, beneficiary name, in-text location, or
              timestamp -- not because the extractor can't find them. */}
          <EntityRow icon={Hash} label="UTR / Transaction Reference">
            <span className="id-tag text-status-warning">{entities.utr || "Not detected"}</span>
          </EntityRow>
          <EntityRow icon={User} label="Beneficiary">
            {entities.beneficiary || "Not detected"}
          </EntityRow>
          <EntityRow icon={MapPin} label="Location Mentioned">
            {entities.location || "Not detected"}
          </EntityRow>
          <EntityRow icon={Calendar} label="Timestamp Mentioned">
            {entities.timestamp || "Not detected"}
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
    </div>
  );
}
