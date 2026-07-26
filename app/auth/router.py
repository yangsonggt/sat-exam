"""Auth router: login, refresh, profile, admin user management."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, require_role
from app.models import User
from app.auth import service
from app.auth.schemas import (
    LoginRequest,
    TokenResponse,
    RefreshRequest,
    UserResponse,
    CreateUserRequest,
    UpdateProfileRequest,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
admin_router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


# ── Public endpoints ──────────────────────────────────────

@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = await service.authenticate(db, body.email, body.password)
    return service.create_tokens(user)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    result = await service.refresh_access(db, body.refresh_token)
    return {**result, "refresh_token": body.refresh_token}


# ── Authenticated endpoints ───────────────────────────────

@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)):
    return user


@router.patch("/me", response_model=UserResponse)
async def update_me(
    body: UpdateProfileRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.display_name is not None:
        user.display_name = body.display_name
    await db.commit()
    await db.refresh(user)
    return user


# ── Admin endpoints ───────────────────────────────────────

@admin_router.post("/users", response_model=UserResponse)
async def create_user(
    body: CreateUserRequest,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_role("admin")),
):
    return await service.create_user(db, body)


@admin_router.get("/users", response_model=list[UserResponse])
async def list_users(
    offset: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_role("admin")),
):
    return await service.list_users(db, offset, limit)


@admin_router.patch("/users/{user_id}/role", response_model=UserResponse)
async def change_role(
    user_id: str,
    new_role: str,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_role("admin")),
):
    return await service.change_user_role(db, user_id, new_role)


@admin_router.patch("/users/{user_id}/toggle-active", response_model=UserResponse)
async def toggle_active(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_role("admin")),
):
    return await service.toggle_user_active(db, user_id)


@admin_router.delete("/users/{user_id}", response_model=dict)
async def delete_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_role("admin")),
):
    await service.delete_user(db, user_id)
    return {"deleted": True}
