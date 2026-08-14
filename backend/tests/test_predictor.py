from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from tests.conftest import TestSessionLocal
from app import models
from app.predictor import service as predictor 
from app.predictor.mixer import DEFAULT_WEIGHTS

FROZEN_NOW = datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc)

async def get_test_user_id(email: str = "test@example.com") -> int:
    async with TestSessionLocal() as db:
        result = await db.execute(select(models.User).where(models.User.email == email))
        return result.scalar_one().id

async def add_exercise_entry(db, user_id: int, name: str, created_at: datetime):
    db.add(models.Entry(
        user_id=user_id,
        metric_type="exercise",
        metric_data={"name": name},
        created_at=created_at,
    ))
    await db.commit()

async def get_events(user_id: int):
    async with TestSessionLocal() as db:
        result = await db.execute(
            select(models.PredictionEvent)
            .where(models.PredictionEvent.user_id == user_id)
            .order_by(models.PredictionEvent.created_at.asc())
        )
        return result.scalars().all()

async def get_weights_row(user_id: int):
    async with TestSessionLocal() as db:
        result = await db.execute(
            select(models.ModelWeights).where(models.ModelWeights.user_id == user_id)
        )
        return result.scalar_one_or_none()

class TestPredictorEndpointWiring:
    """Goes through the real HTTP endpoints rather than calling the
    predictor module directly - this is what would have caught the missing
    `from app.predictor import service as predictor` import in entries.py.
    Not trying to be deterministic here, just confirming the wiring holds."""

    async def test_ranked_endpoint_empty_history(self, auth_client):
        res = await auth_client.get("/api/exercises/ranked")
        assert res.status_code == 200
        assert res.json() == []

    async def test_logging_exercise_does_not_error(self, auth_client):
        await auth_client.get("/api/exercises/ranked")
        res = await auth_client.post("/api/entries", json={
            "metric_type": "exercise",
            "metric_data": {"name": "Bench Press"},
        })
        assert res.status_code == 200
        res = await auth_client.get("/api/exercises/ranked")
        assert res.status_code == 200

class TestPredictorMissOnlyUpdate:
    """Deterministic scenarios with frozen time and hand-placed history, so
    hit/miss outcomes don't depend on the real day tests happen to run."""

    async def test_predict_logs_unresolved_event(self, auth_client):
        user_id = await get_test_user_id()
        async with TestSessionLocal() as db:
            await add_exercise_entry(db, user_id, "Squat", FROZEN_NOW - timedelta(days=1))
            ranked = await predictor.predict(db, user_id, now=FROZEN_NOW)

        assert ranked == ["Squat"]

        events = await get_events(user_id)
        assert len(events) == 1
        assert events[0].resolved is False
        assert events[0].data["weights_snapshot"] == DEFAULT_WEIGHTS

    async def test_hit_does_not_update_weights(self, auth_client):
        user_id = await get_test_user_id()
        async with TestSessionLocal() as db:
            await add_exercise_entry(db, user_id, "Squat", FROZEN_NOW - timedelta(days=1))
            await predictor.predict(db, user_id, now=FROZEN_NOW)
            await predictor.resolve(db, user_id, chosen_exercise="Squat")

        events = await get_events(user_id)
        weights_row = await get_weights_row(user_id)

        assert events[-1].resolved is True
        assert events[-1].data["hit"] is True
        assert events[-1].data["updated"] is False
        assert weights_row is None

    async def test_miss_updates_weights(self, auth_client):
        user_id = await get_test_user_id()
        async with TestSessionLocal() as db:
            await add_exercise_entry(db, user_id, "Deadlift", FROZEN_NOW - timedelta(days=1))
            await add_exercise_entry(db, user_id, "Row", FROZEN_NOW - timedelta(days=5))
            await add_exercise_entry(db, user_id, "OHP", FROZEN_NOW - timedelta(days=10))
            await add_exercise_entry(db, user_id, "Curl", FROZEN_NOW - timedelta(days=40))

            ranked = await predictor.predict(db, user_id, now=FROZEN_NOW)
            assert ranked == ["Deadlift", "Row", "OHP", "Curl"]

            await predictor.resolve(db, user_id, chosen_exercise="Curl")

        events = await get_events(user_id)
        weights_row = await get_weights_row(user_id)

        assert events[-1].data["hit"] is False
        assert events[-1].data["rank"] == 3
        assert events[-1].data["updated"] is True
        assert weights_row is not None
        assert weights_row.weights != DEFAULT_WEIGHTS

    async def test_resolve_chosen_exercise_not_in_candidates(self, auth_client):
        user_id = await get_test_user_id()
        async with TestSessionLocal() as db:
            await add_exercise_entry(db, user_id, "Squat", FROZEN_NOW - timedelta(days=1))
            await predictor.predict(db, user_id, now=FROZEN_NOW)
            await predictor.resolve(db, user_id, chosen_exercise="Lunges")

        events = await get_events(user_id)
        weights_row = await get_weights_row(user_id)

        assert events[-1].resolved is True
        assert events[-1].data["updated"] is False
        assert weights_row is None

    async def test_resolve_with_no_unresolved_event_is_a_noop(self, auth_client):
        user_id = await get_test_user_id()
        async with TestSessionLocal() as db:
            await predictor.resolve(db, user_id, chosen_exercise="Anything")


        assert await get_events(user_id) == []
        assert await get_weights_row(user_id) is None

    async def test_stale_event_marked_resolved_without_updating(self, auth_client):
        user_id = await  get_test_user_id()
        async with TestSessionLocal() as db:
            await add_exercise_entry(db, user_id, "Squat", FROZEN_NOW - timedelta(days=1))
            await predictor.predict(db, user_id, now=FROZEN_NOW)

            result = await db.execute(
                select(models.PredictionEvent).where(models.PredictionEvent.user_id == user_id)
            )
            event = result.scalars().first()
            event.created_at = (
                datetime.now(timezone.utc) - predictor.STALE_CUTOFF - timedelta(minutes=5)
            )
            await db.commit()

            await predictor.resolve(db, user_id, chosen_exercise="Squat")

        events = await get_events(user_id)
        weights_row = await get_weights_row(user_id)

        assert events[-1].resolved is True
        assert events[-1].data.get("stale") is True
        assert weights_row is None

