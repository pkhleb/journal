from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app import models, schemas, auth
from fastapi.responses import JSONResponse
import json
from datetime import date
from app.predictor import service as predictor

router = APIRouter(prefix="/api")


@router.get("/entries", response_model=list[schemas.EntryOut])
async def get_entries(
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Fetch all journal entries for the authenticated user.

    Args:
        db: Open database session.
        current_user: Authenticated user record.

    Returns:
        list[models.Entry]: Journal entries ordered newest first.
    """
    result = await db.execute(
        select(models.Entry)
        .where(models.Entry.user_id == current_user.id)
        .order_by(models.Entry.created_at.desc())
    )
    return result.scalars().all()


@router.post("/entries", response_model=schemas.EntryOut)
async def create_entry(
    entry: schemas.EntryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Create a new journal entry and resolve any related exercise prediction.

    Args:
        entry: Submitted entry payload.
        db: Open database session.
        current_user: Authenticated user record.

    Raises:
        HTTPException: If the payload does not include prose or a metric.

    Returns:
        models.Entry: The created journal entry.
    """
    if not entry.prose and not entry.metric_type:
        raise HTTPException(400, "Entry must have prose or a metric")
    db_entry = models.Entry(
        user_id=current_user.id,
        prose=entry.prose,
        metric_type=entry.metric_type,
        metric_data=entry.metric_data,
    )
    db.add(db_entry)
    await db.commit()
    await db.refresh(db_entry)
    if entry.metric_type == "exercise":
        name = (entry.metric_data or {}).get("name")
        if name:
            await predictor.resolve(db, current_user.id, chosen_exercise=name)
    return db_entry


@router.patch("/entries/{entry_id}")
async def update_entry(
    entry_id: int,
    entry: schemas.EntryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Update an existing journal entry owned by the current user.

    Args:
        entry_id: Numeric ID of the entry to update.
        entry: Updated entry payload.
        db: Open database session.
        current_user: Authenticated user record.

    Raises:
        HTTPException: If the entry is not found.

    Returns:
        dict: A confirmation payload with ok=True.
    """
    result = await db.execute(
        select(models.Entry).where(
            models.Entry.id == entry_id,
            models.Entry.user_id == current_user.id,
        )
    )
    db_entry = result.scalar_one_or_none()
    if not db_entry:
        raise HTTPException(404, "Entry not found")
    db_entry.prose = entry.prose
    db_entry.metric_type = entry.metric_type
    db_entry.metric_data = entry.metric_data
    await db.commit()
    return {"ok": True}


@router.delete("/entries/{entry_id}")
async def delete_entry(
    entry_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Delete a journal entry owned by the current user.

    Args:
        entry_id: Numeric ID of the entry to delete.
        db: Open database session.
        current_user: Authenticated user record.

    Raises:
        HTTPException: If the entry is not found.

    Returns:
        dict: A confirmation payload with ok=True.
    """
    result = await db.execute(
        select(models.Entry).where(
            models.Entry.id == entry_id,
            models.Entry.user_id == current_user.id,
        )
    )
    db_entry = result.scalar_one_or_none()
    if not db_entry:
        raise HTTPException(404, "Entry not found")
    await db.delete(db_entry)
    await db.commit()
    return {"ok": True}


@router.get("/export/db")
async def export_db(
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Export a user's journal data as a JSON file attachment.

    Args:
        db: Open database session.
        current_user: Authenticated user record.

    Returns:
        JSONResponse: Downloadable JSON payload with entries and inventory data.
    """
    entries_result = await db.execute(
        select(models.Entry)
        .where(models.Entry.user_id == current_user.id)
        .order_by(models.Entry.created_at.asc())
    )
    entries = entries_result.scalars().all()

    inventory_result = await db.execute(
        select(models.InventoryItem)
        .where(models.InventoryItem.user_id == current_user.id)
        .order_by(models.InventoryItem.created_at.asc())
    )
    inventory = inventory_result.scalars().all()

    payload = {
        "exported_at": date.today().isoformat(),
        "user": current_user.username,
        "entries": [
            {
                "id": e.id,
                "prose": e.prose,
                "metric_type": e.metric_type,
                "metric_data": e.metric_data,
                "created_at": e.created_at.isoformat(),
            }
            for e in entries
        ],
        "inventory": [
            {
                "id": i.id,
                "name": i.name,
                "items": i.items,
                "created_at": i.created_at.isoformat(),
            }
            for i in inventory
        ],
    }
    return JSONResponse(
        content=payload,
        headers={
            "Content-Disposition": f"attachment; filename=journal-export-{date.today().isoformat()}.json",
        },
    )


@router.get("/exercises/ranked")
async def get_ranked_exercises(
    last_exercise: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Fetch a ranked list of exercise suggestions for the authenticated user.

    Args:
        last_exercise: Optional last exercise used as a context signal.
        db: Open database session.
        current_user: Authenticated user record.

    Returns:
        list[str]: Ranked exercise names ordered by the predictor score.
    """
    return await predictor.predict(db, current_user.id, last_exercise)
