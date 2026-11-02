import asyncio
from datetime import datetime, timedelta, timezone
from time import perf_counter
from zoneinfo import ZoneInfo
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_

from app import models
from app.predictor.features import get_session_aggregates, build_candidates
from app.predictor.mixer import weight_candidates, apply_miss_only_update, DEFAULT_WEIGHTS
from app.predictor.config import FEATURE_ORDER, FEATURE_SIGNATURE, CONFIG_VERSION
from app.timeutil import DEFAULT_TZ

STALE_CUTOFF = timedelta(minutes=45)

# Reserved key inside the persisted weights JSON. Holds the FEATURE_SIGNATURE
# the weights were learned under; never part of the weights handed to the mixer
# or logged on events.

SIGNATURE_KEY = "_feature_signature"

# In-memory per-user cache of the expensive aggregate computation, keyed by
# user_id -> {"aggregates": ..., "day": date, "tz": zone key}. The zone is part
# of the key because the same instant is a different local day in different
# zones. Single-process assumption —
# fine for one backend replica; would need something like Redis if this ever
# runs multi-process/horizontally scaled.
_aggregate_cache: dict[int, dict] = {}

# Bumped by invalidate(). A recompute remembers the generation it started
# under and only caches its result if no invalidation happened meanwhile —
# otherwise a slow recompute finishing after invalidate() would re-cache
# stale data.
_cache_generation: dict[int, int] = {}

# Per-user locks serializing the "find open event, else insert" step in
# predict(), so concurrent keystroke requests can't each insert an open event.
# Same single-process assumption as the cache above.
_event_locks: dict[int, asyncio.Lock] = {}


def _event_lock(user_id: int) -> asyncio.Lock:
    lock = _event_locks.get(user_id)
    if lock is None:
        lock = _event_locks[user_id] = asyncio.Lock()
    return lock


async def _get_aggregates(db: AsyncSession, user_id: int, now: datetime, tz: ZoneInfo):
    today = now.astimezone(tz).date()
    cached = _aggregate_cache.get(user_id)
    if cached and cached["day"] == today and cached["tz"] == tz.key:
        return cached["aggregates"]

    generation = _cache_generation.get(user_id, 0)
    aggregates = await get_session_aggregates(db, user_id, now, tz=tz)
    if _cache_generation.get(user_id, 0) == generation:
        _aggregate_cache[user_id] = {"aggregates": aggregates, "day": today, "tz": tz.key}
    return aggregates


def invalidate(user_id: int):
    """Drop the user's cached aggregates. Call whenever their entry history
    changes (create, edit, delete)."""
    _cache_generation[user_id] = _cache_generation.get(user_id, 0) + 1
    _aggregate_cache.pop(user_id, None)


async def _get_weights(db: AsyncSession, user_id: int) -> dict:
    result = await db.execute(
        select(models.ModelWeights).where(models.ModelWeights.user_id == user_id)
    )
    row = result.scalar_one_or_none()
    # A row learned under a different feature seet (or written before the
    # signature existed) is ignored, not patched up: its legacy weights were
    # tuned without the newer features, so mixing in defaults for the missing
    # ones would serve a combination nobody validated. The row is replaced on
    # the user's next update.
    if row is None or row.weights.get(SIGNATURE_KEY) != FEATURE_SIGNATURE:
        return dict(DEFAULT_WEIGHTS)
    return {k: row.weights.get(k, DEFAULT_WEIGHTS[k]) for k in FEATURE_ORDER}


async def predict(
    db: AsyncSession, user_id: int, last_exercise: str | None = None,
    now: datetime | None = None, tz: ZoneInfo = DEFAULT_TZ,
) -> list[str]:
    """The one thing routers call to get a ranking. Reuses cached aggregates
    within the same day, and updates today's still-open prediction event in
    place rather than inserting a new row on every call — important since
    this can get hit once per keystroke from a search box."""
    started = perf_counter()
    now = now or datetime.now(timezone.utc)
    aggregates = await _get_aggregates(db, user_id, now, tz)
    # The client loses its in-memory last exercise on reload; default to the
    # latest exercise logged today so the transition signals still apply.
    if last_exercise is None and aggregates:
        last_exercise = aggregates.get("today_last_exercise")
    candidates = build_candidates(aggregates, last_exercise, now, tz=tz)
    if not candidates:
        return []

    weights = await _get_weights(db, user_id)
    ranked_names = weight_candidates(candidates, weights)
    latency_ms = (perf_counter() - started) * 1000

    async with _event_lock(user_id):
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
        event_data = {
            "event_type": "next_exercise_prediction",
            "last_exercise": last_exercise,
            "candidates": candidates,
            "ranked_exercises": ranked_names,
            "weights_snapshot": weights,
            "config_version": CONFIG_VERSION,
            "prediction_created_at": now.isoformat(),
        }

        if event and (now - event.created_at) <= STALE_CUTOFF:
            # Still-live prediction from moments ago (e.g. the previous
            # keystroke) — refresh it in place instead of adding a new row.
            event.data = event_data
            event.created_at = now
            event.latency_ms = latency_ms
        else:
            event = models.PredictionEvent(
                user_id=user_id,
                resolved=False,
                data=event_data,
                latency_ms=latency_ms,
            )
            db.add(event)

        await db.commit()

    return ranked_names


