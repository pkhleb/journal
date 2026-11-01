from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from tests.conftest import TestSessionLocal
from tests.test_predictor import (
    FROZEN_NOW,
    add_exercise_entry,
    get_events,
    get_test_user_id,
    get_weights_row,
)
from app import models
from app.predictor import service as predictor
from app.predictor.mixer import DEFAULT_WEIGHTS, apply_miss_only_update
from app.predictor.config import FEATURE_ORDER


def learned(row) -> dict:
    """The weights stored on a ModelWeights row, without the signature key."""
    return {k: row.weights[k] for k in FEATURE_ORDER}


def replay(events, chosen_overrides=None, skip=()):
    """Independent re-computation of the weights after the given resolved
    events, in order, using the mixer directly. Mirrors what the production
    path would have produced had the skipped events never happened."""
    chosen_overrides = chosen_overrides or {}
    w = dict(DEFAULT_WEIGHTS)
    for ev in events:
        if ev.id in skip:
            continue
        chosen = chosen_overrides.get(ev.id, ev.data["chosen_exercise"])
        w, _ = apply_miss_only_update(ev.data["candidates"], chosen, w, DEFAULT_WEIGHTS)
    return w


async def seed_scored_entries(user_id: int, n: int = 3) -> list[int]:
    """History where logging Curl is always a miss (ranked last of 6), plus n
    entries that each get a resolved prediction event (the first two update the weights) tied to
    them by entry_id. Returns the n entry ids, oldest event first.

    The n entries start out as prose-only so they don't feed the aggregates
    while the predictions are made (Curl would otherwise stop being a miss),
    then become Curl exercise entries once the events are scored."""
    ids = []
    async with TestSessionLocal() as db:
        await add_exercise_entry(db, user_id, "Deadlift", FROZEN_NOW - timedelta(days=1))
        await add_exercise_entry(db, user_id, "Row", FROZEN_NOW - timedelta(days=5))
        await add_exercise_entry(db, user_id, "OHP", FROZEN_NOW - timedelta(days=10))
        await add_exercise_entry(db, user_id, "Burpees", FROZEN_NOW - timedelta(days=20))
        await add_exercise_entry(db, user_id, "Plank", FROZEN_NOW - timedelta(days=30))
        await add_exercise_entry(db, user_id, "Curl", FROZEN_NOW - timedelta(days=40))
        for i in range(n):
            entry = models.Entry(
                user_id=user_id, prose="pending", created_at=FROZEN_NOW - timedelta(days=41 + i),
            )
            db.add(entry)
            await db.commit()
            await db.refresh(entry)
            ids.append(entry.id)

        for entry_id in ids:
            await predictor.predict(db, user_id, last_exercise="Deadlift", now=FROZEN_NOW)
            await predictor.resolve(db, user_id, chosen_exercise="Curl", entry_id=entry_id)

        for entry_id in ids:
            entry = await db.get(models.Entry, entry_id)
            entry.prose = None
            entry.metric_type = "exercise"
            entry.metric_data = {"name": "Curl"}
        await db.commit()
        predictor.invalidate(user_id)

    events = await get_events(user_id)
    assert len(events) == n
    # Two misses move the weights enough that a third Curl can become a hit,
    # so only the first two events are guaranteed to have updated them.
    assert all(e.data["updated"] is True for e in events[:2]), "precondition: first two events are misses"
    return ids


async def events_by_entry(user_id: int) -> dict:
    return {e.data["entry_id"]: e for e in await get_events(user_id)}


class TestResolveRecordsEntryId:
    async def test_create_entry_stores_entry_id_on_event(self, auth_client):
        user_id = await get_test_user_id()
        async with TestSessionLocal() as db:
            await add_exercise_entry(db, user_id, "Bench", datetime.now(timezone.utc) - timedelta(days=1))
        res = await auth_client.get("/api/exercises/ranked")
        assert res.status_code == 200

        res = await auth_client.post("/api/entries", json={
            "metric_type": "exercise", "metric_data": {"name": "Squat"},
        })
        assert res.status_code == 200

        events = await get_events(user_id)
        assert len(events) == 1
        assert events[0].resolved is True
        assert events[0].data["entry_id"] == res.json()["id"]


