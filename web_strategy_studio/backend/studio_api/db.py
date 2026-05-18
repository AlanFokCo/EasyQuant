from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from studio_api.config import settings
from studio_api.models import Base


def _is_sqlite(url: str) -> bool:
    return url.startswith("sqlite")


engine = create_async_engine(
    settings.database_url,
    echo=False,
    connect_args={"timeout": 30} if _is_sqlite(settings.database_url) else {},
)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # HIGH-16: enable WAL mode and NORMAL sync for better concurrent
        # read performance on SQLite.  Has no effect on Postgres.
        if _is_sqlite(settings.database_url):
            await conn.execute(text("PRAGMA journal_mode=WAL"))
            await conn.execute(text("PRAGMA synchronous=NORMAL"))


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session
