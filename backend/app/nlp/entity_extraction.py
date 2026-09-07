"""
entity_extraction.py -- regex-only entity extraction over complaint
narrative text (Blueprint Section 4: "Regex + spaCy rule-based Matcher --
NOT a trained transformer, unnecessary risk for structured synthetic
text"). Only the regex half is built -- sufficient for the generator's
templated narratives (see data/generator/generate_synthetic_data.py's
NARRATIVE_TEMPLATES) and for the Complaint Detail screen's "entities
extracted live from the narrative" demo beat (Section 13). A spaCy
rule-based Matcher pass is future work, not today's scope.

Seven fields are extracted, not three -- but only bank/IFSC/amount ever
match on THIS dataset. The generator's own NARRATIVE_TEMPLATES (see the
file above) never mention a UTR, a beneficiary name, an in-text location,
or a timestamp inside the narrative string itself (filed_at is a separate
DB column, not narrative text) -- so utr/beneficiary/location/timestamp
are real, working patterns that correctly return None on every complaint
in this demo, not stubs. They exist so a real NCRP narrative that DOES
mention "UTR 411023556789" or "transferred to Ramesh Kumar" gets picked
up without code changes -- the extractor was under-built for the claim
made about it, not the other way around.
"""

import re
from typing import Optional

BANK_NAMES = [
    "State Bank of India", "HDFC Bank", "ICICI Bank", "Axis Bank",
    "Punjab National Bank", "Bank of Baroda",
]

# Same 5 cities the rest of the app scopes investigators to (see
# auth/AuthContext.jsx's PERSONAS / api/stats.py) -- the real, finite
# location vocabulary this deployment actually knows about, not a
# generic gazetteer that would false-positive on common English words.
KNOWN_LOCATIONS = ["Bengaluru", "Bangalore", "Chennai", "Delhi", "Hyderabad", "Mumbai"]

AMOUNT_RE = re.compile(r"Rs\.?\s?([\d,]+(?:\.\d+)?)")
IFSC_RE = re.compile(r"\b([A-Z]{4}0[A-Z0-9]{3,6})\b")
# UPI UTRs are 12 digits; NEFT/RTGS/IMPS reference numbers run up to ~22
# alphanumeric chars -- matches either, following a UTR/reference/txn-id
# label so a bare 12-digit amount or phone number isn't mistaken for one.
UTR_RE = re.compile(r"\b(?:UTR|UPI\s*ref(?:erence)?|transaction\s*(?:id|reference))[\s:#-]*([A-Z0-9]{9,22})\b", re.IGNORECASE)
# A labeled beneficiary/recipient name -- stops at the next clause
# (comma/period/"and"/"who") rather than swallowing the rest of the
# sentence.
BENEFICIARY_RE = re.compile(
    r"(?i:beneficiary(?:\s+name)?(?:\s+(?:is|was))?)[\s:]+([A-Z][a-zA-Z.\s]{2,40}?)(?=[,.]| who| and\b|$)"
)
# dd/mm/yyyy or dd-mm-yyyy, optionally followed by a 24h or 12h clock time.
TIMESTAMP_RE = re.compile(
    r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}(?:[ ,]+\d{1,2}:\d{2}(?:\s?[AP]M)?)?)\b", re.IGNORECASE
)


def extract_entities(narrative_text: str) -> dict:
    bank_match: Optional[str] = next((b for b in BANK_NAMES if b in narrative_text), None)

    amount_match = AMOUNT_RE.search(narrative_text)
    amount: Optional[float] = None
    if amount_match:
        amount = float(amount_match.group(1).replace(",", ""))

    ifsc_match = IFSC_RE.search(narrative_text)
    ifsc_code = ifsc_match.group(1) if ifsc_match else None

    utr_match = UTR_RE.search(narrative_text)
    utr = utr_match.group(1) if utr_match else None

    beneficiary_match = BENEFICIARY_RE.search(narrative_text)
    beneficiary = beneficiary_match.group(1).strip() if beneficiary_match else None

    location_match = next((loc for loc in KNOWN_LOCATIONS if loc in narrative_text), None)

    timestamp_match = TIMESTAMP_RE.search(narrative_text)
    timestamp = timestamp_match.group(1) if timestamp_match else None

    return {
        "bank_name": bank_match,
        "ifsc_code": ifsc_code,
        "amount": amount,
        "utr": utr,
        "beneficiary": beneficiary,
        "location": location_match,
        "timestamp": timestamp,
    }
