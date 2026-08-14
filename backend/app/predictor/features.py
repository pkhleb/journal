from collections import defaultdict
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import math
from app.models import Entry

LOCAL_TZ = ZoneInfo("America/New_York")

async def get_exercise_candidates(
    db: AsyncSession, user_id: int, last_exercise: str | None = None,
    now: datetime | None = None,
) -> list[dict]:
    """Per-exercise feature vectors, unweighted.

    Each item: {"exercise": name, "features": {"transition": float, "weekday": float, "recency": float}}
    """
    result = await db.execute(
        select(Entry)
        .where(Entry.user_id == user_id, Entry.metric_type == "exercise")
        .order_by(Entry.created_at.asc())
    )
    entries = result.scalars().all()
    if not entries:
        return []

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

    now = now or datetime.now(timezone.utc)
    today_wd = now.astimezone(LOCAL_TZ).weekday()
    total_today = sum(weekday_counts[today_wd].values())
    transition_total = (
        sum(transition_counts[last_exercise].values()) if last_exercise else 0
    )

    candidates = []
    for name in last_seen:
        transition_score = (
            transition_counts[last_exercise].get(name, 0) /  transition_total
            if transition_total else 0.0
        )
        weekday_score = (
            weekday_counts[today_wd].get(name, 0) / total_today
            if total_today else 0.0
        )
        days_since = (now - last_seen[name]).days
        recency_score = math.exp(-days_since / 21)

        candidates.append({
            "exercise": name,
            "features": {
                "transition": transition_score,
                "weekday": weekday_score,
                "recency": recency_score,
            },
        })

    return candidates
