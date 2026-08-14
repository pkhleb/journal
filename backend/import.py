import asyncio, json, sys
from datetime import datetime
from app.database import AsyncSessionLocal
from app.models import User, Entry, InventoryItem
from app.auth import hash_password


async def main(export_path: str):
    """Import a journal export JSON file into a local database.

    Args:
        export_path: Path to the exported JSON file to import.
    """
    with open(export_path) as f:
        data = json.load(f)

    async with AsyncSessionLocal() as db:
        user = User(
            email="test@local.dev",
            username=data["user"],
            hashed_password=hash_password("testpassword123"),
            is_verified=True,
        )
        db.add(user)
        await db.flush()

        for e in data["entries"]:
            db.add(Entry(
                user_id=user.id,
                prose=e["prose"],
                metric_type=e["metric_type"],
                metric_data=e["metric_data"],
                created_at=datetime.fromisoformat(e["created_at"]),
            ))

        for i in data["inventory"]:
            db.add(InventoryItem(
                user_id=user.id,
                name=i["name"],
                items=i["items"],
                created_at=datetime.fromisoformat(i["created_at"]),
            ))

        await db.commit()
        print(f"Imported {len(data['entries'])} entries, {len(data['inventory'])} inventory items as user_id={user.id}")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1]))
