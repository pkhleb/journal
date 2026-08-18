"""Validate that both_signals (phase + position) actually holds up on
held-out data, not just the full dataset it was compared on.

Usage:
    DATABASE_URL=... SECRET_KEY=... python -m experiments.signals_validate your@email.com
"""
import asyncio
import sys

from experiments.backtest import replay_history, summarize
from experiments.models import (
    StaticWeightsModel,
    NONE_WEIGHTS,
    PHASE_ONLY_WEIGHTS,
    POSITION_ONLY_WEIGHTS,
    PRECEDENCE_ONLY_WEIGHTS,
)
from experiments.run import load_entries
from app.predictor.mixer import DEFAULT_WEIGHTS

SPLIT_FRAC = 0.7  # same split point as phase_validate.py, for comparability


async def main(email: str):
    entries = await load_entries(email)
    split_idx = int(len(entries) * SPLIT_FRAC)
    split_time = entries[split_idx]["created_at"]

    print(f"Loaded {len(entries)} entries. Validating on events after index {split_idx} ({split_time}).\n")

    configs = {
        "none": NONE_WEIGHTS,
        "phase_only": PHASE_ONLY_WEIGHTS,
        "position_only": POSITION_ONLY_WEIGHTS,
        "precedence_only": PRECEDENCE_ONLY_WEIGHTS,
        "all_signals": DEFAULT_WEIGHTS,
    }

    print(f"{'model':<22} {'top1_acc':>9} {'top3_hit':>9} {'mean_mrr':>9} {'n_held_out':>11}")
    print("-" * 66)

    held_out_scores = {}
    for name, weights in configs.items():
        model = StaticWeightsModel(weights=weights, name=name)
        results = replay_history(entries, model)  # full history informs predictions
        held_out = [r for r in results if r["created_at"] >= split_time]  # only score what's held out
        s = summarize(held_out)
        held_out_scores[name] = s
        print(f"{name:<22} {s['top1_accuracy']:>9.3f} {s['top3_hit_rate']:>9.3f} {s['mean_mrr']:>9.3f} {s['n_events']:>11}")

    baseline = held_out_scores["none"]["top3_hit_rate"]
    best_name = max(held_out_scores, key=lambda k: held_out_scores[k]["top3_hit_rate"])
    best_score = held_out_scores[best_name]["top3_hit_rate"]

    print(f"\nBest on held-out data: {best_name} ({best_score:.3f} vs no-signal baseline {baseline:.3f})")
    if held_out_scores["all_signals"]["n_events"] < 50:
        print("Note: small held-out sample — treat as directional, not conclusive.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python -m experiments.signals_validate <email>")
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))
