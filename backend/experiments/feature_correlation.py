"""Are recency and weekday (or phase_transition) actually encoding
overlapping information? Walks history the same way the backtest does, but
instead of scoring predictions, collects every candidate's raw feature
vector at every event, then reports the pairwise correlation matrix.

A high correlation between two features means one is largely redundant
given the other — which would explain why the weight search drives one of
them toward zero once both are free to be weighted properly.

Usage:
    DATABASE_URL=... SECRET_KEY=... python -m experiments.feature_correlation your@email.com
"""
import asyncio
import sys
from collections import defaultdict
import numpy as np

from app.predictor.features import build_candidates
from app.predictor.config import FEATURE_ORDER, PHASE_CUTOFF, MIN_PHASE_SUPPORT
from experiments.run import load_entries
from zoneinfo import ZoneInfo

LOCAL_TZ = ZoneInfo("America/New_York")


async def main(email: str):
    entries = await load_entries(email)
    print(f"Loaded {len(entries)} entries.\n")

    transition_counts: dict = defaultdict(lambda: defaultdict(int))
    phase_transition_counts: dict = {"early": defaultdict(lambda: defaultdict(int)), "late": defaultdict(lambda: defaultdict(int))}
    weekday_counts: dict = defaultdict(lambda: defaultdict(int))
    position_counts: dict = defaultdict(lambda: defaultdict(int))
    session_precedence_counts: dict = defaultdict(lambda: defaultdict(int))
    today_exercises_seen: dict = defaultdict(set)
    last_seen: dict = {}
    last_in_day: dict = {}
    day_position: dict = defaultdict(int)
    day_exercise_seen: set = set()

    rows = []  # every candidate's feature vector, across every scoreable event

    for entry in entries:
        name = entry["name"]
        created_at = entry["created_at"]
        day = created_at.astimezone(LOCAL_TZ).date()
        today_wd = day.weekday()
        last_exercise = last_in_day.get(day)
        session_len = day_position[day]
        today_so_far = today_exercises_seen[day]

        aggregates = {
            "transition_counts": transition_counts,
            "phase_transition_counts": phase_transition_counts,
            "weekday_counts": weekday_counts,
            "position_counts": position_counts,
            "session_precedence_counts": session_precedence_counts,
            "today_exercises_so_far": today_so_far,
            "last_seen": last_seen,
            "today_session_length": session_len,
            "phase_cutoff": PHASE_CUTOFF,
        }
        candidates = build_candidates(aggregates, last_exercise, now=created_at, min_phase_support=MIN_PHASE_SUPPORT)

        if name in last_seen:  # only scoreable events, matching the backtest
            for c in candidates:
                rows.append([c["features"].get(k, 0.0) for k in FEATURE_ORDER])

        # Same incremental bookkeeping as backtest.py.
        position_counts[session_len][name] += 1
        if name not in today_so_far:
            for prior_name in today_so_far:
                session_precedence_counts[prior_name][name] += 1
            today_exercises_seen[day].add(name)
        if last_exercise:
            transition_counts[last_exercise][name] += 1
            phase = "early" if session_len < PHASE_CUTOFF else "late"
            phase_transition_counts[phase][last_exercise][name] += 1
        last_in_day[day] = name
        day_position[day] = session_len + 1
        key = (day, name)
        if key not in day_exercise_seen:
            weekday_counts[today_wd][name] += 1
            day_exercise_seen.add(key)
        last_seen[name] = created_at

    matrix = np.array(rows)
    print(f"Collected {len(rows)} candidate feature rows across all scoreable events.\n")

    corr = np.corrcoef(matrix, rowvar=False)
    print(f"{'':<18}" + "".join(f"{k:>18}" for k in FEATURE_ORDER))
    for i, k in enumerate(FEATURE_ORDER):
        print(f"{k:<18}" + "".join(f"{corr[i][j]:>18.3f}" for j in range(len(FEATURE_ORDER))))

    print("\nStrongest correlations with recency:")
    recency_idx = FEATURE_ORDER.index("recency")
    others = [(k, corr[recency_idx][i]) for i, k in enumerate(FEATURE_ORDER) if k != "recency"]
    others.sort(key=lambda x: abs(x[1]), reverse=True)
    for k, v in others:
        print(f"  recency vs {k:<18} r={v:.3f}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python -m experiments.feature_correlation <email>")
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))
