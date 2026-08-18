from collections import defaultdict
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import math
from app.models import Entry
from app.predictor.config import PHASE_CUTOFF, MIN_PHASE_SUPPORT

LOCAL_TZ = ZoneInfo("America/New_York")

async def get_session_aggregates(
    db: AsyncSession, user_id: int, now: datetime | None = None,
    phase_cutoff: int = PHASE_CUTOFF,
) -> dict | None:
    """The expensive part: one query over the user's whole exercise history
    plus O(n) aggregation. Deliberately does NOT take last_exercise — that's
    the part that changes on every keystroke of a search box, and none of
    what's computed here depends on it. This is what predictor/service.py
    caches per (user, day).

    phase_cutoff is threaded through as a parameter (default PHASE_CUTOFF)
    rather than hardcoded, so experiments/phase_sweep.py can try different
    values without editing this file between runs."""
    result = await db.execute(
        select(Entry)
        .where(Entry.user_id == user_id, Entry.metric_type == "exercise")
        .order_by(Entry.created_at.asc())
    )
    entries = result.scalars().all()
    if not entries:
        return None

    raw_sessions: dict = defaultdict(list)
    for e in entries:
        local_dt = e.created_at.astimezone(LOCAL_TZ)
        day = local_dt.date()
        name = e.metric_data.get("name")
        if not name:
            continue
        raw_sessions[day].append(name)

    transition_counts: dict = defaultdict(lambda: defaultdict(int))
    for day_exercises in raw_sessions.values():
        for prev, nxt in zip(day_exercises, day_exercises[1:]):
            transition_counts[prev][nxt] += 1

    # Phase-bucketed transitions: k = how many sets were already logged
    # today (including prev) before nxt was logged. This must exactly
    # match how "today_session_length" is interpreted at prediction time
    # in build_candidates — same k, same phase_cutoff, means same bucket.
    phase_transition_counts = {
        "early": defaultdict(lambda: defaultdict(int)),
        "late": defaultdict(lambda: defaultdict(int)),
    }
    for day_exercises in raw_sessions.values():
        for i, (prev, nxt) in enumerate(zip(day_exercises, day_exercises[1:])):
            k = i + 1
            phase = "early" if k < phase_cutoff else "late"
            phase_transition_counts[phase][prev][nxt] += 1

    weekday_counts: dict = defaultdict(lambda: defaultdict(int))
    for day, day_exercises in raw_sessions.items():
        wd = day.weekday()
        for name in set(day_exercises):
            weekday_counts[wd][name] += 1

    # Marginal frequency of which exercise shows up at exact session
    # position i (0-indexed: i=0 is the day's first set, i=1 the second,
    # etc.) — unconditional on what came before, unlike transition/phase.
    # Each day contributes exactly one exercise per position it reaches, so
    # no "distinct per day" dedup is needed the way weekday_counts needs it.
    position_counts: dict = defaultdict(lambda: defaultdict(int))
    for day_exercises in raw_sessions.values():
        for i, name in enumerate(day_exercises):
            position_counts[i][name] += 1

    # Session precedence: for each pair (e1, e2), how many DISTINCT SESSIONS
    # had e2 show up anywhere after e1's first occurrence — presence only,
    # not count, and any distance apart (not just immediately next, unlike
    # transition_counts). This is a coarser, distance-independent ordering
    # signal that stays informative even when a session's exact set order
    # is irregular from day to day.
    session_precedence_counts: dict = defaultdict(lambda: defaultdict(int))
    for day_exercises in raw_sessions.values():
        seen_order = []
        seen_set = set()
        for name in day_exercises:
            if name not in seen_set:
                seen_set.add(name)
                seen_order.append(name)
        for i in range(len(seen_order)):
            for j in range(i + 1, len(seen_order)):
                session_precedence_counts[seen_order[i]][seen_order[j]] += 1

    last_seen = {}
    for e in entries:
        name = e.metric_data.get("name")
        if name:
            last_seen[name] = e.created_at

    now = now or datetime.now(timezone.utc)
    today = now.astimezone(LOCAL_TZ).date()
    today_session_length = len(raw_sessions.get(today, []))
    today_exercises_so_far = set(raw_sessions.get(today, []))

    return {
        "transition_counts": transition_counts,
        "phase_transition_counts": phase_transition_counts,
        "weekday_counts": weekday_counts,
        "position_counts": position_counts,
        "session_precedence_counts": session_precedence_counts,
        "last_seen": last_seen,
        "today_session_length": today_session_length,
        "today_exercises_so_far": today_exercises_so_far,
        "phase_cutoff": phase_cutoff,
    }


