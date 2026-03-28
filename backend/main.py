from fastapi import FastAPI, HTTPException, APIRouter
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import aiosqlite, json, os
from datetime import datetime

app = FastAPI()
router = APIRouter(prefix="/api")
DB = "journal.db"

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

class Entry(BaseModel):
    prose: Optional[str] = None
    metric_type: Optional[str] = None
    metric_data: Optional[dict] = None

@router.patch("/entries/{entry_id}")
async def update_entry(entry_id: int, entry: Entry):
    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "UPDATE entries SET prose=?, metric_type=?, metric_data=?, WHERE id=?",
            (entry.prose, entry.metric_type, json.dumps(entry.metric_data) if entry.metric_data else None, entry_id)
        )
        await db.commit()
    return {"ok": True}

@app.on_event("startup")
async def init_db():
    async with aiosqlite.connect(DB) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                prose TEXT,
                metric_type TEXT,
                metric_data TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        await db.commit()

@router.get("/entries")
async def get_entries():
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM entries ORDER BY created_at DESC") as cur:
            rows = await cur.fetchall()
    result = []
    for r in rows:
        row = dict(r)
        row['metric_data'] = json.loads(row['metric_data']) if row['metric_data'] else None
        result.append(row)
    return result

from fastapi.responses import FileResponse

@router.get("/export/db")
async def export_db():
    if not os.path.exists(DB):
        raise HTTPException(404, "Database not found")
    return FileResponse(
        path=DB,
        media_type="application/octet-stream",
        filename="journal.db"
    )

@router.post("/entries")
async def create_entry(entry: Entry):
    if not entry.prose and not entry.metric_type:
        raise HTTPException(400, "Entry must have prose or a metric")
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute(
            "INSERT INTO entries (prose, metric_type, metric_data) VALUES (?, ?, ?)",
            (entry.prose, entry.metric_type, json.dumps(entry.metric_data) if entry.metric_data else None)
        )
        await db.commit()
        return {"id": cur.lastrowid}

@router.delete("/entries/{entry_id}")
async def delete_entry(entry_id: int):
    async with aiosqlite.connect(DB) as db:
        await db.execute("DELETE FROM entries WHERE id = ?", (entry_id,))
        await db.commit()
    return {"ok": True}


class InventoryItem(BaseModel):
    name: str
    items: list[dict]

@router.get("/inventory")
async def get_inventory():
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM inventory ORDER BY created_at DESC") as cur:
            rows = await cur.fetchall()
    result = []
    for r in rows:
        row = dict(r)
        row['items'] = json.loads(row['items'])
        result.append(row)
    return result

@router.post("/inventory")
async def create_inventory_item(item: InventoryItem):
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute(
            "INSERT INTO inventory (name, items) VALUES (?, ?)",
            (item.name, json.dumps(item.items))
        )
        await db.commit()
        return {"id": cur.lastrowid}

@router.delete("/inventory/{item_id}")
async def delete_inventory_item(item_id: int):
    async with aiosqlite.connect(DB) as db:
        await db.execute("DELETE FROM inventory WHERE id = ?", (item_id,))
        await db.commit()
    return {"ok": True}

@router.post("/inventory/{item_id}/consume")
async def consume_inventory_item(item_id: int):
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM inventory WHERE id = ?", (item_id,)) as cur:
            row = await cur.fetchone()
        if not row:
            raise HTTPException(404, "Inventory item not found")
        row = dict(row)
        items = json.loads(row['items'])
        await db.execute(
            "INSERT INTO entries (prose, metric_type, metric_data) VALUES (?, ?, ?)",
            (None, 'meal', json.dumps({"items": items}))
        )
        await db.commit()
    return {"ok": True}

app.include_router(router)
app.mount("/", StaticFiles(directory="static", html=True), name="static")
