from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from sqlalchemy import select
from tests.conftest import TestSessionLocal
from tests.test_predictor import add_exercise_entry, get_test_user_id
from app import models
from app.predictor import service as predictor
from app.predictor.features import get_session_aggregates
from app.timeutil import DEFAULT_TIMEZONE, is_valid_timezone, zone_for

NEW_YORK = ZoneInfo("America/New_York")
TOKYO = ZoneInfo("Asia/Tokyo")

# 03:30Z and 05:00Z on Jun 16: Jun 15 23:30 and Jun 16 01:00 in New York (two
# local days), but 12:30 and 14:00 on Jun 16 in Tokyo (one local day).
NOW = datetime(2026, 6, 16, 6, 0, tzinfo=timezone.utc)
FIRST = datetime(2026, 6, 16, 3, 30, tzinfo=timezone.utc)
SECOND = datetime(2026, 6, 16, 5, 0, tzinfo=timezone.utc)


async def seed(user_id: int):
    async with TestSessionLocal() as db:
        await add_exercise_entry(db, user_id, "Squat", FIRST)
        await add_exercise_entry(db, user_id, "Bench", SECOND)


class TestHelpers:
    def test_validation(self):
        assert is_valid_timezone("Asia/Tokyo")
        assert not is_valid_timezone("Mars/Olympus")
        assert not is_valid_timezone("")

    def test_zone_for_falls_back(self):
        assert zone_for(None).key == DEFAULT_TIMEZONE
        assert zone_for("Mars/Olympus").key == DEFAULT_TIMEZONE
        assert zone_for("Asia/Tokyo").key == "Asia/Tokyo"


class TestSessionBoundaries:
    async def test_day_boundary_follows_zone(self, auth_client):
        user_id = await get_test_user_id()
        await seed(user_id)
        async with TestSessionLocal() as db:
            ny = await get_session_aggregates(db, user_id, NOW, tz=NEW_YORK)
            tokyo = await get_session_aggregates(db, user_id, NOW, tz=TOKYO)
        assert ny["today_session_length"] == 1
        assert tokyo["today_session_length"] == 2

    async def test_default_is_eastern(self, auth_client):
        user_id = await get_test_user_id()
        await seed(user_id)
        async with TestSessionLocal() as db:
            default = await get_session_aggregates(db, user_id, NOW)
        assert default["today_session_length"] == 1

    async def test_cache_is_not_shared_across_zones(self, auth_client):
        user_id = await get_test_user_id()
        await seed(user_id)
        async with TestSessionLocal() as db:
            await predictor.predict(db, user_id, now=NOW, tz=NEW_YORK)
            assert predictor._aggregate_cache[user_id]["tz"] == "America/New_York"
            await predictor.predict(db, user_id, now=NOW, tz=TOKYO)
            cached = predictor._aggregate_cache[user_id]
        assert cached["tz"] == "Asia/Tokyo"
        assert cached["aggregates"]["today_session_length"] == 2


class TestTimezoneApi:
    async def test_new_user_defaults_to_eastern(self, auth_client):
        res = await auth_client.get("/api/users/me")
        assert res.json()["timezone"] == DEFAULT_TIMEZONE

    async def test_register_stores_given_timezone(self, client):
        res = await client.post("/api/users/register", json={
            "email": "tz@example.com", "username": "tzuser",
            "password": "password123", "timezone": "Europe/Berlin",
        })
        assert res.status_code == 200
        assert res.json()["timezone"] == "Europe/Berlin"

    async def test_register_rejects_bad_timezone(self, client):
        res = await client.post("/api/users/register", json={
            "email": "tz@example.com", "username": "tzuser",
            "password": "password123", "timezone": "Mars/Olympus",
        })
        assert res.status_code == 422

    async def test_patch_me_updates_and_invalidates_cache(self, auth_client):
        user_id = await get_test_user_id()
        await seed(user_id)
        async with TestSessionLocal() as db:
            await predictor.predict(db, user_id, now=NOW)
        assert user_id in predictor._aggregate_cache

        res = await auth_client.patch("/api/users/me", json={"timezone": "Asia/Tokyo"})
        assert res.status_code == 200
        assert res.json()["timezone"] == "Asia/Tokyo"
        assert user_id not in predictor._aggregate_cache

        async with TestSessionLocal() as db:
            user = (await db.execute(select(models.User).where(models.User.id == user_id))).scalar_one()
        assert user.timezone == "Asia/Tokyo"

    async def test_patch_me_rejects_bad_timezone(self, auth_client):
        res = await auth_client.patch("/api/users/me", json={"timezone": "Mars/Olympus"})
        assert res.status_code == 422
        res = await auth_client.get("/api/users/me")
        assert res.json()["timezone"] == DEFAULT_TIMEZONE