def build_candidates(
    aggregates: dict | None, last_exercise: str | None = None, now: datetime | None = None,
    min_phase_support: int = MIN_PHASE_SUPPORT,
) -> list[dict]:
    """The cheap part: pure in-memory math from already-computed aggregates.
    No DB access — safe to call on every keystroke. This is where
    last_exercise actually matters (the transition signals).

    min_phase_support is also a parameter (default MIN_PHASE_SUPPORT) for
    the same sweepability reason as phase_cutoff. phase_cutoff itself isn't
    a parameter here — it's baked into aggregates["phase_transition_counts"]
    already, read back via aggregates["phase_cutoff"] for consistency."""
    if aggregates is None:
        return []

    now = now or datetime.now(timezone.utc)
    today_wd = now.astimezone(LOCAL_TZ).weekday()

    transition_counts = aggregates["transition_counts"]
    phase_transition_counts = aggregates.get("phase_transition_counts", {"early": {}, "late": {}})
    weekday_counts = aggregates["weekday_counts"]
    position_counts = aggregates.get("position_counts", {})
    session_precedence_counts = aggregates.get("session_precedence_counts", {})
    today_exercises_so_far = aggregates.get("today_exercises_so_far", set())
    last_seen = aggregates["last_seen"]
    session_len = aggregates.get("today_session_length", 0)
    phase_cutoff = aggregates.get("phase_cutoff", PHASE_CUTOFF)
    current_phase = "early" if session_len < phase_cutoff else "late"

    total_today = sum(weekday_counts[today_wd].values())
    transition_total = (
        sum(transition_counts[last_exercise].values()) if last_exercise else 0
    )

    # session_len IS the position index of the set about to be logged
    # (0-indexed: session_len=0 means this is the day's first set).
    position_at_counts = position_counts.get(session_len, {})
    position_total = sum(position_at_counts.values())

    phase_prev_counts = (
        phase_transition_counts.get(current_phase, {}).get(last_exercise, {})
        if last_exercise else {}
    )
    phase_total = sum(phase_prev_counts.values())
    phase_has_support = phase_total >= min_phase_support

    # For each candidate, sum session_precedence_counts[e][candidate] across
    # every exercise e already done today — "how often has this candidate
    # eventually followed any exercise I've already done today, in any
    # session, at any distance." Normalized across candidates afterward.
    raw_precedence = {
        name: sum(session_precedence_counts.get(e, {}).get(name, 0) for e in today_exercises_so_far)
        for name in last_seen
    }
    precedence_total = sum(raw_precedence.values())

    candidates = []
    for name in last_seen:
        transition_score = (
            transition_counts[last_exercise].get(name, 0) / transition_total
            if transition_total else 0.0
        )
        weekday_score = (
            weekday_counts[today_wd].get(name, 0) / total_today
            if total_today else 0.0
        )
        position_score = (
            position_at_counts.get(name, 0) / position_total
            if position_total else 0.0
        )
        precedence_score = (
            raw_precedence.get(name, 0) / precedence_total
            if precedence_total else 0.0
        )
        days_since = (now - last_seen[name]).days
        recency_score = math.exp(-days_since / 21)  # ~3 week half-life

        # Phase-specific transition probability when there's enough support
        # for this (phase, last_exercise) pair; otherwise fall back to the
        # global transition score computed above — same score, no new
        # signal, so the phase feature is a no-op rather than noise when
        # data is sparse.
        if phase_has_support:
            phase_transition_score = phase_prev_counts.get(name, 0) / phase_total
        else:
            phase_transition_score = transition_score

        candidates.append({
            "exercise": name,
            "features": {
                "transition": transition_score,
                "phase_transition": phase_transition_score,
                "weekday": weekday_score,
                "position_freq": position_score,
                "session_precedence": precedence_score,
                "recency": recency_score,
            },
        })

    return candidates


async def get_exercise_candidates(
    db: AsyncSession, user_id: int, last_exercise: str | None = None,
    now: datetime | None = None,
) -> list[dict]:
    """One-shot convenience wrapper — still what check_rankings.py and the
    tests call directly. The cached path in predictor/service.py calls
    get_session_aggregates + build_candidates separately instead, so it can
    reuse aggregates across many calls with different last_exercise."""
    aggregates = await get_session_aggregates(db, user_id, now)
    return build_candidates(aggregates, last_exercise, now)
