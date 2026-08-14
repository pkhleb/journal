from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app import models
from app.predictor.features import get_session_aggregates, build_candidates
from app.predictor.mixer import weight_candidates, apply_miss_only_update, DEFAULT_WEIGHTS

LOCAL_TZ = ZoneInfo("America/New_York")
STALE_CUTOFF = timedelta(minutes=45)

# In-memory per-user cache of the expensive aggregate computation, keyed by
# user_id -> {"aggregates": ..., "day": date}. Single-process assumption —
# fine for one backend replica; would need something like Redis if this ever
# runs multi-process/horizontally scaled.
_aggregate_cache: dict[int, dict] = {}


async def _get_aggregates(db: AsyncSession, user_id: int, now: datetime):
    today = now.astimezone(LOCAL_TZ).date()
    cached = _aggregate_cache.get(user_id)
    if cached and cached["day"] == today:
        return cached["aggregates"]

    aggregates = await get_session_aggregates(db, user_id, now)
    _aggregate_cache[user_id] = {"aggregates": aggregates, "day": today}
    return aggregates


def _invalidate_cache(user_id: int):
    _aggregate_cache.pop(user_id, None)


async def _get_weights(db: AsyncSession, user_id: int) -> dict:
    result = await db.execute(
        select(models.ModelWeights).where(models.ModelWeights.user_id == user_id)
    )
    row = result.scalar_one_or_none()
    return row.weights if row else DEFAULT_WEIGHTS


async def predict(
    db: AsyncSession, user_id: int, last_exercise: str | None = None,
    now: datetime | None = None,
) -> list[str]:
    """The one thing routers call to get a ranking. Reuses cached aggregates
    within the same day, and updates today's still-open prediction event in
    place rather than inserting a new row on every call — important since
    this can get hit once per keystroke from a search box."""
    now = now or datetime.now(timezone.utc)
    aggregates = await _get_aggregates(db, user_id, now)
    candidates = build_candidates(aggregates, last_exercise, now)
    if not candidates:
        return []

    weights = await _get_weights(db, user_id)
    ranked_names = weight_candidates(candidates, weights)

    result = await db.execute(
        select(models.PredictionEvent)
        .where(
            models.PredictionEvent.user_id == user_id,
            models.PredictionEvent.resolved == False,  # noqa: E712
        )
        .order_by(models.PredictionEvent.created_at.desc())
        .limit(1)
    )
    event = result.scalar_one_or_none()
    event_data = {"candidates": candidates, "weights_snapshot": weights}

    if event and (now - event.created_at) <= STALE_CUTOFF:
        # Still-live prediction from moments ago (e.g. the previous
        # keystroke) — refresh it in place instead of adding a new row.
        event.data = event_data
        event.created_at = now
    else:
        event = models.PredictionEvent(user_id=user_id, resolved=False, data=event_data)
        db.add(event)

    await db.commit()
    return ranked_names


async def resolve(db: AsyncSession, user_id: int, chosen_exercise: str) -> None:
    """Called after a set is actually logged. Always invalidates the cache
    first — a new entry changes transition/weekday/recency history for this
    user regardless of what happens below."""
    _invalidate_cache(user_id)

    result = await db.execute(
        select(models.PredictionEvent)
        .where(
            models.PredictionEvent.user_id == user_id,
            models.PredictionEvent.resolved == False,  # noqa: E712
        )
        .order_by(models.PredictionEvent.created_at.desc())
        .limit(1)
    )
    event = result.scalar_one_or_none()
    if event is None:
        return

    if datetime.now(timezone.utc) - event.created_at > STALE_CUTOFF:
        event.resolved = True
        event.resolved_at = datetime.now(timezone.utc)
        event.data = {**event.data, "chosen_exercise": chosen_exercise, "stale": True}
        await db.commit()
        return

    candidates = event.data["candidates"]
    weights_before = event.data["weights_snapshot"]

    weights_row_result = await db.execute(
        select(models.ModelWeights).where(models.ModelWeights.user_id == user_id)
    )
    weights_row = weights_row_result.scalar_one_or_none()

    new_weights, info = apply_miss_only_update(
        candidates, chosen_exercise, weights_before, prior_weights=DEFAULT_WEIGHTS
    )

    if info["updated"]:
        if weights_row:
            weights_row.weights = new_weights
        else:
            db.add(models.ModelWeights(user_id=user_id, weights=new_weights))

    event.resolved = True
    event.resolved_at = datetime.now(timezone.utc)
    event.data = {
        **event.data,
        "chosen_exercise": chosen_exercise,
        "rank": info["rank"],
        "hit": info["hit"],
        "updated": info["updated"],
        "update_mode": "miss_only",
        "weights_before": weights_before,
        "weights_after": new_weights if info["updated"] else None,
    }
    await db.commit()
