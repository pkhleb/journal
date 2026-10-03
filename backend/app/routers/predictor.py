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
    """Return the current user's prediction event history.

    Scoped to ``current_user`` — prediction events contain another user's
    exercise history and choices, so this must never cross users.
    """
    result = await db.execute(
        select(models.PredictionEvent)
        .where(models.PredictionEvent.user_id == current_user.id)
        .order_by(models.PredictionEvent.created_at.desc())
    )
    return result.scalars().all()
