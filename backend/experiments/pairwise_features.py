"""For each pair of features, sweep the best 2-way split (everything else
zeroed), check it against held-out data, and compare to the better of the
two features alone. A pair that beats max(solo_a, solo_b) by a lot is
capturing complementary information; a pair that barely beats the better
solo feature is largely redundant (one is absorbing the other).

Usage:
    DATABASE_URL=... SECRET_KEY=... python -m experiments.pairwise_features your@email.com
"""
import asyncio
import sys
import itertools
import numpy as np

from experiments.backtest import replay_history, summarize
from experiments.models import StaticWeightsModel
from experiments.run import load_entries
from app.predictor.config import FEATURE_ORDER

SPLIT_FRAC = 0.7
ALPHA_STEPS = 21  # 0.0, 0.05, ..., 1.0


def score_on(entries, weights) -> float:
    return summarize(replay_history(entries, StaticWeightsModel(weights=weights)))["top3_hit_rate"]


async def main(email: str):
    entries = await load_entries(email)
    split_idx = int(len(entries) * SPLIT_FRAC)
    train_entries = entries[:split_idx]
    split_time = entries[split_idx]["created_at"]
    print(f"Loaded {len(entries)} entries. Sweeping on first {split_idx}, validating on the rest.\n")

    def held_out_score(weights):
        results = replay_history(entries, StaticWeightsModel(weights=weights))
        held_out = [r for r in results if r["created_at"] >= split_time]
        return summarize(held_out)["top3_hit_rate"]

    # Solo scores first, for comparison.
    solo_train = {}
    solo_held = {}
    for f in FEATURE_ORDER:
        w = {k: (1.0 if k == f else 0.0) for k in FEATURE_ORDER}
        solo_train[f] = score_on(train_entries, w)
        solo_held[f] = held_out_score(w)

    print(f"{'pair':<32} {'best_alpha':>10} {'train_top3':>11} {'held_top3':>10} {'best_solo_held':>15} {'delta':>8}")
    print("-" * 90)

    for f1, f2 in itertools.combinations(FEATURE_ORDER, 2):
        best_alpha, best_train = 0.0, -1.0
        for alpha in np.linspace(0, 1, ALPHA_STEPS):
            w = {k: 0.0 for k in FEATURE_ORDER}
            w[f1] = alpha
            w[f2] = 1 - alpha
            s = score_on(train_entries, w)
            if s > best_train:
                best_train, best_alpha = s, alpha

        best_w = {k: 0.0 for k in FEATURE_ORDER}
        best_w[f1] = best_alpha
        best_w[f2] = 1 - best_alpha
        held = held_out_score(best_w)
        best_solo_held = max(solo_held[f1], solo_held[f2])
        delta = held - best_solo_held

        pair_label = f"{f1}+{f2}"
        flag = "  <- pair adds real value" if delta > 0.02 else ("  <- largely redundant" if delta < 0.005 else "")
        print(f"{pair_label:<32} {best_alpha:>10.2f} {best_train:>11.3f} {held:>10.3f} {best_solo_held:>15.3f} {delta:>+8.3f}{flag}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python -m experiments.pairwise_features <email>")
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))
