"""Sweep phase_cutoff / min_phase_support against real data.

Usage:
    DATABASE_URL=... SECRET_KEY=... python -m experiments.phase_sweep your@email.com
"""
import asyncio
import sys

from experiments.backtest import replay_history, summarize
from experiments.models import StaticWeightsModel
from experiments.run import load_entries
from app.predictor.mixer import DEFAULT_WEIGHTS

CUTOFF_GRID = [2, 3, 4, 5, 6, 8, 10, 12, 15, 18, 21, 24]
SUPPORT_GRID = [1, 2, 3, 5, 8, 12]


async def main(email: str):
    entries = await load_entries(email)
    print(f"Loaded {len(entries)} exercise entries for {email}")

    baseline = summarize(replay_history(entries, StaticWeightsModel(weights={
        "transition": 0.4, "weekday": 0.1, "recency": 0.5,
    })))
    print(f"\nno-phase baseline: top1={baseline['top1_accuracy']:.3f} "
          f"top3={baseline['top3_hit_rate']:.3f} mrr={baseline['mean_mrr']:.3f}\n")

    print(f"{'cutoff':>7} {'min_support':>12} {'top1_acc':>9} {'top3_hit':>9} {'mean_mrr':>9}")
    print("-" * 52)

    best = {"score": -1, "config": None}
    for cutoff in CUTOFF_GRID:
        for support in SUPPORT_GRID:
            model = StaticWeightsModel(weights=DEFAULT_WEIGHTS)
            results = replay_history(entries, model, phase_cutoff=cutoff, min_phase_support=support)
            s = summarize(results)
            print(f"{cutoff:>7} {support:>12} {s['top1_accuracy']:>9.3f} {s['top3_hit_rate']:>9.3f} {s['mean_mrr']:>9.3f}")
            if s["top3_hit_rate"] > best["score"]:
                best["score"] = s["top3_hit_rate"]
                best["config"] = (cutoff, support, s)

    cutoff, support, s = best["config"]
    print(f"\nBest: phase_cutoff={cutoff}, min_phase_support={support}")
    print(f"  top3_hit_rate={s['top3_hit_rate']:.3f} vs no-phase baseline={baseline['top3_hit_rate']:.3f}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python -m experiments.phase_sweep <email>")
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))
