"""Walk-forward backtest harness.

Replays a user's chronological exercise history one logged set at a time.
At each event, the model predicts using ONLY aggregates built from events
strictly before it (no lookahead), gets scored against what was actually
logged, updates (if the model learns), and only then folds that event into
the running aggregates for the next step.

Reuses app.predictor.features.build_candidates directly — the same function
production calls — so a model that wins here is guaranteed to behave
identically when it's actually live. The aggregate state maintained here
mirrors app.predictor.features.get_session_aggregates exactly (including
phase-bucketed transitions), just built incrementally instead of via a
fresh DB query each time, since replaying via repeated queries would be
O(n^2) instead of O(n).
"""
from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo

from app.predictor.features import build_candidates
from app.predictor.config import PHASE_CUTOFF, MIN_PHASE_SUPPORT

LOCAL_TZ = ZoneInfo("America/New_York")

TOP_K = 3


def replay_history(
    entries: list[dict], model,
    phase_cutoff: int = PHASE_CUTOFF, min_phase_support: int = MIN_PHASE_SUPPORT,
) -> list[dict]:
    """entries: chronological list of {"name": str, "created_at": datetime},
    one user's exercise-type log, already sorted ascending by created_at.
    model: any RankerModel (see models.py).

    phase_cutoff/min_phase_support default to the same constants production
    uses, but are parameters here so experiments/phase_sweep.py can vary
    them across many runs without editing app/predictor/features.py between
    each one.

    Returns one result dict per scoreable event (an event is only scoreable
    if that exercise has appeared at least once before — matches the cold
    start behavior already accepted in production)."""
    transition_counts: dict = defaultdict(lambda: defaultdict(int))
    phase_transition_counts: dict = {
        "early": defaultdict(lambda: defaultdict(int)),
        "late": defaultdict(lambda: defaultdict(int)),
    }
    weekday_counts: dict = defaultdict(lambda: defaultdict(int))
    position_counts: dict = defaultdict(lambda: defaultdict(int))
    session_precedence_counts: dict = defaultdict(lambda: defaultdict(int))
    today_exercises_seen: dict = defaultdict(set)  # day -> distinct exercises logged so far that day
    last_seen: dict = {}
    last_in_day: dict = {}
    day_position: dict = defaultdict(int)  # day -> count of sets logged so far that day
    day_exercise_seen: set = set()

    results = []

    for entry in entries:
        name = entry["name"]
        created_at: datetime = entry["created_at"]
        day = created_at.astimezone(LOCAL_TZ).date()
        today_wd = day.weekday()
        last_exercise = last_in_day.get(day)
        session_len = day_position[day]  # sets logged today BEFORE this one
        today_so_far = today_exercises_seen[day]  # distinct exercises today BEFORE this one

        aggregates = {
            "transition_counts": transition_counts,
            "phase_transition_counts": phase_transition_counts,
            "weekday_counts": weekday_counts,
            "position_counts": position_counts,
            "session_precedence_counts": session_precedence_counts,
            "today_exercises_so_far": today_so_far,
            "last_seen": last_seen,
            "today_session_length": session_len,
            "phase_cutoff": phase_cutoff,
        }
        candidates = build_candidates(aggregates, last_exercise, now=created_at, min_phase_support=min_phase_support)

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
        # position_counts uses session_len directly (the position this
        # entry occupies), unconditional on last_exercise — unlike
        # transition/phase, it's tracked even for the day's first set.
        position_counts[session_len][name] += 1

        # Only forms new precedence pairs the first time this exercise
        # appears today — repeats of an already-seen-today exercise don't
        # add new pairs, matching the "presence, not count" definition.
        if name not in today_so_far:
            for prior_name in today_so_far:
                session_precedence_counts[prior_name][name] += 1
            today_exercises_seen[day].add(name)

        if last_exercise:
            transition_counts[last_exercise][name] += 1
            # k = session_len (sets logged today before this one, including
            # last_exercise) — must match the k used at prediction time.
            phase = "early" if session_len < phase_cutoff else "late"
            phase_transition_counts[phase][last_exercise][name] += 1

        last_in_day[day] = name
        day_position[day] = session_len + 1

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
