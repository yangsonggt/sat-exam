"""Auth schemas: request/response models for login, tokens, user management."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    id: str
    email: str
    role: str
    display_name: Optional[str] = None
    grade: Optional[str] = None
    school: Optional[str] = None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class CreateUserRequest(BaseModel):
    email: EmailStr
    password: str
    role: str = "student"
    display_name: Optional[str] = None
    grade: Optional[str] = None
    school: Optional[str] = None


class UpdateProfileRequest(BaseModel):
    display_name: Optional[str] = None
