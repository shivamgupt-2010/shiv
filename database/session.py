"""
Database session management with SQLAlchemy 2.0 Async Engine.
"""
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select
from config.settings import settings
from database.models import Base, User


# Initialize async engine
engine = create_async_engine(
    settings.DATABASE_URL,
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
