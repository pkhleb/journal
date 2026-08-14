from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app import models
from app.predictor.features import get_exercise_candidates
from app.predictor.mixer import weight_candidates, apply_miss_only_update, DEFAULT_WEIGHTS

STALE_CUTOFF = timedelta(minutes=45)


async def _get_weights(db: AsyncSession, user_id: int) -> dict:
    """Return the current stored feature weights for a user.

    Args:
        db: Open database session.
        user_id: User ID whose model weights are requested.

    Returns:
        dict: Current feature weights or the default weights if unset.
    """
    result = await db.execute(
        select(models.ModelWeights).where(models.ModelWeights.user_id == user_id)
    )
    row = result.scalar_one_or_none()
    return row.weights if row else DEFAULT_WEIGHTS


async def predict(
    db: AsyncSession, user_id: int, last_exercise: str | None = None,
    now: datetime | None = None,
) -> list[str]:
    """Create a ranking of exercise candidates and store the prediction event.

    Args:
        db: Open database session.
        user_id: User ID to score candidates for.
        last_exercise: Optional last exercise used as a ranking signal.
        now: Optional timestamp used in tests for deterministic output.

    Returns:
        list[str]: Ranked exercise names.
    """
    candidates = await get_exercise_candidates(db, user_id, last_exercise, now)
    if not candidates:
        return []

    weights = await _get_weights(db, user_id)
    ranked_names = weight_candidates(candidates, weights)

    event = models.PredictionEvent(
        user_id=user_id,
        resolved=False,
        data={"candidates": candidates, "weights_snapshot": weights},
    )
    db.add(event)
    await db.commit()

    return ranked_names


async def resolve(db: AsyncSession, user_id: int, chosen_exercise: str) -> None:
    """Resolve the most recent prediction event with a user-selected exercise.

    Args:
        db: Open database session.
        user_id: User whose prediction event should be resolved.
        chosen_exercise: Exercise actually selected by the user.
    """
    result = await db.execute(
        select(models.PredictionEvent)
        .where(
            models.PredictionEvent.user_id == user_id,
            models.PredictionEvent.resolved == False,
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
