"""Validate the phase_sweep winner isn't overfit to the exact dataset it
was chosen on. Splits history chronologically: tunes phase_cutoff /
min_phase_support on the first split_frac of events, then checks whether
that same config still beats no-phase on the held-out remainder.

Usage:
    DATABASE_URL=... SECRET_KEY=... python -m experiments.phase_validate your@email.com
"""
import asyncio
import sys

from experiments.backtest import replay_history, summarize
from experiments.models import StaticWeightsModel
from experiments.run import load_entries
from app.predictor.mixer import DEFAULT_WEIGHTS

CUTOFF_GRID = [2, 3, 4, 5, 6, 8, 10, 12, 15]
SUPPORT_GRID = [2, 3, 5, 8, 12]
SPLIT_FRAC = 0.7  # tune on first 70% of history (by entry count), validate on last 30%

NO_PHASE_WEIGHTS = {"transition": 0.4, "weekday": 0.1, "recency": 0.5}


def best_config_on(entries):
    best = {"score": -1, "config": None}
    for cutoff in CUTOFF_GRID:
        for support in SUPPORT_GRID:
            model = StaticWeightsModel(weights=DEFAULT_WEIGHTS)
            results = replay_history(entries, model, phase_cutoff=cutoff, min_phase_support=support)
            s = summarize(results)
            if s["top3_hit_rate"] > best["score"]:
                best["score"] = s["top3_hit_rate"]
                best["config"] = (cutoff, support)
    return best["config"]


async def main(email: str):
    entries = await load_entries(email)
    split_idx = int(len(entries) * SPLIT_FRAC)
    train_entries = entries[:split_idx]
    val_entries = entries  # backtest needs full prefix history to score val events correctly

    print(f"Loaded {len(entries)} entries. Tuning on first {split_idx}, validating on the rest.\n")

    cutoff, support = best_config_on(train_entries)
    print(f"Best config found on training split: phase_cutoff={cutoff}, min_phase_support={support}\n")

    # Score on the FULL entries list (so history before the split still
    # informs predictions), but only report metrics for events that occur
    # AFTER split_idx — i.e., only score what was actually held out.
    def held_out_summary(model_fn, **kwargs):
        model = model_fn()
        results = replay_history(val_entries, model, **kwargs)
        held_out = [r for r in results if r["created_at"] >= entries[split_idx]["created_at"]]
        return summarize(held_out)

    no_phase = held_out_summary(lambda: StaticWeightsModel(weights=NO_PHASE_WEIGHTS))
    with_phase = held_out_summary(
        lambda: StaticWeightsModel(weights=DEFAULT_WEIGHTS),
        phase_cutoff=cutoff, min_phase_support=support,
    )

    print("Held-out validation (events the config was NOT tuned on):")
    print(f"  no_phase:   top1={no_phase['top1_accuracy']:.3f} top3={no_phase['top3_hit_rate']:.3f} mrr={no_phase['mean_mrr']:.3f}  (n={no_phase['n_events']})")
    print(f"  with_phase: top1={with_phase['top1_accuracy']:.3f} top3={with_phase['top3_hit_rate']:.3f} mrr={with_phase['mean_mrr']:.3f}  (n={with_phase['n_events']})")

    if with_phase["n_events"] < 50:
        print("\nNote: small held-out sample — treat this result as directional, not conclusive.")

    if with_phase["top3_hit_rate"] > no_phase["top3_hit_rate"]:
        print("\n-> Phase awareness holds up on held-out data. Reasonable to ship.")
    else:
        print("\n-> Phase awareness did NOT clearly hold up on held-out data — likely overfit to the tuning split.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python -m experiments.phase_validate <email>")
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))
