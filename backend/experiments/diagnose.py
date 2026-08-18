"""Diagnose why the online mixer underperformed the static baseline.

Usage:
    DATABASE_URL=... SECRET_KEY=... python -m experiments.diagnose your@email.com

Two things this checks:
1. A lr/l2 grid sweep for both mixer modes, to see if the defaults (0.05/0.1)
   were just poorly chosen rather than online learning being wrong here.
2. A first-half vs second-half split of each run, to see whether the mixer
   is uniformly worse or specifically getting worse as it accumulates
   updates (the latter points at instability, not just "wrong idea").
"""
import asyncio
import sys

from experiments.backtest import replay_history, summarize
from experiments.models import MixerModel, StaticWeightsModel
from experiments.run import load_entries

LR_GRID = [0.01, 0.02, 0.05, 0.1, 0.2]
L2_GRID = [0.05, 0.1, 0.3, 0.6, 1.0]


def half_split_summary(entries, model_factory):
    """Runs once, then compares accuracy on the first half of scoreable
    events vs the second half — reveals whether the model improves,
    degrades, or stays flat as it sees more data."""
    model = model_factory()
    results = replay_history(entries, model)
    mid = len(results) // 2
    first_half = summarize(results[:mid])
    second_half = summarize(results[mid:])
    return first_half, second_half


def sweep(entries):
    print(f"\n{'mode':<12} {'lr':>6} {'l2':>6} {'top1_acc':>9} {'top3_hit':>9} {'mean_mrr':>9}")
    print("-" * 56)

    static_summary = summarize(replay_history(entries, StaticWeightsModel()))
    print(
        f"{'static':<12} {'--':>6} {'--':>6} "
        f"{static_summary['top1_accuracy']:>9.3f} {static_summary['top3_hit_rate']:>9.3f} "
        f"{static_summary['mean_mrr']:>9.3f}   <- baseline"
    )
    print()

    best = {"score": -1, "config": None}
    for mode in ["miss_only", "always"]:
        for lr in LR_GRID:
            for l2 in L2_GRID:
                model = MixerModel(mode=mode, lr=lr, l2=l2)
                results = replay_history(entries, model)
                s = summarize(results)
                print(
                    f"{mode:<12} {lr:>6} {l2:>6} "
                    f"{s['top1_accuracy']:>9.3f} {s['top3_hit_rate']:>9.3f} {s['mean_mrr']:>9.3f}"
                )
                if s["top3_hit_rate"] > best["score"]:
                    best["score"] = s["top3_hit_rate"]
                    best["config"] = (mode, lr, l2, s)

    print(f"\nBest config found: mode={best['config'][0]} lr={best['config'][1]} l2={best['config'][2]}")
    print(f"  vs static baseline top3_hit_rate={static_summary['top3_hit_rate']:.3f}")
    print(f"  best mixer top3_hit_rate={best['config'][3]['top3_hit_rate']:.3f}")


def print_half_split(entries):
    print(f"\n{'model':<20} {'first-half top3':>16} {'second-half top3':>18}")
    print("-" * 56)
    for name, factory in [
        ("static_weights", lambda: StaticWeightsModel()),
        ("miss_only (default)", lambda: MixerModel(mode="miss_only")),
        ("always (default)", lambda: MixerModel(mode="always")),
    ]:
        first, second = half_split_summary(entries, factory)
        f1 = first["top3_hit_rate"] if first["n_events"] else float("nan")
        f2 = second["top3_hit_rate"] if second["n_events"] else float("nan")
        print(f"{name:<20} {f1:>16.3f} {f2:>18.3f}")


async def main(email: str):
    entries = await load_entries(email)
    print(f"Loaded {len(entries)} exercise entries for {email}")

    print("\n=== First half vs second half (is the mixer getting better or worse over time?) ===")
    print_half_split(entries)

    print("\n=== lr/l2 sweep (can tuning beat the static baseline?) ===")
    sweep(entries)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python -m experiments.diagnose <email>")
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))
