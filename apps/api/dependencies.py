"""
FastAPI dependency injection utilities.
"""
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from database.session import get_db
from security.auth import get_current_user_id
from security.rate_limiter import rate_limit_middleware_check


async def get_request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "req-unknown")
