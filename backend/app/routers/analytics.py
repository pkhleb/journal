from collections import defaultdict
from datetime import datetime, timezone, date
from zoneinfo import ZoneInfo
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import math
from app.models import Entry

LOCAL_TZ = ZoneInfo("America/New_York")

async def get_exercise_rankings(
    db: AsyncSession, user_id: int) -> list[str]:
    result = await db.execute(
        select(Entry)
        .where(Entry.user_id == user_id, Entry.metric_type == "exercise")
        .order_by(Entry.created_at.asc())
    )
    entries = result.scalars().all()
    if not entries:
        return []

    now = datetime.now(timezone.utc)
    today = now.astimezone(LOCAL_TZ).date()
    today_wd = today.weekday()

    raw_sessions: dict = defaultdict(list)
    daily_exercise_sets: dict = defaultdict(set)
    session_set_counts: dict = defaultdict(lambda: defaultdict(int))
    current_counts: dict = defaultdict(int)

    for e in entries:
        local_dt = e.created_at.astimezone(LOCAL_TZ)
        day = local_dt.date()
        name=  e.metric_data.get("name")
        if not name:
           continue
        session_set_counts[name][day] += 1
        raw_sessions[day].append(name)
        daily_exercise_sets[day].add(name)
        if day == today:
           current_counts[name] += 1

    last_exercise = raw_sessions[today][-1] if raw_sessions.get(today) else None



    # Bigram transition counts: prev -> {next: count}
    transition_counts: dict = defaultdict(lambda: defaultdict(int))
    for day_exercises in raw_sessions.values():
        for prev, nxt in zip(day_exercises, day_exercises[1:]):
            transition_counts[prev][nxt] += 1

    # Trigram transition counts: p2, p1 -> {next: count}
    tri_transition_counts: dict = defaultdict(lambda: defaultdict(int))
    for day_exercises in raw_sessions.values():
        for p2, p1, nxt in zip(day_exercises, day_exercises[1:], day_exercises[2:]):
            tri_transition_counts[(p2,p1)][nxt] +=1

    # find average count for each exercise across all sessions
    avg_sets: dict = {}
    for name, day_counts in session_set_counts.items():
        avg_sets[name] = sum(day_counts.values()) / len(day_counts)

    # Weekday frequency: weekday -> {name: count}, once per day per exercise
    weekday_counts: dict = defaultdict(lambda: defaultdict(int))
    for day, names in daily_exercise_sets.items():
        wd = day.weekday()
        for name in names:
            weekday_counts[wd][name] += 1

    # Last-seen timestamp per exercise (entries are asc, so this lands on latest)
    last_seen = {}
    for e in entries:
        name = e.metric_data.get("name")
        if name:
            last_seen[name] = e.created_at

    avg_sets: dict = {}
    for name, day_counts in session_set_counts.items():
        avg_sets[name] = sum(day_counts.values()) / len(day_counts)

    total_today = sum(weekday_counts[today_wd].values())
    transition_total = (
        sum(transition_counts[last_exercise].values()) if last_exercise else 0
    )
    tri_transition_total = (
        sum(tri_transition_counts[last_exercise].values()) if last_exercise else 0
    )

    scores = {}
    for name in last_seen:
        transition_score = (
            transition_counts[last_exercise].get(name, 0) / transition_total
            if transition_total else 0.0
        )
        long_transition_score = (
            transition_counts[last_exercise].get(name, 0) / tri_transition_total
            if tri_transition_total else 0.0
        )
        weekday_score = (
            weekday_counts[today_wd].get(name, 0) / total_today
            if total_today else 0.0
        )
        days_since = (now - last_seen[name]).days
        recency_score = math.exp(-days_since / 21) # ~3 week half-life
        print(current_counts)
        current = current_counts.get(name,0)
        avg=avg_sets.get(name,1)
        print(name)
        print(current,avg)
        saturation_score = max(0.0, 1-(current/avg))
        print(transition_score, long_transition_score, saturation_score) 

        scores[name] = (
            0.4 * transition_score
            + 0.25 * long_transition_score
            + 0.0 * weekday_score
            + 0.1 * recency_score
            + 0.25 * saturation_score
        )
    print("~~~~~~~~~~~~~~~~~~~~~")
    print(scores)
    print("~~~~~~~~~~~~~~~~~~~~~")
    return [name for name, _ in sorted(scores.items(), key=lambda x: x[1], reverse = True)]


