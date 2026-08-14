from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from dotenv import load_dotenv
import os

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL", "TEST_DATABASE_URL")

engine = create_async_engine(DATABASE_URL, echo=False)

AsyncSessionLocal = sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
)

class Base(DeclarativeBase):
        """Shared declarative base for all SQLAlchemy models in the app."""
        pass

async def get_db():
        """Yield a database session for each request.

        Yields:
            AsyncSession: An async SQLAlchemy session bound to the configured DB.
        """
        async with AsyncSessionLocal() as session:
                yield session
