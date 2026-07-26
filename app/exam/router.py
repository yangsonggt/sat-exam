"""Exam blueprint router: CRUD, validation, publish."""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, require_role
from app.models import User
from app.exam import service
from app.exam.schemas import ExamCreate, ExamUpdate, ExamResponse, ExamListResponse

router = APIRouter(prefix="/api/v1/exams", tags=["exams"])


@router.post("", response_model=ExamResponse)
async def create_exam(
    body: ExamCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("admin", "editor")),
):
    """Create an exam blueprint with modules and selection rules."""
    return await service.create_exam(db, body, user.id)


@router.get("", response_model=ExamListResponse)
async def list_exams(
    status: Optional[str] = Query(None),
    offset: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List exams. Students only see published."""
    if user.role == "student" and status is None:
        status = "published"
    items, total = await service.list_exams(db, status_filter=status, offset=offset, limit=limit)
    return ExamListResponse(items=items, total=total, offset=offset, limit=limit)


@router.get("/{exam_id}", response_model=ExamResponse)
async def get_exam(
    exam_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get exam detail with modules."""
    return await service.get_exam(db, exam_id)


@router.patch("/{exam_id}", response_model=ExamResponse)
async def update_exam(
    exam_id: str,
    body: ExamUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("admin", "editor")),
):
    """Update exam metadata."""
    return await service.update_exam(db, exam_id, body)


@router.post("/{exam_id}/publish", response_model=ExamResponse)
async def publish_exam(
    exam_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("admin", "editor")),
):
    """Validate pool sufficiency and publish exam."""
    return await service.publish_exam(db, exam_id)


@router.get("/{exam_id}/validate")
async def validate_exam(
    exam_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("admin", "editor")),
):
    """Check if all selection rules can be satisfied (dry-run)."""
    errors = await service.validate_publish(db, exam_id)
    return {"valid": len(errors) == 0, "errors": errors}


@router.delete("/{exam_id}")
async def delete_exam(
    exam_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("admin", "editor")),
):
    """Delete exam (blocked if has attempts)."""
    await service.delete_exam(db, exam_id)
    return {"ok": True}
