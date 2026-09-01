"""
entity_extraction.py -- regex-only entity extraction over complaint
narrative text (Blueprint Section 4: "Regex + spaCy rule-based Matcher --
NOT a trained transformer, unnecessary risk for structured synthetic
text"). Only the regex half is built -- sufficient for the generator's
templated narratives (see data/generator/generate_synthetic_data.py's
NARRATIVE_TEMPLATES) and for the Complaint Detail screen's "entities
extracted live from the narrative" demo beat (Section 13). A spaCy
rule-based Matcher pass is future work, not today's scope.
"""

import re
from typing import Optional

BANK_NAMES = [
    "State Bank of India", "HDFC Bank", "ICICI Bank", "Axis Bank",
    "Punjab National Bank", "Bank of Baroda",
]

AMOUNT_RE = re.compile(r"Rs\.?\s?([\d,]+(?:\.\d+)?)")
IFSC_RE = re.compile(r"\b([A-Z]{4}0[A-Z0-9]{3,6})\b")


def extract_entities(narrative_text: str) -> dict:
    bank_match: Optional[str] = next((b for b in BANK_NAMES if b in narrative_text), None)

    amount_match = AMOUNT_RE.search(narrative_text)
    amount: Optional[float] = None
    if amount_match:
        amount = float(amount_match.group(1).replace(",", ""))

    ifsc_match = IFSC_RE.search(narrative_text)
    ifsc_code = ifsc_match.group(1) if ifsc_match else None

    return {"bank_name": bank_match, "ifsc_code": ifsc_code, "amount": amount}
