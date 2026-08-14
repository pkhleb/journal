from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from dotenv import load_dotenv
import os

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL", "TEST_DATABASE_URL")

engine = create_async_engine(DATABASE_URL, echo=False)

AsyncSessionLocal=sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False
)

class Base(DeclarativeBase):
        pass

async def get_db():
        async with AsyncSessionLocal() as session:
                yield session
