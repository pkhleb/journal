"""How well does each feature predict the next exercise on its own, with
zero weight on everything else? Directly measures univariate predictive
power — useful alongside feature_correlation.py's redundancy findings.

Caveat: a feature evaluated alone produces many exact ties (e.g.
transition scores 0 for every candidate that's never directly followed
last_exercise) — those ties are broken by stable-sort insertion order,
which isn't meaningful. Sparse signals (transition, phase_transition) will
show this more than dense ones (recency). Read low scores for sparse
features with that in mind, not as pure "this feature is bad."

Usage:
    DATABASE_URL=... SECRET_KEY=... python -m experiments.single_feature your@email.com
"""
import asyncio
import sys

from experiments.backtest import replay_history, summarize
from experiments.models import StaticWeightsModel
from experiments.run import load_entries
from app.predictor.config import FEATURE_ORDER


async def main(email: str):
    entries = await load_entries(email)
    print(f"Loaded {len(entries)} entries.\n")

    print(f"{'feature (alone)':<20} {'top1_acc':>9} {'top3_hit':>9} {'mean_mrr':>9}")
    print("-" * 50)

    results = []
    for feature in FEATURE_ORDER:
        weights = {k: (1.0 if k == feature else 0.0) for k in FEATURE_ORDER}
        model = StaticWeightsModel(weights=weights, name=feature)
        s = summarize(replay_history(entries, model))
        results.append((feature, s))
        print(f"{feature:<20} {s['top1_accuracy']:>9.3f} {s['top3_hit_rate']:>9.3f} {s['mean_mrr']:>9.3f}")

    results.sort(key=lambda x: x[1]["top3_hit_rate"], reverse=True)
    print(f"\nRanked by standalone top3_hit_rate: {' > '.join(f for f, _ in results)}")
    print("\nNote: sparse signals (transition, phase_transition) tie heavily when isolated —")
    print("their standalone score understates how useful they are IN COMBINATION with others.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python -m experiments.single_feature <email>")
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))
