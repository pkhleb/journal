import pytest
from datetime import datetime, timezone
from tests.conftest import TestSessionLocal
from sqlalchemy import update
from app import models
from tests.test_predictor import get_test_user_id


async def add_entry(user_id: int, created_at: datetime):
    async with TestSessionLocal() as db:
        db.add(models.Entry(user_id=user_id, prose="x", created_at=created_at))
        await db.commit()


async def add_other_user() -> int:
    async with TestSessionLocal() as db:
        user = models.User(email="o@example.com", username="other", hashed_password="x")
        db.add(user)
        await db.commit()
        return user.id


async def make_admin(email: str = "test@example.com"):
    async with TestSessionLocal() as db:
        await db.execute(
            update(models.User).where(models.User.email == email).values(is_admin=True)
        )
        await db.commit()


class TestActivityAccess:
    async def test_requires_auth(self, client):
        res = await client.get("/api/activity")
        assert res.status_code == 401

    async def test_non_admin_forbidden(self, auth_client):
        res = await auth_client.get("/api/activity")
        assert res.status_code == 403

    async def test_me_exposes_is_admin(self, auth_client):
        assert (await auth_client.get("/api/users/me")).json()["is_admin"] is False
        await make_admin()
        assert (await auth_client.get("/api/users/me")).json()["is_admin"] is True


class TestActivity:
    @pytest.fixture(autouse=True)
    async def admin(self, auth_client):
        await make_admin()

    async def test_empty(self, auth_client):
        res = await auth_client.get("/api/activity")
        assert res.status_code == 200
        assert res.json() == []

    async def test_weekly_counts_distinct_users_and_zero_fills(self, auth_client):
        me = await get_test_user_id()
        other = await add_other_user()
        # 2026-06-15 is a Monday; 06-17 same week; 06-29 two weeks later.
        await add_entry(me, datetime(2026, 6, 15, 9, tzinfo=timezone.utc))
        await add_entry(me, datetime(2026, 6, 17, 9, tzinfo=timezone.utc))
        await add_entry(other, datetime(2026, 6, 16, 9, tzinfo=timezone.utc))
        await add_entry(other, datetime(2026, 6, 29, 9, tzinfo=timezone.utc))

        res = await auth_client.get("/api/activity?period=week")
        assert res.json() == [
            {"period_start": "2026-06-15", "posts": 3, "users": 2},
            {"period_start": "2026-06-22", "posts": 0, "users": 0},
            {"period_start": "2026-06-29", "posts": 1, "users": 1},
        ]

    async def test_monthly_spans_year_boundary(self, auth_client):
        me = await get_test_user_id()
        await add_entry(me, datetime(2025, 12, 31, 12, tzinfo=timezone.utc))
        await add_entry(me, datetime(2026, 2, 1, 12, tzinfo=timezone.utc))

        res = await auth_client.get("/api/activity?period=month")
        assert [b["period_start"] for b in res.json()] == [
            "2025-12-01", "2026-01-01", "2026-02-01",
        ]

    async def test_invalid_period_rejected(self, auth_client):
        res = await auth_client.get("/api/activity?period=day")
        assert res.status_code == 422
