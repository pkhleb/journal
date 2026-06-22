from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app import models, schemas, auth
from fastapi.responses import JSONResponse
import json
from datetime import date

router = APIRouter(prefix="/api")

@router.get("/entries", response_model=list[schemas.EntryOut])
async def get_entries(
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
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
    current_user: models.User = Depends(auth.get_current_user)
):
    if not entry.prose and not entry.metric_type:
        raise HTTPException(400, "Entry must have prose or a metric")
    db_entry = models.Entry(
        user_id=current_user.id,
        prose=entry.prose,
        metric_type=entry.metric_type,
        metric_data=entry.metric_data
    )
    db.add(db_entry)
    await db.commit()
    await db.refresh(db_entry)
    return db_entry

@router.patch("/entries/{entry_id}")
async def update_entry(
    entry_id: int,
    entry: schemas.EntryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    result = await db.execute(
        select(models.Entry).where(
            models.Entry.id == entry_id,
            models.Entry.user_id == current_user.id
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
    current_user: models.User = Depends(auth.get_current_user)
):
    result = await db.execute(
        select(models.Entry).where(
            models.Entry.id == entry_id,
            models.Entry.user_id == current_user.id
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
    current_user: models.User = Depends(auth.get_current_user)
):
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
            "Content-Disposition": f"attachment; filename=journal-export-{date.today().isoformat()}.json"
        }
    )
