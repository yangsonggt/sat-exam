"""Upload schemas."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class UploadResponse(BaseModel):
    id: str
    filename: str
    file_size: Optional[int] = None
    status: str
    checksum: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class UploadListResponse(BaseModel):
    items: list[UploadResponse]
    total: int
    offset: int
    limit: int


class ParseStatusResponse(BaseModel):
    upload_id: str
    status: str
    error: Optional[str] = None