class TestDeleteRollsBack:
    async def test_delete_first_event_replays_the_rest(self, auth_client):
        user_id = await get_test_user_id()
        ids = await seed_scored_entries(user_id)
        before = await get_events(user_id)

        res = await auth_client.delete(f"/api/entries/{ids[0]}")
        assert res.status_code == 200

        remaining = await get_events(user_id)
        assert [e.data["entry_id"] for e in remaining] == ids[1:]

        expected = replay(before, skip={before[0].id})
        row_weights = learned(await get_weights_row(user_id))
        assert row_weights == expected

        # The first surviving event now starts from the defaults, not from
        # the weights the deleted event had produced.
        assert before[1].data["weights_before"] != DEFAULT_WEIGHTS
        assert remaining[0].data["weights_before"] == DEFAULT_WEIGHTS
        assert remaining[1].data["weights_before"] == remaining[0].data["weights_after"]
        assert remaining[-1].data["weights_after"] == expected

    async def test_delete_last_event_leaves_earlier_ones_untouched(self, auth_client):
        user_id = await get_test_user_id()
        ids = await seed_scored_entries(user_id)
        before = await get_events(user_id)

        res = await auth_client.delete(f"/api/entries/{ids[-1]}")
        assert res.status_code == 200

        remaining = await get_events(user_id)
        assert [e.data for e in remaining] == [e.data for e in before[:-1]]
        assert learned(await get_weights_row(user_id)) == before[-2].data["weights_after"]

    async def test_delete_only_event_reverts_to_default_weights(self, auth_client):
        user_id = await get_test_user_id()
        ids = await seed_scored_entries(user_id, n=1)
        assert learned(await get_weights_row(user_id)) != DEFAULT_WEIGHTS

        res = await auth_client.delete(f"/api/entries/{ids[0]}")
        assert res.status_code == 200

        assert await get_events(user_id) == []
        assert learned(await get_weights_row(user_id)) == DEFAULT_WEIGHTS

    async def test_replayed_event_rank_and_hit_are_reevaluated(self, auth_client):
        user_id = await get_test_user_id()
        ids = await seed_scored_entries(user_id)
        by_entry = await events_by_entry(user_id)
        stored_weights_before = by_entry[ids[1]].data["weights_before"]
        assert stored_weights_before != DEFAULT_WEIGHTS

        await auth_client.delete(f"/api/entries/{ids[0]}")

        after = (await events_by_entry(user_id))[ids[1]]
        expected_w, info = apply_miss_only_update(
            after.data["candidates"], "Curl", DEFAULT_WEIGHTS, DEFAULT_WEIGHTS
        )
        assert after.data["rank"] == info["rank"]
        assert after.data["hit"] == info["hit"]
        assert after.data["updated"] == info["updated"]
        assert after.data["weights_before"] == DEFAULT_WEIGHTS
        assert after.data["weights_after"] == expected_w

    async def test_delete_entry_without_event_changes_nothing(self, auth_client):
        user_id = await get_test_user_id()
        await seed_scored_entries(user_id, n=2)
        async with TestSessionLocal() as db:
            unrelated = models.Entry(user_id=user_id, prose="just a note")
            db.add(unrelated)
            await db.commit()
            await db.refresh(unrelated)
        before = await get_events(user_id)
        weights_before = learned(await get_weights_row(user_id))

        res = await auth_client.delete(f"/api/entries/{unrelated.id}")
        assert res.status_code == 200

        assert [e.data for e in await get_events(user_id)] == [e.data for e in before]
        assert learned(await get_weights_row(user_id)) == weights_before

    async def test_legacy_event_without_entry_id_is_left_alone(self, auth_client):
        user_id = await get_test_user_id()
        ids = await seed_scored_entries(user_id, n=2)
        async with TestSessionLocal() as db:
            ev = (await db.execute(
                select(models.PredictionEvent)
                .where(models.PredictionEvent.user_id == user_id)
                .order_by(models.PredictionEvent.id)
            )).scalars().first()
            ev.data = {k: v for k, v in ev.data.items() if k != "entry_id"}
            await db.commit()
        before = await get_events(user_id)
        weights_before = learned(await get_weights_row(user_id))

        res = await auth_client.delete(f"/api/entries/{ids[0]}")
        assert res.status_code == 200

        assert [e.data for e in await get_events(user_id)] == [e.data for e in before]
        assert learned(await get_weights_row(user_id)) == weights_before

    async def test_delete_stale_event_drops_it_without_touching_weights(self, auth_client):
        user_id = await get_test_user_id()
        ids = await seed_scored_entries(user_id, n=2)
        async with TestSessionLocal() as db:
            entry = models.Entry(
                user_id=user_id, metric_type="exercise", metric_data={"name": "Row"},
            )
            db.add(entry)
            await db.commit()
            await db.refresh(entry)
            await predictor.predict(db, user_id, last_exercise="Deadlift", now=FROZEN_NOW)
            ev = (await db.execute(
                select(models.PredictionEvent).where(
                    models.PredictionEvent.user_id == user_id,
                    models.PredictionEvent.resolved == False,  # noqa: E712
                )
            )).scalar_one()
            ev.created_at = datetime.now(timezone.utc) - predictor.STALE_CUTOFF - timedelta(minutes=5)
            await db.commit()
            await predictor.resolve(db, user_id, chosen_exercise="Row", entry_id=entry.id)
        weights_before = learned(await get_weights_row(user_id))
        scored_before = [e.data for e in await get_events(user_id) if not e.data.get("stale")]

        res = await auth_client.delete(f"/api/entries/{entry.id}")
        assert res.status_code == 200

        events = await get_events(user_id)
        assert all(not e.data.get("stale") for e in events)
        assert [e.data for e in events] == scored_before
        assert learned(await get_weights_row(user_id)) == weights_before

    async def test_delete_does_not_touch_other_users_events(self, auth_client):
        user_id = await get_test_user_id()
        ids = await seed_scored_entries(user_id, n=1)
        async with TestSessionLocal() as db:
            other = models.User(
                email="other@example.com", username="otheruser",
                hashed_password="x", is_verified=True,
            )
            db.add(other)
            await db.commit()
            await db.refresh(other)
            db.add(models.PredictionEvent(
                user_id=other.id, resolved=True, resolved_at=datetime.now(timezone.utc),
                data={"entry_id": ids[0], "chosen_exercise": "Curl"},
            ))
            await db.commit()
            other_id = other.id

        await auth_client.delete(f"/api/entries/{ids[0]}")

        async with TestSessionLocal() as db:
            theirs = (await db.execute(
                select(models.PredictionEvent)
                .where(models.PredictionEvent.user_id == other_id)
            )).scalars().all()
        assert len(theirs) == 1
        assert await get_events(user_id) == []

    async def test_unknown_entry_is_404_and_leaves_events(self, auth_client):
        user_id = await get_test_user_id()
        await seed_scored_entries(user_id, n=1)
        before = await get_events(user_id)

        res = await auth_client.delete("/api/entries/999999")
        assert res.status_code == 404
        assert len(await get_events(user_id)) == len(before)


