import asyncio, sys
from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models import User
from app.routers.analytics import get_exercise_rankings


async def main(email: str, last_exercise: str | None = None):
    """Print the current ranked exercise list for a user.

    Args:
        email: Email address of the target user.
        last_exercise: Optional last exercise used to bias the ranking.
    """
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if not user:
            print(f"No user found for {email}")
            return
        ranked = await get_exercise_rankings(db, user.id, last_exercise)
        print(f"Rankings for {email}" + (f" after '{last_exercise}'" if last_exercise else "") + ":")
        for i, name in enumerate(ranked, 1):
            print(f"    {i}. {name}")


if __name__ == "__main__":
    email = sys.argv[1]
    last_exercise = sys.argv[2] if len(sys.argv) > 2 else None
    asyncio.run(main(email, last_exercise))
