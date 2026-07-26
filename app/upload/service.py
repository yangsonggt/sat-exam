"""Upload service: file validation, storage, dedup, parse job enqueue."""

import hashlib
import os
import uuid
from datetime import datetime
from typing import Optional

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import Upload, ParseJob, User


async def upload_file(
    db: AsyncSession,
    file: UploadFile,
    uploader: User,
) -> Upload:
    """Validate, store, dedup, and create an Upload record. Enqueues a parse job."""
    settings = get_settings()

    # Validate file size
    contents = await file.read()
    if len(contents) > settings.upload_max_file_size_mb * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={"code": "FILE_TOO_LARGE",
                    "message": f"Max file size is {settings.upload_max_file_size_mb}MB"},
        )

    # Validate MIME type
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "INVALID_FILE_TYPE", "message": "Only PDF files are accepted"},
        )

    # Checksum for dedup
    checksum = hashlib.sha256(contents).hexdigest()

    # Check for duplicate
    result = await db.execute(select(Upload).where(Upload.checksum == checksum))
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "DUPLICATE_UPLOAD",
                "message": f"This file was already uploaded as '{existing.filename}'",
                "existing_upload_id": existing.id,
            },
        )

    # Store file
    upload_id = str(uuid.uuid4())
    storage_dir = os.path.join(settings.upload_storage_path, "raw")
    os.makedirs(storage_dir, exist_ok=True)
    storage_key = os.path.join("raw", f"{upload_id}.pdf")
    full_path = os.path.join(settings.upload_storage_path, storage_key)
    with open(full_path, "wb") as f:
        f.write(contents)

    # Create DB record
    upload = Upload(
        id=upload_id,
        uploader_id=uploader.id,
        filename=file.filename,
        storage_key=storage_key,
        checksum=checksum,
        file_size=len(contents),
        mime_type=file.content_type or "application/pdf",
        status="uploaded",
    )
    db.add(upload)
    await db.commit()
    await db.refresh(upload)

    # Enqueue parse job (Phase 2: fire-and-forget background task)
    # In production, this would go through Redis/ARQ
    # For now, we trigger it synchronously via the router
    return upload


async def get_upload(db: AsyncSession, upload_id: str) -> Upload:
    """Get an upload by ID."""
    result = await db.execute(select(Upload).where(Upload.id == upload_id))
    upload = result.scalar_one_or_none()
    if upload is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Upload not found"},
        )
    return upload


async def list_uploads(
    db: AsyncSession, offset: int = 0, limit: int = 50
) -> tuple[list[Upload], int]:
    """List uploads with pagination. Returns (items, total)."""
    total_result = await db.execute(select(func.count(Upload.id)))
    total = total_result.scalar()

    result = await db.execute(
        select(Upload)
        .order_by(Upload.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().all()), total


async def delete_upload(db: AsyncSession, upload_id: str) -> None:
    """Delete an upload and its file. Published questions are NOT deleted."""
    upload = await get_upload(db, upload_id)

    # Delete file from disk
    settings = get_settings()
    full_path = os.path.join(settings.upload_storage_path, upload.storage_key)
    if os.path.exists(full_path):
        os.remove(full_path)

    await db.delete(upload)
    await db.commit()
