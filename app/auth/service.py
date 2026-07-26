"""Auth service: login, token refresh, user management."""

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.auth.schemas import CreateUserRequest
from app.auth.utils import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
)


async def authenticate(db: AsyncSession, email: str, password: str) -> User:
    """Validate credentials and return user. Raises 401 on failure."""
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHENTICATED", "message": "Invalid email or password"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHENTICATED", "message": "Account is inactive"},
        )

    return user


def create_tokens(user: User) -> dict:
    """Generate access + refresh token pair."""
    return {
        "access_token": create_access_token(user.id, user.role),
        "refresh_token": create_refresh_token(user.id),
        "token_type": "bearer",
    }


async def refresh_access(db: AsyncSession, refresh_token: str) -> dict:
    """Validate refresh token and issue a new access token."""
    payload = decode_token(refresh_token)
    if payload is None or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHENTICATED", "message": "Invalid refresh token"},
        )

    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHENTICATED", "message": "User not found"},
        )

    return {
        "access_token": create_access_token(user.id, user.role),
        "token_type": "bearer",
    }


async def create_user(db: AsyncSession, data: CreateUserRequest) -> User:
    """Admin-only: create a new user account."""
    # Check for duplicate email
    result = await db.execute(select(User).where(User.email == data.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "DUPLICATE_EMAIL", "message": "Email already registered"},
        )

    user = User(
        email=data.email,
        password_hash=hash_password(data.password),
        role=data.role,
        display_name=data.display_name,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def list_users(db: AsyncSession, offset: int = 0, limit: int = 50) -> list[User]:
    """Admin-only: list all users."""
    result = await db.execute(
        select(User).offset(offset).limit(limit).order_by(User.created_at.desc())
    )
    return list(result.scalars().all())


async def change_user_role(db: AsyncSession, user_id: str, new_role: str) -> User:
    """Admin-only: change a user's role."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "User not found"},
        )
    if new_role not in ("admin", "editor", "student"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "INVALID_ROLE", "message": "Role must be admin, editor, or student"},
        )
    user.role = new_role
    await db.commit()
    await db.refresh(user)
    return user