class TestRenameRescores:
    async def rename(self, auth_client, entry_id, name):
        return await auth_client.patch(f"/api/entries/{entry_id}", json={
            "metric_type": "exercise", "metric_data": {"name": name},
        })

    async def test_rename_to_a_hit_rescores_and_replays(self, auth_client):
        user_id = await get_test_user_id()
        ids = await seed_scored_entries(user_id)
        before = await get_events(user_id)

        # Deadlift is the top-ranked candidate for these events, so renaming
        # Curl -> Deadlift turns the first event from a miss into a hit.
        res = await self.rename(auth_client, ids[0], "Deadlift")
        assert res.status_code == 200

        by_entry = await events_by_entry(user_id)
        first = by_entry[ids[0]]
        assert first.data["chosen_exercise"] == "Deadlift"
        assert first.data["hit"] is True
        assert first.data["rank"] == 0
        assert first.data["updated"] is False
        assert first.data["weights_after"] is None
        assert first.data["weights_before"] == DEFAULT_WEIGHTS

        expected = replay(before, chosen_overrides={before[0].id: "Deadlift"})
        assert learned(await get_weights_row(user_id)) == expected
        assert by_entry[ids[1]].data["weights_before"] == DEFAULT_WEIGHTS
        assert by_entry[ids[-1]].data["weights_after"] == expected

    async def test_rename_to_name_outside_candidates(self, auth_client):
        user_id = await get_test_user_id()
        ids = await seed_scored_entries(user_id, n=2)
        before = await get_events(user_id)

        res = await self.rename(auth_client, ids[0], "Lunges")
        assert res.status_code == 200

        by_entry = await events_by_entry(user_id)
        first = by_entry[ids[0]]
        assert first.data["chosen_exercise"] == "Lunges"
        assert first.data["hit"] is None
        assert first.data["rank"] is None
        assert first.data["updated"] is False
        assert learned(await get_weights_row(user_id)) == replay(
            before, chosen_overrides={before[0].id: "Lunges"}
        )

    async def test_rename_keeps_event_and_its_entry_link(self, auth_client):
        user_id = await get_test_user_id()
        ids = await seed_scored_entries(user_id, n=2)

        await self.rename(auth_client, ids[0], "Deadlift")

        assert sorted((await events_by_entry(user_id)).keys()) == sorted(ids)

    async def test_edit_without_name_change_does_not_rescore(self, auth_client):
        user_id = await get_test_user_id()
        ids = await seed_scored_entries(user_id)
        before = await get_events(user_id)
        weights_before = learned(await get_weights_row(user_id))

        res = await auth_client.patch(f"/api/entries/{ids[0]}", json={
            "prose": "felt heavy",
            "metric_type": "exercise",
            "metric_data": {"name": "Curl", "reps": 12},
        })
        assert res.status_code == 200

        assert [e.data for e in await get_events(user_id)] == [e.data for e in before]
        assert learned(await get_weights_row(user_id)) == weights_before

    async def test_changing_to_non_exercise_drops_the_event(self, auth_client):
        user_id = await get_test_user_id()
        ids = await seed_scored_entries(user_id)
        before = await get_events(user_id)

        res = await auth_client.patch(f"/api/entries/{ids[0]}", json={"prose": "rest day"})
        assert res.status_code == 200

        remaining = await get_events(user_id)
        assert [e.data["entry_id"] for e in remaining] == ids[1:]
        assert learned(await get_weights_row(user_id)) == replay(
            before, skip={before[0].id}
        )

    async def test_rename_of_entry_without_event_is_harmless(self, auth_client):
        user_id = await get_test_user_id()
        await seed_scored_entries(user_id, n=1)
        async with TestSessionLocal() as db:
            entry = models.Entry(
                user_id=user_id, metric_type="exercise", metric_data={"name": "Row"},
            )
            db.add(entry)
            await db.commit()
            await db.refresh(entry)
        before = await get_events(user_id)
        weights_before = learned(await get_weights_row(user_id))

        res = await self.rename(auth_client, entry.id, "Lunges")
        assert res.status_code == 200

        assert [e.data for e in await get_events(user_id)] == [e.data for e in before]
        assert learned(await get_weights_row(user_id)) == weights_before


