from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from tests.conftest import TestSessionLocal
from app import models
from app.predictor import service as predictor 
from app.predictor.mixer import DEFAULT_WEIGHTS, weight_candidates
from app.predictor.config import FEATURE_ORDER, FEATURE_SIGNATURE, CONFIG_VERSION

FROZEN_NOW = datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc)

# The row production actually held when the incident was found: written before
# phase_transition/position_freq existed, so it has three keys and no
# signature. Served as-is, the two newer features score at weight 0.

LEGACY_WEIGHTS = {
        "recency": 0.16267394841208443,
        "weekday": 0.08701475650835418,
        "transition": 0.2698653601483609,
}

# Deliberately lopsided legacy row, so serving it visibly changes the ranking
# on the history built by add_ranking_history().
SKEWED_LEGACY_WEIGHTS = {"transition": 0.0, "weekday": 0.0, "recency": 1.0}

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

async def set_weights_row(user_id: int, weights: dict):
    async with TestSessionLocal() as db:
        db.add(models.ModelWeights(user_id=user_id, weights=weights))
        await db.commit()

async def add_ranking_history(db, user_id: int):
    """Two identical sessions plus a recent Plank/Squat. With last_exercise
    "Bench", DEFAULT_WEIGHTS rank Row first while a recency_only weighting
    ranks Squat first, so the two are distinguishable by ranking alone."""
    base = FROZEN_NOW - timedelta(days=14)
    for week in range(2):
        start = base + timedelta(days=7 * week)
        for i, name in enumerate(["Squat", "Bench", "Row", "Curl", "Plank"]):
            await add_exercise_entry(db, user_id, name, start + timedelta(minutes=10 * i))
    await add_exercise_entry(db, user_id, "Plank", FROZEN_NOW - timedelta(hours=20))
    await add_exercise_entry(db, user_id, "Squat", FROZEN_NOW - timedelta(hours=19))

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
            ranked = await predictor.predict(db, user_id, last_exercise="Squat", now=FROZEN_NOW)

        assert ranked == ["Squat"]

        events = await get_events(user_id)
        assert len(events) == 1
        assert events[0].resolved is False
        assert events[0].data["event_type"] == "next_exercise_prediction"
        assert events[0].data["last_exercise"] == "Squat"
        assert events[0].data["ranked_exercises"] == ["Squat"]
        assert events[0].data["weights_snapshot"] == DEFAULT_WEIGHTS
        assert events[0].latency_ms is not None
        assert events[0].latency_ms >= 0

    async def test_hit_does_not_update_weights(self, auth_client):
        user_id = await get_test_user_id()
        async with TestSessionLocal() as db:
            await add_exercise_entry(db, user_id, "Squat", FROZEN_NOW - timedelta(days=1))
            await predictor.predict(db, user_id, last_exercise="Squat", now=FROZEN_NOW)
            await predictor.resolve(db, user_id, chosen_exercise="Squat")

        events = await get_events(user_id)
        weights_row = await get_weights_row(user_id)

        assert events[-1].resolved is True
        assert events[-1].data["hit"] is True
        assert events[-1].data["updated"] is False
        assert events[-1].data["chosen_exercise"] == "Squat"
        assert weights_row is None

    async def test_miss_updates_weights(self, auth_client):
        user_id = await get_test_user_id()
        async with TestSessionLocal() as db:
            await add_exercise_entry(db, user_id, "Deadlift", FROZEN_NOW - timedelta(days=1))
            await add_exercise_entry(db, user_id, "Row", FROZEN_NOW - timedelta(days=5))
            await add_exercise_entry(db, user_id, "OHP", FROZEN_NOW - timedelta(days=10))
            await add_exercise_entry(db, user_id, "Curl", FROZEN_NOW - timedelta(days=40))

            ranked = await predictor.predict(db, user_id, last_exercise="Deadlift", now=FROZEN_NOW)
            assert ranked == ["Deadlift", "Row", "OHP", "Curl"]

            await predictor.resolve(db, user_id, chosen_exercise="Curl")

        events = await get_events(user_id)
        weights_row = await get_weights_row(user_id)

        assert events[-1].data["hit"] is False
        assert events[-1].data["rank"] == 3
        assert events[-1].data["updated"] is True
        assert events[-1].data["chosen_exercise"] == "Curl"
        assert weights_row is not None
        assert weights_row.weights != DEFAULT_WEIGHTS

    async def test_resolve_chosen_exercise_not_in_candidates(self, auth_client):
        user_id = await get_test_user_id()
        async with TestSessionLocal() as db:
            await add_exercise_entry(db, user_id, "Squat", FROZEN_NOW - timedelta(days=1))
            await predictor.predict(db, user_id, last_exercise="Squat", now=FROZEN_NOW)
            await predictor.resolve(db, user_id, chosen_exercise="Lunges")

        events = await get_events(user_id)
        weights_row = await get_weights_row(user_id)

        assert events[-1].resolved is True
        assert events[-1].data["updated"] is False
        assert events[-1].data["chosen_exercise"] == "Lunges"
        assert weights_row is None

    async def test_resolve_with_no_unresolved_event_is_a_noop(self, auth_client):
        user_id = await get_test_user_id()
        async with TestSessionLocal() as db:
            await predictor.resolve(db, user_id, chosen_exercise="Anything")

        assert await get_events(user_id) == []
        assert await get_weights_row(user_id) is None

    async def test_stale_event_marked_resolved_without_updating(self, auth_client):
        user_id = await get_test_user_id()
        async with TestSessionLocal() as db:
            await add_exercise_entry(db, user_id, "Squat", FROZEN_NOW - timedelta(days=1))
            await predictor.predict(db, user_id, last_exercise="Squat", now=FROZEN_NOW)

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

    async def test_prediction_event_tracks_latency(self, auth_client):
        user_id = await get_test_user_id()
        async with TestSessionLocal() as db:
            await add_exercise_entry(db, user_id, "Squat", FROZEN_NOW - timedelta(days=1))
            await predictor.predict(db, user_id, last_exercise="Squat", now=FROZEN_NOW)

        events = await get_events(user_id)
        assert len(events) == 1
        assert events[0].latency_ms is not None
        assert events[0].data["event_type"] == "next_exercise_prediction"
        assert events[0].data["prediction_created_at"] == FROZEN_NOW.isoformat()

