"""Search for near-optimal linear combination weights across the validated
feature set, rather than continuing to hand-guess splits.

Uses random search over the weight simplex (Dirichlet sampling) rather than
a grid — grid search scales badly past ~2-3 dimensions, random search covers
a high-dimensional space more efficiently for the same budget.

Tunes ONLY on the training split, then confirms the winner on held-out data
— same discipline as phase_sweep.py / signals_validate.py. A weight sweep
tuned and evaluated on the same data would just be sophisticated overfitting.

Usage:
    DATABASE_URL=... SECRET_KEY=... python -m experiments.weight_sweep your@email.com
"""
import asyncio
import sys
import numpy as np

from experiments.backtest import replay_history, summarize
from experiments.models import StaticWeightsModel
from experiments.run import load_entries
from app.predictor.config import FEATURE_ORDER, DEFAULT_WEIGHTS as HAND_PICKED_WEIGHTS

N_SAMPLES = 1000
SPLIT_FRAC = 0.85
SEED = 109


def sample_weights(rng: np.random.Generator) -> dict:
    raw = rng.dirichlet(np.ones(len(FEATURE_ORDER)))
    return dict(zip(FEATURE_ORDER, raw.tolist()))


def held_out_summary(entries, split_time, weights):
    model = StaticWeightsModel(weights=weights)
    results = replay_history(entries, model)  # full history informs predictions
    held_out = [r for r in results if r["created_at"] >= split_time]
    return summarize(held_out)


async def main(email: str):
    entries = await load_entries(email)
    split_idx = int(len(entries) * SPLIT_FRAC)
    train_entries = entries[:split_idx]
    split_time = entries[split_idx]["created_at"]

    print(f"Loaded {len(entries)} entries. Searching on first {split_idx} (train), validating on the rest.\n")

    rng = np.random.default_rng(SEED)
    scored = []
    for i in range(N_SAMPLES):
        w = sample_weights(rng)
        model = StaticWeightsModel(weights=w, name=f"sample_{i}")
        s = summarize(replay_history(train_entries, model))
        scored.append((w, s["top3_hit_rate"]))

    scored.sort(key=lambda x: x[1], reverse=True)
    best_weights, best_train_score = scored[0]

    print(f"Best on TRAIN split (top3_hit_rate={best_train_score:.3f}):")
    for k in FEATURE_ORDER:
        print(f"  {k:<18} {best_weights[k]:.3f}")

    # Feature relevance: average weight in the top 10% of samples vs the
    # bottom 10% — a feature that's consistently high in good configs and
    # low in bad ones is doing real work; one with no pattern (similar
    # average either way) is likely not contributing much.
    n = len(scored)
    top_decile = scored[: max(1, n // 10)]
    bottom_decile = scored[-max(1, n // 10):]
    print(f"\nFeature relevance (avg weight: top 10% of configs vs bottom 10%):")
    for k in FEATURE_ORDER:
        top_avg = sum(w[k] for w, _ in top_decile) / len(top_decile)
        bottom_avg = sum(w[k] for w, _ in bottom_decile) / len(bottom_decile)
        flag = "  <- low in both, possibly not useful" if top_avg < 0.08 and bottom_avg < 0.08 else ""
        print(f"  {k:<18} top={top_avg:.3f}  bottom={bottom_avg:.3f}{flag}")

    # Confirm on held-out data — the step that actually matters.
    val_summary = held_out_summary(entries, split_time, best_weights)
    print(f"\nHeld-out validation of the search winner (n={val_summary['n_events']}):")
    print(f"  top1={val_summary['top1_accuracy']:.3f} top3={val_summary['top3_hit_rate']:.3f} mrr={val_summary['mean_mrr']:.3f}")

    ref_summary = held_out_summary(entries, split_time, HAND_PICKED_WEIGHTS)
    print(f"\nFor comparison, hand-picked weights on the same held-out slice:")
    print(f"  top1={ref_summary['top1_accuracy']:.3f} top3={ref_summary['top3_hit_rate']:.3f} mrr={ref_summary['mean_mrr']:.3f}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python -m experiments.weight_sweep <email>")
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))
