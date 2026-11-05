from pathlib import Path

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATABASE_URL = f"sqlite+aiosqlite:///{PROJECT_ROOT / 'garage.db'}"

engine = create_async_engine(DATABASE_URL)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as db:
        yield db
