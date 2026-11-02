"""
SHIV Platform Unified Authentication & Identity Gateway Router.
Directly integrates with the primary SHIV Database (shiv_dev.db)
providing register, login, session token issuance, refresh, and profile resolution.
"""
from __future__ import annotations

import hashlib
import logging
import random
import secrets
import sqlite3
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import jwt
from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr, Field

from config.settings import settings

logger = logging.getLogger("shivai.auth.router")

router = APIRouter(prefix="/auth", tags=["SHIV Identity & Authentication"])

pwd_context = CryptContext(schemes=["argon2", "bcrypt"], deprecated="auto")

SHIV_DB_PATH = Path("F:/SHIV/shiv-database/shiv_dev.db")


def get_db_connection() -> sqlite3.Connection:
    """Connects to the primary local SHIV Database SQLite file with row access."""
    if not SHIV_DB_PATH.exists():
        # Fallback to local working directory if moved
        alt_path = Path(__file__).resolve().parent.parent.parent.parent / "shiv-database" / "shiv_dev.db"
        if alt_path.exists():
            conn = sqlite3.connect(str(alt_path))
        else:
            conn = sqlite3.connect("F:/SHIV/shivai/shivai.db")
    else:
        conn = sqlite3.connect(str(SHIV_DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def generate_unique_shiv_id(conn: sqlite3.Connection) -> str:
    """Generates a unique human-readable SHIV ID (e.g. SHV-10842)."""
    for _ in range(20):
        num = random.randint(10000, 99999)
        candidate = f"SHV-{num}"
        row = conn.execute("SELECT id FROM users WHERE shiv_id = ?", (candidate,)).fetchone()
        if not row:
            return candidate
    return f"SHV-{int(time.time()) % 100000}"


# --- Pydantic Schemas ---
class UserRegisterRequest(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6, max_length=128)
    display_name: Optional[str] = None
    phone: Optional[str] = None


class UserLoginRequest(BaseModel):
    email_or_username: str
    password: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class UserProfile(BaseModel):
    id: str
    shiv_id: Optional[str] = None
    email: str
    username: str
    display_name: Optional[str] = None
    role: str = "user"
    status: str = "active"
    avatar_url: Optional[str] = None
    created_at: Optional[str] = None


class TokenResponseData(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 3600
    user: UserProfile


class AuthResponse(BaseModel):
    success: bool = True
    data: Any
    message: str = "Success"


# --- Helper Methods ---
def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception as e:
        logger.warning(f"Argon2 verification failed, trying fallback: {e}")
        # Direct bcrypt / fallback
        try:
            import bcrypt
            return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
        except Exception:
            return False


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(user_id: str, email: str, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=60)
    payload = {
        "sub": user_id,
        "id": user_id,
        "email": email,
        "role": role,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.SHIV_AUTH_JWT_SECRET, algorithm=settings.SHIV_AUTH_JWT_ALGORITHM)


def create_refresh_token() -> tuple[str, str, datetime]:
    token = secrets.token_urlsafe(64)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    expire = datetime.now(timezone.utc) + timedelta(days=30)
    return token, token_hash, expire


def decode_access_token(token: str) -> Dict[str, Any]:
    try:
        return jwt.decode(
            token,
            settings.SHIV_AUTH_JWT_SECRET,
            algorithms=[settings.SHIV_AUTH_JWT_ALGORITHM],
            options={"verify_exp": True},
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "TOKEN_EXPIRED", "message": "SHIV Auth token has expired."}},
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "INVALID_TOKEN", "message": f"Token validation failed: {str(e)}"}},
            headers={"WWW-Authenticate": "Bearer"},
        )


# --- Endpoints ---
@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(body: UserRegisterRequest):
    """Registers a new user in SHIV DB with Argon2 hashing and unique SHIV ID."""
    conn = get_db_connection()
    try:
        email = body.email.strip().lower()
        username = body.username.strip()
        norm_username = username.lower()

        # Check existing email
        row = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if row:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": {"code": "EMAIL_EXISTS", "message": "An account with this email already exists."}},
            )

        # Check existing username
        row = conn.execute(
            "SELECT id FROM users WHERE username = ? OR normalized_username = ?",
            (username, norm_username),
        ).fetchone()
        if row:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": {"code": "USERNAME_TAKEN", "message": "This username is already taken."}},
            )

        import uuid
        user_id = str(uuid.uuid4())
        shiv_id = generate_unique_shiv_id(conn)
        hashed_pwd = get_password_hash(body.password)
        now_iso = datetime.now(timezone.utc).isoformat()
        display_name = body.display_name or username

        conn.execute(
            """
            INSERT INTO users (id, shiv_id, email, username, normalized_username, display_name, phone, hashed_password, email_verified, phone_verified, mfa_enabled, role, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, 0, 0, 'user', 'active', ?, ?)
            """,
            (user_id, shiv_id, email, username, norm_username, display_name, body.phone, hashed_pwd, now_iso, now_iso),
        )
        conn.commit()

        user_profile = UserProfile(
            id=user_id,
            shiv_id=shiv_id,
            email=email,
            username=username,
            display_name=display_name,
            role="user",
            status="active",
            created_at=now_iso,
        )

        return AuthResponse(
            success=True,
            data=user_profile.model_dump(),
            message="SHIV Account created successfully",
        )
    finally:
        conn.close()


