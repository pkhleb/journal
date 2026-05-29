from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app import models, schemas, auth

router = APIRouter(prefix="/api")

@router.get("/inventory", response_model=list[schemas.InventoryItemOut])
async def get_inventory(
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    result = await db.execute(
        select(models.InventoryItem)
        .where(models.InventoryItem.user_id == current_user.id)
        .order_by(models.InventoryItem.created_at.desc())
    )
    return result.scalars().all()

@router.post("/inventory", response_model=schemas.InventoryItemOut)
async def create_inventory_item(
    item: schemas.InventoryItemCreate,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    db_item = models.InventoryItem(
        user_id=current_user.id,
        name=item.name,
        items=item.items
    )
    db.add(db_item)
    await db.commit()
    await db.refresh(db_item)
    return db_item

@router.delete("/inventory/{item_id}")
async def delete_inventory_item(
    item_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    result = await db.execute(
        select(models.InventoryItem).where(
            models.InventoryItem.id == item_id,
            models.InventoryItem.user_id == current_user.id
        )
    )
    db_item = result.scalar_one_or_none()
    if not db_item:
        raise HTTPException(404, "Item not found")
    await db.delete(db_item)
    await db.commit()
    return {"ok": True}

@router.post("/inventory/{item_id}/consume")
async def consume_inventory_item(
    item_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    result = await db.execute(
        select(models.InventoryItem).where(
            models.InventoryItem.id == item_id,
            models.InventoryItem.user_id == current_user.id
        )
    )
    db_item = result.scalar_one_or_none()
    if not db_item:
        raise HTTPException(404, "Item not found")
    db_entry = models.Entry(
        user_id=current_user.id,
        metric_type="meal",
        metric_data={"items": db_item.items}
    )
    db.add(db_entry)
    await db.delete(db_item)
    await db.commit()
    return {"ok": True}
