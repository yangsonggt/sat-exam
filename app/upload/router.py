"""Upload router: PDF upload, list, status, delete."""

from fastapi import APIRouter, Depends, UploadFile, File, BackgroundTasks, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, require_role
from app.models import User
from app.upload import service
from app.upload.schemas import UploadResponse, UploadListResponse, ParseStatusResponse

router = APIRouter(prefix="/api/v1/uploads", tags=["uploads"])


@router.post("", response_model=UploadResponse)
async def upload_pdf(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("admin", "editor")),
):
    """Upload a PDF file for question extraction."""
    return await service.upload_file(db, file, user)


@router.get("", response_model=UploadListResponse)
async def list_uploads(
    offset: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("admin", "editor")),
):
    """List all uploads (paginated)."""
    items, total = await service.list_uploads(db, offset, limit)
    return UploadListResponse(items=items, total=total, offset=offset, limit=limit)


@router.get("/{upload_id}", response_model=UploadResponse)
async def get_upload(
    upload_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("admin", "editor")),
):
    """Get upload details."""
    return await service.get_upload(db, upload_id)


@router.get("/{upload_id}/status", response_model=ParseStatusResponse)
async def get_parse_status(
    upload_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("admin", "editor")),
):
    """Get parsing status for an upload."""
    upload = await service.get_upload(db, upload_id)

    # Get latest parse job
    from sqlalchemy import select
    from app.models import ParseJob
    result = await db.execute(
        select(ParseJob)
        .where(ParseJob.upload_id == upload_id)
        .order_by(ParseJob.started_at.desc())
        .limit(1)
    )
    job = result.scalar_one_or_none()

    return ParseStatusResponse(
        upload_id=upload_id,
        status=upload.status,
        error=job.error if job else None,
    )


@router.delete("/{upload_id}")
async def delete_upload(
    upload_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("admin", "editor")),
):
    """Delete an upload. Published questions are preserved."""
    await service.delete_upload(db, upload_id)
    return {"ok": True}


@router.post("/images")
async def upload_image(
    file: UploadFile = File(...),
    user: User = Depends(require_role("admin", "editor")),
):
    """Upload an image for use in question stems/options."""
    import uuid
    from pathlib import Path

    ext = file.filename.split(".")[-1].lower() if file.filename else "png"
    if ext not in ("png", "jpg", "jpeg", "gif", "svg", "webp"):
        raise HTTPException(400, "Invalid image format")

    name = f"{uuid.uuid4().hex}.{ext}"
    uploads_dir = Path("uploads/images")
    uploads_dir.mkdir(parents=True, exist_ok=True)
    (uploads_dir / name).write_bytes(await file.read())

    return {"url": f"/uploads/images/{name}"}
