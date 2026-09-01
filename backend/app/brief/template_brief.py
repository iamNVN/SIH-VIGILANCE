"""
template_brief.py -- Jinja2-templated intervention brief (Blueprint Section
4/15/24). This is the GUARANTEED default output -- deterministic, not
hallucinated (Section 14: "REAL (template-generated)"). An LLM-grounded
version is a 10 Sep stretch (Section 15) that must fall back to exactly
this template on any failure/timeout (Section 24 kill-switch) -- so this
module's contract (`generate_brief(context) -> str`) is what that future
LLM wrapper will also have to satisfy.
"""

from jinja2 import Template

BRIEF_TEMPLATE = Template(
    """\
INTERVENTION BRIEF -- Complaint #{{ complaint_id }}
Generated: {{ generated_at }}
Model version: {{ model_version }}

VICTIM & LOSS
  Amount at risk: Rs {{ "{:,.2f}".format(amount_at_risk) }}
  Bank: {{ bank_name }}

TOP PREDICTED CASH-OUT LOCATION
  #{{ top_prediction.rank }} {{ top_prediction.name }} ({{ top_prediction.lat }}, {{ top_prediction.lon }})
  Confidence: {{ "{:.0%}".format(top_prediction.confidence) }}
  Estimated window: {{ top_prediction.estimated_window.earliest }} -- {{ top_prediction.estimated_window.latest }}
  Urgency: {{ top_prediction.urgency }}

WHY
  {{ top_prediction.explanation.narrative }}
  Top signals: {{ top_prediction.explanation.top_features | join(", ") }}

LINKED CASES
{% if related_complaints %}
{% for rc in related_complaints %}
  - Complaint #{{ rc.complaint_id }} (shared account/community, filed {{ rc.filed_at }})
{% endfor %}
{% else %}
  - No other complaints currently linked to this account/community.
{% endif %}

OTHER RANKED LOCATIONS
{% for p in other_predictions %}
  #{{ p.rank }} {{ p.name }} -- confidence {{ "{:.0%}".format(p.confidence) }}
{% endfor %}

RECOMMENDED ACTION
  Alert the withdrawal point(s) above and the issuing bank's fraud desk within the
  estimated window. This brief requires investigator review and approval before
  any action is taken -- nothing here is auto-executed (Blueprint Section 14/25).
"""
)


def generate_brief(prediction_response: dict, related_complaints: list | None = None) -> str:
    """`prediction_response` is exactly the Section 11 JSON contract.
    `related_complaints` is the `/related/{complaint_id}` response (a list
    of {"complaint_id": ..., "filed_at": ...} dicts), or None/empty."""
    predictions = prediction_response["predictions"]
    top_prediction = predictions[0]
    other_predictions = predictions[1:]

    return BRIEF_TEMPLATE.render(
        complaint_id=prediction_response["complaint_id"],
        generated_at=prediction_response["generated_at"],
        model_version=prediction_response["model_version"],
        amount_at_risk=top_prediction["amount_at_risk"],
        bank_name=prediction_response.get("bank_name", "N/A"),
        top_prediction=top_prediction,
        other_predictions=other_predictions,
        related_complaints=related_complaints or [],
    )
