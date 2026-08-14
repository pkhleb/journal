from collections import defaultdict
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import math
from app.models import Entry

LOCAL_TZ = ZoneInfo("America/New_York")


async def get_session_aggregates(db: AsyncSession, user_id: int, now: datetime | None = None) -> dict | None:
    """The expensive part: one query over the user's whole exercise history
    plus O(n) aggregation. Deliberately does NOT take last_exercise — that's
    the part that changes on every keystroke of a search box, and none of
    what's computed here depends on it. This is what predictor/service.py
    caches per (user, day)."""
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

    weekday_counts: dict = defaultdict(lambda: defaultdict(int))
    for day, day_exercises in raw_sessions.items():
        wd = day.weekday()
        for name in set(day_exercises):
            weekday_counts[wd][name] += 1

    last_seen = {}
    for e in entries:
        name = e.metric_data.get("name")
        if name:
            last_seen[name] = e.created_at

    return {
        "transition_counts": transition_counts,
        "weekday_counts": weekday_counts,
        "last_seen": last_seen,
    }


def build_candidates(
    aggregates: dict | None, last_exercise: str | None = None, now: datetime | None = None,
) -> list[dict]:
    """The cheap part: pure in-memory math from already-computed aggregates.
    No DB access — safe to call on every keystroke. This is where
    last_exercise actually matters (the transition signal)."""
    if aggregates is None:
        return []

    now = now or datetime.now(timezone.utc)
    today_wd = now.astimezone(LOCAL_TZ).weekday()

    transition_counts = aggregates["transition_counts"]
    weekday_counts = aggregates["weekday_counts"]
    last_seen = aggregates["last_seen"]

    total_today = sum(weekday_counts[today_wd].values())
    transition_total = (
        sum(transition_counts[last_exercise].values()) if last_exercise else 0
    )

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
        days_since = (now - last_seen[name]).days
        recency_score = math.exp(-days_since / 21)  # ~3 week half-life

        candidates.append({
            "exercise": name,
            "features": {
                "transition": transition_score,
                "weekday": weekday_score,
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