class TestCacheInvalidation:
    async def ranked(self, auth_client, last_exercise=None):
        params = {"last_exercise": last_exercise} if last_exercise else {}
        res = await auth_client.get("/api/exercises/ranked", params=params)
        assert res.status_code == 200
        return res.json()

    async def test_delete_removes_exercise_from_suggestions(self, auth_client):
        user_id = await get_test_user_id()
        async with TestSessionLocal() as db:
            await add_exercise_entry(db, user_id, "Squat", datetime.now(timezone.utc) - timedelta(days=1))
            await add_exercise_entry(db, user_id, "Bench", datetime.now(timezone.utc) - timedelta(days=2))
        assert set(await self.ranked(auth_client)) == {"Squat", "Bench"}

        async with TestSessionLocal() as db:
            squat = (await db.execute(
                select(models.Entry).where(
                    models.Entry.user_id == user_id,
                    models.Entry.metric_data["name"].astext == "Squat",
                )
            )).scalar_one()
        res = await auth_client.delete(f"/api/entries/{squat.id}")
        assert res.status_code == 200

        assert await self.ranked(auth_client) == ["Bench"]

    async def test_edit_swaps_old_name_for_new_name(self, auth_client):
        user_id = await get_test_user_id()
        async with TestSessionLocal() as db:
            await add_exercise_entry(db, user_id, "Squat", datetime.now(timezone.utc) - timedelta(days=1))
        assert await self.ranked(auth_client) == ["Squat"]

        async with TestSessionLocal() as db:
            entry = (await db.execute(
                select(models.Entry).where(models.Entry.user_id == user_id)
            )).scalar_one()
        res = await auth_client.patch(f"/api/entries/{entry.id}", json={
            "metric_type": "exercise", "metric_data": {"name": "Lunges"},
        })
        assert res.status_code == 200

        assert await self.ranked(auth_client) == ["Lunges"]

    async def test_public_invalidate_clears_user_cache(self, auth_client):
        user_id = await get_test_user_id()
        async with TestSessionLocal() as db:
            await add_exercise_entry(db, user_id, "Squat", FROZEN_NOW - timedelta(days=1))
            await predictor.predict(db, user_id, now=FROZEN_NOW)
        assert user_id in predictor._aggregate_cache

        predictor.invalidate(user_id)

        assert user_id not in predictor._aggregate_cache
        predictor.invalidate(user_id)  # idempotent
