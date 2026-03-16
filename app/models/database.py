from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.config import Settings

engine = None
async_session_factory: async_sessionmaker[AsyncSession] | None = None


async def init_db(settings: Settings) -> None:
    global engine, async_session_factory

    engine = create_async_engine(settings.database_url, echo=False)
    async_session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


async def close_db() -> None:
    global engine
    if engine:
        await engine.dispose()


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    assert async_session_factory is not None, "Database not initialized"
    return async_session_factory
