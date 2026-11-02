from fastapi import APIRouter, Depends
from sqlalchemy import Text, cast, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import auth, models, schemas
from app.database import get_db


router = APIRouter(prefix="/api")


@router.get(
    "/predictor/metrics",
    response_model=list[schemas.PredictionEventOut],
)
async def get_prediction_metrics(
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Return the current user's prediction event history.

    Scoped to ``current_user`` — prediction events contain another user's
    exercise history and choices, so this must never cross users.

    ``data.candidates`` (the full per-candidate feature vectors) is dropped in
    SQL (``jsonb - 'candidates'``), so it never leaves the database. It
    dominates row size and the dashboard doesn't use it; rescoring reads it
    straight from the table.
    """
    pe = models.PredictionEvent
    result = await db.execute(
        select(
            pe.id,
            pe.user_id,
            pe.created_at,
            pe.resolved,
            pe.resolved_at,
            pe.data.op("-")(cast("candidates", Text)).label("data"),
            pe.latency_ms,
        )
        .where(models.PredictionEvent.user_id == current_user.id)
        .order_by(models.PredictionEvent.created_at.desc())
    )
    return result.all()
