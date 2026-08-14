"""Walk-forward backtest harness.

Replays a user's chronological exercise history one logged set at a time.
At each event, the model predicts using ONLY aggregates built from events
strictly before it (no lookahead), gets scored against what was actually
logged, updates (if the model learns), and only then folds that event into
the running aggregates for the next step.

Reuses app.predictor.features.build_candidates directly — the same function
production calls — so a model that wins here is guaranteed to behave
identically when it's actually live. No feature math is duplicated.
"""
from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo

from app.predictor.features import build_candidates

LOCAL_TZ = ZoneInfo("America/New_York")

TOP_K = 3


def replay_history(entries: list[dict], model) -> list[dict]:
    """entries: chronological list of {"name": str, "created_at": datetime},
    one user's exercise-type log, already sorted ascending by created_at.
    model: any RankerModel (see models.py).

    Returns one result dict per scoreable event (an event is only scoreable
    if that exercise has appeared at least once before — matches the cold
    start behavior already accepted in production)."""
    transition_counts: dict = defaultdict(lambda: defaultdict(int))
    weekday_counts: dict = defaultdict(lambda: defaultdict(int))
    last_seen: dict = {}
    last_in_day: dict = {}
    day_exercise_seen: set = set()

    results = []

    for entry in entries:
        name = entry["name"]
        created_at: datetime = entry["created_at"]
        day = created_at.astimezone(LOCAL_TZ).date()
        today_wd = day.weekday()
        last_exercise = last_in_day.get(day)

        aggregates = {
            "transition_counts": transition_counts,
            "weekday_counts": weekday_counts,
            "last_seen": last_seen,
        }
        candidates = build_candidates(aggregates, last_exercise, now=created_at)

        if name in last_seen:
            ranked = model.predict(candidates)
            rank = ranked.index(name)
            hit = rank < TOP_K
            results.append({
                "created_at": created_at,
                "chosen": name,
                "rank": rank,
                "hit": hit,
                "mrr": 1.0 / (rank + 1),
                "n_candidates": len(candidates),
            })
            model.update(candidates, name)

        # Fold this event into running state regardless of whether it was
        # scoreable — matches production, where every logged set updates
        # history even if it was a cold-start exercise this time.
        if last_exercise:
            transition_counts[last_exercise][name] += 1
        last_in_day[day] = name
        key = (day, name)
        if key not in day_exercise_seen:
            weekday_counts[today_wd][name] += 1
            day_exercise_seen.add(key)
        last_seen[name] = created_at

    return results


def summarize(results: list[dict]) -> dict:
    n = len(results)
    if n == 0:
        return {"n_events": 0, "top1_accuracy": None, "top3_hit_rate": None, "mean_mrr": None}
    return {
        "n_events": n,
        "top1_accuracy": sum(r["rank"] == 0 for r in results) / n,
        "top3_hit_rate": sum(r["hit"] for r in results) / n,
        "mean_mrr": sum(r["mrr"] for r in results) / n,
    }


def rolling_accuracy(results: list[dict], window: int = 20) -> list[dict]:
    """Top-3 hit rate over a trailing window of N events — the trend line
    that actually shows a model improving, not just a single final number."""
    out = []
    for i in range(len(results)):
        chunk = results[max(0, i - window + 1): i + 1]
        out.append({
            "created_at": results[i]["created_at"],
            "rolling_top3_hit_rate": sum(r["hit"] for r in chunk) / len(chunk),
        })
    return out
