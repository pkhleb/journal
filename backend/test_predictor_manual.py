import asyncio
import sys
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models import User, ModelWeights, PredictionEvent
from app.predictor import service as predictor

async def show_state(db, user_id, label):
    print(f"\n--- {label} ---")

    weights_result = await db.execute(
        select(ModelWeights).where(ModelWeights.user_id == user_id)
    )
    weights_row = weights_result.scalar_one_or_none()
    print("model_weights:", weights_row.weights if weights_row else "(none yet - using DEFAULT_WEIGHTS)")

    events_result = await db.execute(
        select(PredictionEvent)
        .where(PredictionEvent.user_id == user_id)
        .order_by(PredictionEvent.created_at.desc())
        .limit(3)
    )
    events = events_result.scalars().all()
    print(f"last {len(events)} prediction_events:")
    for e in events:
        d = e.data
        print(
            f"  id={e.id} resolved={e.resolved} "
            f"chosen={d.get('chosen_exercise')} rank={d.get('rank')} "
            f"hit={d.get('hit')} updated={d.get('updated')}"
        )

async def main(email: str, chosen_exxercise: str, last_exercise: str | None = None):
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if not user:
            print(f"No user found for {email}")
            return

        await show_state(db, user.id, "before")

        ranked = await predictor.predict(db, user.id, last_exercise)
        print(f"\npredicted ranking (top 5): {ranked[:5]}")
        print(f"is '{chosen_exercise}' in top 3? {chosen_exercise in ranked[:3]}")

        await predictor.resolve(db, user.id, chosen_exercise=chosen_exxercise)

        await show_state(db, user.id, "after")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("usage: python test_predictor.py <email> <chosen_exercise> [last_exercise]")
        sys.exit(1)

    email = sys.argv[1]
    chosen_exercise = sys.argv[2]
    last_exercise = sys.argv[3] if len(sys.argv) > 3 else None
    asyncio.run(main(email, chosen_exercise, last_exercise))
