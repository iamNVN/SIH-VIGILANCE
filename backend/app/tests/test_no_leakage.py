"""
The single most important invariant in this project (Blueprint Section 4,
PROGRESS_LOG.md's own "do not regress" callout): `ring_id` and
`account_type` (mule/victim/normal) are GENERATOR-SIDE GROUND TRUTH, never
legitimate model inputs. Louvain-discovered `community_id`/`community_*`
features are fine -- they're the model's own unsupervised discovery, not
an answer key. This test exists so a future refactor that accidentally
wires ground truth back in as a "helpful" feature fails loudly here,
immediately, rather than being caught (or not) by a suspiciously-good
evaluation number.
"""

from graph_engine.features import ADVANCED_FEATURE_COLUMNS, BASELINE_FEATURE_COLUMNS

LEAKY_COLUMNS = {"ring_id", "account_type", "is_mule", "is_fraud_ring"}


def test_no_leaky_columns_in_baseline():
    assert not (LEAKY_COLUMNS & set(BASELINE_FEATURE_COLUMNS))


def test_no_leaky_columns_in_advanced():
    assert not (LEAKY_COLUMNS & set(ADVANCED_FEATURE_COLUMNS))


def test_advanced_is_a_strict_superset_of_baseline():
    # advanced_model.py fuses graph+temporal+geo features ON TOP of the
    # baseline tabular set -- if this stops being true, the two models are
    # no longer a fair "does the graph help" comparison (Section 18's
    # entire point).
    assert set(BASELINE_FEATURE_COLUMNS).issubset(set(ADVANCED_FEATURE_COLUMNS))
