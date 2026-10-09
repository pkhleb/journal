from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import auth, models, schemas
from app.database import get_db


router = APIRouter(prefix="/api")


def _next_period(d: date, period: str) -> date:
    if period == "week":
        return d + timedelta(days=7)
    return date(d.year + (d.month == 12), d.month % 12 + 1, 1)


@router.get(
    "/activity",
    response_model=list[schemas.ActivityBucket],
)
async def get_activity(
    period: Literal["week", "month"] = Query("week"),
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(auth.require_admin),
):
    """Return site-wide posting activity (admin only) bucketed by week or month.

    Each bucket holds the number of entries created and the number of
    distinct users who created them. Only aggregate counts are returned —
    no per-user data.
    Buckets with no activity between the first and last are zero-filled so
    charts show gaps rather than skipping them. Weeks start on Monday (UTC).
    """
    bucket = func.date_trunc(period, func.timezone("UTC", models.Entry.created_at))
    result = await db.execute(
        select(
            bucket.label("period_start"),
            func.count(models.Entry.id),
            func.count(func.distinct(models.Entry.user_id)),
        )
        .group_by(bucket)
        .order_by(bucket)
    )
    rows = {r[0].date(): (r[1], r[2]) for r in result.all()}
    if not rows:
        return []

    buckets = []
    d, last = min(rows), max(rows)
    while d <= last:
        posts, users = rows.get(d, (0, 0))
        buckets.append(schemas.ActivityBucket(period_start=d, posts=posts, users=users))
        d = _next_period(d, period)
    return buckets
