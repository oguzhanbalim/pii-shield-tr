"""Score the detector on the synthetic set: exact-span precision and recall per kind.

Usage: python evaluation/run_eval.py [--n 20] [--seed 2030] [--misses 5]
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from synth import GOLD_KIND, TEMPLATES, Example, generate  # noqa: E402

from pii_shield_tr.detect import detect  # noqa: E402


def score(examples: list[Example]) -> dict[str, Counter]:
    """Per-kind tp/fp/fn counts, requiring exact span and kind."""
    results: dict[str, Counter] = {}
    for example in examples:
        predicted = {(s.start, s.end, s.kind.value) for s in detect(example.text)}
        gold = {(g.start, g.end, g.kind) for g in example.gold}
        for item in predicted | gold:
            bucket = results.setdefault(item[2], Counter())
            if item in predicted and item in gold:
                bucket["tp"] += 1
            elif item in predicted:
                bucket["fp"] += 1
            else:
                bucket["fn"] += 1
    return results


def by_slot_recall(examples: list[Example]) -> dict[str, tuple[int, int]]:
    """Recall per gold slot type, so hard categories are visible on their own."""
    out: dict[str, list[int]] = {}
    for example in examples:
        predicted = {(s.start, s.end, s.kind.value) for s in detect(example.text)}
        for g in example.gold:
            hit, total = out.setdefault(g.slot, [0, 0])
            out[g.slot] = [hit + ((g.start, g.end, g.kind) in predicted), total + 1]
    return {k: (v[0], v[1]) for k, v in out.items()}


def _ratio(numerator: int, denominator: int) -> str:
    return f"{numerator / denominator:.3f}" if denominator else "n/a"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=20, help="sentences per template")
    parser.add_argument("--seed", type=int, default=2030)
    parser.add_argument("--errors", type=int, default=0, help="print up to N wrong examples")
    args = parser.parse_args()

    examples = generate(args.n, args.seed)
    results = score(examples)
    print(
        f"Synthetic set: {len(TEMPLATES)} templates x {args.n} = {len(examples)} sentences, "
        f"seed {args.seed}. Self-written; exact span and kind required."
    )
    print()
    print(f"{'kind':<8}{'gold':>6}{'tp':>6}{'fp':>6}{'fn':>6}{'precision':>11}{'recall':>8}")
    totals: Counter = Counter()
    for kind in sorted(results):
        c = results[kind]
        totals.update(c)
        print(
            f"{kind:<8}{c['tp'] + c['fn']:>6}{c['tp']:>6}{c['fp']:>6}{c['fn']:>6}"
            f"{_ratio(c['tp'], c['tp'] + c['fp']):>11}{_ratio(c['tp'], c['tp'] + c['fn']):>8}"
        )
    print(
        f"{'ALL':<8}{totals['tp'] + totals['fn']:>6}{totals['tp']:>6}{totals['fp']:>6}"
        f"{totals['fn']:>6}{_ratio(totals['tp'], totals['tp'] + totals['fp']):>11}"
        f"{_ratio(totals['tp'], totals['tp'] + totals['fn']):>8}"
    )
    print()
    print("Recall by slot:")
    for slot, (hit, total) in sorted(by_slot_recall(examples).items()):
        print(f"  {slot:<20}{hit:>5}/{total:<5}{_ratio(hit, total):>7}  ({GOLD_KIND[slot]})")

    if args.errors:
        print()
        shown = 0
        for example in examples:
            predicted = {(s.start, s.end, s.kind.value) for s in detect(example.text)}
            gold = {(g.start, g.end, g.kind) for g in example.gold}
            if predicted != gold and shown < args.errors:
                shown += 1
                print(repr(example.text))
                print("  gold:", sorted(gold))
                print("  pred:", sorted(predicted))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