@router.post("/login", response_model=AuthResponse)
def login(request: Request, body: UserLoginRequest):
    """Authenticates user using email or username, creates session, issues JWT tokens."""
    conn = get_db_connection()
    try:
        ident = body.email_or_username.strip().lower()
        row = conn.execute(
            """
            SELECT id, shiv_id, email, username, display_name, hashed_password, role, status, avatar_url, created_at
            FROM users
            WHERE lower(email) = ? OR lower(username) = ? OR lower(normalized_username) = ? OR lower(shiv_id) = ?
            LIMIT 1
            """,
            (ident, ident, ident, ident),
        ).fetchone()

        if not row or not verify_password(body.password, row["hashed_password"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": {"code": "INVALID_CREDENTIALS", "message": "Invalid email/username or password."}},
            )

        if row["status"] != "active":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": {"code": "ACCOUNT_INACTIVE", "message": "This SHIV account is suspended or inactive."}},
            )

        user_id = row["id"]
        email = row["email"]
        role = row["role"]

        # Generate tokens
        access_token = create_access_token(user_id, email, role)
        refresh_token, refresh_token_hash, expire = create_refresh_token()

        # Create session in DB
        import uuid
        session_id = str(uuid.uuid4())
        ip = request.client.host if request.client else "127.0.0.1"
        ua = request.headers.get("user-agent", "Unknown Client")[:250]
        now_iso = datetime.now(timezone.utc).isoformat()
        exp_iso = expire.isoformat()

        try:
            conn.execute(
                """
                INSERT INTO sessions (id, user_id, device_info, ip_address, expires_at, revoked, refresh_token_hash, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?)
                """,
                (session_id, user_id, ua, ip, exp_iso, refresh_token_hash, now_iso, now_iso),
            )
            conn.commit()
        except Exception as e:
            logger.warning(f"Could not persist session record: {e}")

        user_profile = UserProfile(
            id=user_id,
            shiv_id=row["shiv_id"],
            email=email,
            username=row["username"],
            display_name=row["display_name"] or row["username"],
            role=role,
            status=row["status"],
            avatar_url=row["avatar_url"],
            created_at=str(row["created_at"]),
        )

        token_data = TokenResponseData(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=3600,
            user=user_profile,
        )

        return AuthResponse(
            success=True,
            data=token_data.model_dump(),
            message="Logged in successfully",
        )
    finally:
        conn.close()


@router.get("/me", response_model=AuthResponse)
def get_me(authorization: Optional[str] = Header(None)):
    """Returns the authenticated user's full SHIV Identity profile from DB."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "UNAUTHORIZED", "message": "Bearer authentication required."}},
        )

    raw_token = authorization.split(" ")[1].strip()
    payload = decode_access_token(raw_token)
    user_id = payload.get("sub") or payload.get("id")

    conn = get_db_connection()
    try:
        row = conn.execute(
            "SELECT id, shiv_id, email, username, display_name, role, status, avatar_url, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()

        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": {"code": "USER_NOT_FOUND", "message": "User account no longer exists."}},
            )

        user_profile = UserProfile(
            id=row["id"],
            shiv_id=row["shiv_id"],
            email=row["email"],
            username=row["username"],
            display_name=row["display_name"] or row["username"],
            role=row["role"],
            status=row["status"],
            avatar_url=row["avatar_url"],
            created_at=str(row["created_at"]),
        )

        return AuthResponse(success=True, data=user_profile.model_dump())
    finally:
        conn.close()


@router.post("/refresh", response_model=AuthResponse)
def refresh_token_endpoint(body: RefreshTokenRequest):
    """Refreshes an expired access token using a valid persistent refresh token."""
    token_hash = hashlib.sha256(body.refresh_token.encode()).hexdigest()
    conn = get_db_connection()
    try:
        row = conn.execute(
            """
            SELECT s.id as session_id, s.user_id, s.expires_at, s.revoked, u.email, u.role, u.status
            FROM sessions s
            JOIN users u ON u.id = s.user_id
            WHERE s.refresh_token_hash = ?
            LIMIT 1
            """,
            (token_hash,),
        ).fetchone()

        if not row or row["revoked"] == 1:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": {"code": "SESSION_REVOKED", "message": "Invalid or revoked refresh token."}},
            )

        # Revoke old session and issue new pair
        conn.execute("UPDATE sessions SET revoked = 1 WHERE id = ?", (row["session_id"],))

        new_access = create_access_token(row["user_id"], row["email"], row["role"])
        new_refresh, new_hash, new_expire = create_refresh_token()
        now_iso = datetime.now(timezone.utc).isoformat()

        conn.execute(
            """
            INSERT INTO sessions (id, user_id, device_info, ip_address, expires_at, revoked, refresh_token_hash, created_at, updated_at)
            VALUES (?, ?, 'refreshed_session', '127.0.0.1', ?, 0, ?, ?, ?)
            """,
            (str(uuid.uuid4()), row["user_id"], new_expire.isoformat(), new_hash, now_iso, now_iso),
        )
        conn.commit()

        return AuthResponse(
            success=True,
            data={
                "access_token": new_access,
                "refresh_token": new_refresh,
                "token_type": "bearer",
                "expires_in": 3600,
            },
        )
    finally:
        conn.close()


@router.post("/logout", response_model=AuthResponse)
def logout(body: RefreshTokenRequest):
    """Revokes active session tokens."""
    token_hash = hashlib.sha256(body.refresh_token.encode()).hexdigest()
    conn = get_db_connection()
    try:
        conn.execute("UPDATE sessions SET revoked = 1 WHERE refresh_token_hash = ?", (token_hash,))
        conn.commit()
        return AuthResponse(success=True, data={"revoked": True}, message="Logged out successfully")
    finally:
        conn.close()