class TestPredictorWeightsCompatibility:
    """A stored weights row must never silently outlive the feature set it
    was learned for. Production served a three-key row after two features
    were added: scoring read the missing keys as weight 0 while the update
    path filled the from defaults, so the model that was served differed
    from the one that was validated and from the one that got scored."""

    async def test_legacy_row_without_signature_is_ignored(self, auth_client):
        user_id = await get_test_user_id()
        await set_weights_row(user_id, LEGACY_WEIGHTS)
        async with TestSessionLocal() as db:
            await add_ranking_history(db, user_id)
            await predictor.predict(db, user_id, last_exercise="Bench", now=FROZEN_NOW)
        events = await get_events(user_id)
        assert events[-1].data["weights_snapshot"] == DEFAULT_WEIGHTS

    async def test_legacy_row_does_not_change_the_ranking(self, auth_client):
        user_id = await get_test_user_id()
        await set_weights_row(user_id, SKEWED_LEGACY_WEIGHTS)
        async with TestSessionLocal() as db:
            await add_ranking_history(db, user_id)
            ranked = await predictor.predict(db, user_id, last_exercise="Bench", now=FROZEN_NOW)
        events = await get_events(user_id)
        expected = weight_candidates(events[-1].data["candidates"], DEFAULT_WEIGHTS)
        assert ranked == expected
        assert ranked[0] == "Row" # recency_only weighting would put Squat first

    async def test_row_with_other_feature_signature_is_ignored(self, auth_client):
        user_id = await get_test_user_id()
        await set_weights_row(user_id, {
            **{k: 0.5 for k in FEATURE_ORDER},
            predictor.SIGNATURE_KEY: "learned-for-another-feature-set",
        })
        async with TestSessionLocal() as db:
            await add_ranking_history(db, user_id)
            await predictor.predict(db, user_id, last_exercise="Bench", now=FROZEN_NOW)

        events = await get_events(user_id)
        assert events[-1].data["weights_snapshot"] == DEFAULT_WEIGHTS

    async def test_row_with_current_signature_is_used(self, auth_client):
        user_id = await get_test_user_id()
        learned = {k: 0.1 * (i + 1) for i, k in enumerate(FEATURE_ORDER)}
        await set_weights_row(user_id, {**learned, predictor.SIGNATURE_KEY: FEATURE_SIGNATURE})
        async with TestSessionLocal() as db:
            await add_ranking_history(db, user_id)
            await predictor.predict(db, user_id, last_exercise="Bench", now=FROZEN_NOW)
        events = await get_events(user_id)
        snapshot = events[-1].data["weights_snapshot"]
        assert snapshot == learned
        assert predictor.SIGNATURE_KEY not in snapshot

    async def test_miss_replaces_legacy_row_with_a_complete_signed_one(self, auth_client):
        user_id = await get_test_user_id()
        await set_weights_row(user_id, LEGACY_WEIGHTS)
        async with TestSessionLocal() as db:
            await add_exercise_entry(db, user_id, "Deadlift", FROZEN_NOW - timedelta(days=1))
            await add_exercise_entry(db, user_id, "Row", FROZEN_NOW - timedelta(days=5))
            await add_exercise_entry(db, user_id, "OHP", FROZEN_NOW - timedelta(days=10))
            await add_exercise_entry(db, user_id, "Curl", FROZEN_NOW - timedelta(days=40))
            await predictor.predict(db, user_id, last_exercise="Deadlift", now=FROZEN_NOW)
            await predictor.resolve(db, user_id, chosed_exercise="Curl")

        events = await get_events(user_id)
        weights_row = await get_weights_row(user_id)

        # The event was scored against the weights that were actually served.
        assert events[-1].data["weights_before"] == DEFAULT_WEGHTS
        assert events[-1].data["updated"] is True
        assert weights_row.weights[predictor.SIGNATURE_KEY] == FEATURE_SIGNATURE
        assert set(weights_row.weights) == set(FEATURE_ORDER) | {predictor.SIGNATURE_KEY}

    async def test_learned_weights_are_served_on_the_next_prediction(self, auth_client):
        user_id = await get_test_user_id()
        async with TestSessionLocal() as db:
            await add_exercise_entry(db, user_id, "Deadlift", FROZEN_NOW - timedelta(days=1))
            await add_exercise_entry(db, user_id, "Row", FROZEN_NOW - timedelta(days=5))
            await add_exercise_entry(db, user_id, "OHP", FROZEN_NOW - timedelta(days=10))
            await add_exercise_entry(db, user_id, "Curl", FROZEN_NOW - timedelta(days=40))
            await predictor.predict(db, user_id, last_exercise="Deadlift", now=FROZEN_NOW)
            await predictor.resolve(db, user_id, chosen_exercise="Curl")
            await predictor.predict(db, user_id, last_exercise="Deadlift", now=FROZEN_NOW)
        
        events = await get_events(user_id)
        weights_row = await get_weights_row(user_id)
        learned = {k: weights_row.weights[k] for k in FEATURE_ORDER}

        assert learned != DEFAULT_WEIGHTS
        assert events[-1].data["weights_snapshot"] == learned

    async def test_events_are_stamped_with_the_config_version(self, auth_client):
        user_id: await get_test_user_id()
        async with TestSessionLocal() as db:
            await add_exercise_entry(db, user_id, "Squat", FROZEN_NOW - timedelta(days=1))
            await predictor.predict(db, user_id, last_exercise="Squat", now=FROZEN_NOW)

            events = await get_events(user_id)
            assert events[-1].data["config_version"] == CONFIG_VERSION

            # Resolving must not drop the stamp
            await predictor.resolve(db, user_id, chosen_exercise="Squat")

        events = await get_events(user_id)
        assert events[-1].resolved is True
        assert events[-1].data["config_version"] == CONFIG_VERSION

        res = await auth_client.get("/api/predictor/metrics")
        assert res.json()[0]["data"]["config_version"] == CONFIG_VERSION


class TestPredictorMetricsEndpoint:
    """/api/predictor/metrics must be scoped to the caller - it's easy to
    forget the user_id filter here since current_user is otherwise only
    used to require authentication."""

    async def test_metrics_excludes_other_users_events(self, client, auth_client):
        user_id = await get_test_user_id()

        await client.post("/api/users/register", json={
            "email": "other@example.com",
            "username": "otheruser",
            "password": "testpassword123",
        })
        other_user_id = await get_test_user_id("other@example.com")

        async with TestSessionLocal() as db:
            await add_exercise_entry(db, user_id, "Squat", FROZEN_NOW - timedelta(days=1))
            await predictor.predict(db, user_id, last_exercise="Squat", now=FROZEN_NOW)
            db.add(models.PredictionEvent(
                user_id=other_user_id,
                resolved=False,
                data={"event_type": "next_exercise_prediction"},
            ))
            await db.commit()

        res = await auth_client.get("/api/predictor/metrics")
        assert res.status_code == 200
        payload = res.json()
        assert len(payload) == 1
        assert all(e["user_id"] == user_id for e in payload)