async def resolve(
    db: AsyncSession, user_id: int, chosen_exercise: str, entry_id: int | None = None,
) -> None:
    """Called after a set is actually logged. Always invalidates the cache
    first — a new entry changes transition/weekday/recency history for this
    user regardless of what happens below. entry_id is stored on the event so
    rescore() can find it if the entry is later deleted or renamed."""
    invalidate(user_id)

    async with _event_lock(user_id):
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

        now = datetime.now(timezone.utc)
        if now - event.created_at > STALE_CUTOFF:
            event.resolved = True
            event.resolved_at = now
            event.data = {**event.data, "chosen_exercise": chosen_exercise, "entry_id": entry_id, "stale": True}
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
            stored = {**new_weights, SIGNATURE_KEY: FEATURE_SIGNATURE}
            if weights_row:
                weights_row.weights = stored
            else:
                db.add(models.ModelWeights(user_id=user_id, weights=stored))

        event.resolved = True
        event.resolved_at = now
        event.data = {
            **event.data,
            "chosen_exercise": chosen_exercise,
            "entry_id": entry_id,
            "rank": info["rank"],
            "hit": info["hit"],
            "updated": info["updated"],
            "update_mode": "miss_only",
            "weights_before": weights_before,
            "weights_after": new_weights if info["updated"] else None,
        }
        await db.commit()


async def rescore(
    db: AsyncSession, user_id: int, entry_id: int, new_exercise: str | None = None,
) -> None:
    """Undo or redo what an entry taught the model after it was deleted
    (new_exercise=None) or renamed (new_exercise=the new name). Finds the
    prediction event scored against the entry; a deleted entry's event is
    dropped, a renamed one is re-scored against the new name. Then every later
    resolved event is replayed in order from the weights in force before it, so
    the learned weights and the replayed events' rank/hit/weights_before/after
    match the corrected history. Replay reuses each event's stored candidate
    snapshot (features as they were at prediction time).

    Does not commit — the caller commits together with the entry change. Events
    resolved before entry_id was recorded can't be matched and are left as is."""
    result = await db.execute(
        select(models.PredictionEvent).where(
            models.PredictionEvent.user_id == user_id,
            models.PredictionEvent.resolved == True,  # noqa: E712
            models.PredictionEvent.data["entry_id"].astext == str(entry_id),
        )
    )
    target = result.scalars().first()
    if target is None:
        return

    if new_exercise is None:
        await db.delete(target)
    else:
        target.data = {**target.data, "chosen_exercise": new_exercise}

    base = target.data.get("weights_before")
    if base is None:
        # Stale event: it never touched the weights, nothing to replay.
        return

    later_result = await db.execute(
        select(models.PredictionEvent)
        .where(
            models.PredictionEvent.user_id == user_id,
            models.PredictionEvent.resolved == True,  # noqa: E712
            or_(
                models.PredictionEvent.resolved_at > target.resolved_at,
                and_(
                    models.PredictionEvent.resolved_at == target.resolved_at,
                    models.PredictionEvent.id > target.id,
                ),
            ),
        )
        .order_by(models.PredictionEvent.resolved_at, models.PredictionEvent.id)
    )
    replay = list(later_result.scalars())
    if new_exercise is not None:
        replay.insert(0, target)

    weights = base
    for event in replay:
        data = event.data
        if data.get("stale") or "candidates" not in data:
            continue
        new_weights, info = apply_miss_only_update(
            data["candidates"], data["chosen_exercise"], weights, prior_weights=DEFAULT_WEIGHTS
        )
        event.data = {
            **data,
            "rank": info["rank"],
            "hit": info["hit"],
            "updated": info["updated"],
            "weights_before": weights,
            "weights_after": new_weights if info["updated"] else None,
        }
        if info["updated"]:
            weights = new_weights

    row_result = await db.execute(
        select(models.ModelWeights).where(models.ModelWeights.user_id == user_id)
    )
    row = row_result.scalar_one_or_none()
    stored = {**weights, SIGNATURE_KEY: FEATURE_SIGNATURE}
    if row:
        row.weights = stored
    elif weights != dict(DEFAULT_WEIGHTS):
        db.add(models.ModelWeights(user_id=user_id, weights=stored))
