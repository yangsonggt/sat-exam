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


@router.post("", response_model=dict)
async def create_exam(
    body: ExamCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("admin", "editor")),
):
    """Create an exam blueprint with modules and selection rules."""
    exam = await service.create_exam(db, body, user.id)
    # Reload with eager loading
    exam = await service.get_exam(db, exam.id)
    return _exam_to_dict(exam)


@router.get("", response_model=dict)
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
    return {"items": [_exam_to_dict(e) for e in items], "total": total, "offset": offset, "limit": limit}


@router.get("/{exam_id}", response_model=dict)
async def get_exam(
    exam_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get exam detail with modules."""
    exam = await service.get_exam(db, exam_id)
    return _exam_to_dict(exam)


@router.patch("/{exam_id}", response_model=dict)
async def update_exam(
    exam_id: str,
    body: ExamUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("admin", "editor")),
):
    """Update exam metadata."""
    exam = await service.update_exam(db, exam_id, body)
    exam = await service.get_exam(db, exam.id)
    return _exam_to_dict(exam)


@router.post("/{exam_id}/publish", response_model=dict)
async def publish_exam(
    exam_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("admin", "editor")),
):
    """Validate pool sufficiency and publish exam."""
    exam = await service.publish_exam(db, exam_id)
    exam = await service.get_exam(db, exam.id)
    return _exam_to_dict(exam)


def _exam_to_dict(exam) -> dict:
    """Convert Exam ORM to dict (avoids async lazy-load issues)."""
    return {
        "id": exam.id,
        "title": exam.title,
        "description": exam.description,
        "status": exam.status,
        "routing_threshold_rw": exam.routing_threshold_rw,
        "routing_threshold_math": exam.routing_threshold_math,
        "timer_mode": exam.timer_mode,
        "created_at": exam.created_at.isoformat() if exam.created_at else None,
        "updated_at": exam.updated_at.isoformat() if exam.updated_at else None,
        "modules": [
            {
                "id": m.id,
                "section": m.section,
                "module_no": m.module_no,
                "form": m.form,
                "time_limit_min": m.time_limit_min,
                "question_count": m.question_count,
                "selection_rules": [
                    {"id": r.id, "skill": r.skill, "difficulty": r.difficulty, "count": r.count}
                    for r in (m.selection_rules or [])
                ],
            }
            for m in (exam.modules or [])
        ],
    }


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
