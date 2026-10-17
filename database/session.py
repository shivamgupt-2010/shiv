import os
from pathlib import Path
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select
from config.settings import settings
from database.models import Base, User


import tempfile
import logging

logger = logging.getLogger("shivai.database")


def _resolve_safe_database_url(raw_url: str) -> str:
    """Ensures SQLite target directory exists and is writable, falling back to tempdir or memory."""
    if "sqlite" in raw_url and ":memory:" not in raw_url:
        db_path_str = raw_url.split(":///")[-1]
        if db_path_str:
            try:
                db_path = Path(db_path_str).resolve()
                db_path.parent.mkdir(parents=True, exist_ok=True)
                # Test write capability
                test_marker = db_path.parent / ".perm_check"
                test_marker.touch(exist_ok=True)
                test_marker.unlink(missing_ok=True)
                return raw_url
            except Exception as e:
                safe_tmp = Path(tempfile.gettempdir()) / "shivai.db"
                logger.warning(
                    f"Configured SQLite path '{db_path_str}' is not writable ({e}). "
                    f"Falling back to safe temp path: '{safe_tmp}'."
                )
                return f"sqlite+aiosqlite:///{safe_tmp.as_posix()}"
    return raw_url


effective_db_url = _resolve_safe_database_url(settings.DATABASE_URL)

# Initialize async engine
engine = create_async_engine(
    effective_db_url,
    echo=settings.SHIVAI_DEBUG,
    future=True,
)

# Async session factory
async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for providing an async database session per request."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Creates all database tables and seed default user if not exists."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Seed default user for local development
    async with async_session_factory() as session:
        stmt = select(User).where(User.username == "default_user")
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        if not user:
            default_user = User(
                username="default_user",
                is_active=True,
                is_admin=True,
            )
            session.add(default_user)
            await session.commit()
