from fastapi import APIRouter, Depends
from sqlalchemy import select
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
    """Return the complete prediction event table for authenticated callers.

    ``current_user`` is intentionally only used to require authentication. The
    metrics endpoint is intended to expose the full prediction event dataset,
    rather than limiting results to the current user's events.
    """
    result = await db.execute(
        select(models.PredictionEvent).order_by(
            models.PredictionEvent.created_at.desc()
        )
    )
    return result.scalars().all()
