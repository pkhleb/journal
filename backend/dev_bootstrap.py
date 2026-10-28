"""Prepare the local development database, then exit.

Run by entrypoint.dev.sh on every `docker compose up`. Safe to re-run.

The baseline Alembic migration is an empty stamp of a pre-existing schema, so
`alembic upgrade head` fails on a brand-new database. This script handles both
cases:

  * Fresh database: create all tables from the models, then `alembic stamp head`.
  * Existing database: `alembic upgrade head` to apply any new migrations.

It then seeds a verified dev user (email verification needs a Resend key, so
registering a user locally is otherwise a dead end).
"""
import asyncio

from alembic import command
from alembic.config import Config
from sqlalchemy import select, text

from app import models
from app.auth import hash_password
from app.database import AsyncSessionLocal, Base, engine

DEV_EMAIL = "dev@local.dev"
DEV_USERNAME = "dev"
DEV_PASSWORD = "devpassword123"


async def ensure_schema() -> bool:
    """Create tables on a fresh database. Returns True if the DB was fresh."""
    async with engine.begin() as conn:
        has_version = (
            await conn.execute(text("SELECT to_regclass('public.alembic_version')"))
        ).scalar()
        fresh = has_version is None
        if fresh:
            await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    return fresh


async def seed_dev_user() -> None:
    async with AsyncSessionLocal() as db:
        existing = await db.scalar(
            select(models.User).where(models.User.email == DEV_EMAIL)
        )
        if existing is None:
            db.add(
                models.User(
                    email=DEV_EMAIL,
                    username=DEV_USERNAME,
                    hashed_password=hash_password(DEV_PASSWORD),
                    is_verified=True,
                    is_admin=True,
                )
            )
            await db.commit()
            print(f"[dev] seeded user {DEV_EMAIL} / {DEV_PASSWORD}")
    await engine.dispose()


def main() -> None:
    fresh = asyncio.run(ensure_schema())
    cfg = Config("alembic.ini")
    if fresh:
        print("[dev] fresh database: created tables from models, stamping head")
        command.stamp(cfg, "head")
    else:
        command.upgrade(cfg, "head")
    asyncio.run(seed_dev_user())


if __name__ == "__main__":
    main()
