"""The scoring harness runs, is deterministic, and known-hard slots stay visibly hard."""

from run_eval import by_slot_recall, score
from synth import generate


def test_evaluation_is_deterministic():
    a = score(generate(5, seed=7))
    b = score(generate(5, seed=7))
    assert a == b


def test_checksum_kinds_have_no_false_positives():
    results = score(generate(10, seed=8))
    assert results["IBAN"]["fp"] == 0
    assert results["TCKN"]["fp"] == 0


def test_hard_categories_are_counted_as_misses_not_hidden():
    recall = by_slot_recall(generate(5, seed=9))
    assert recall["TCKN_TYPO"][0] == 0  # mistyped IDs pass through: documented limit
    assert recall["AD_AMBIGUOUS_ALONE"][0] == 0
    assert recall["AD_UNSEEN"][0] < recall["AD_UNSEEN"][1]
