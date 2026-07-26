"""Question router: CRUD, search, review queue, bulk actions, vocabulary."""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, require_role
from app.models import User
from app.question import service
from app.question.schemas import (
    QuestionCreate,
    QuestionUpdate,
    QuestionResponse,
    QuestionListResponse,
    BulkStatusRequest,
    BulkTagRequest,
)

router = APIRouter(prefix="/api/v1/questions", tags=["questions"])


@router.post("", response_model=QuestionResponse)
async def create_question(
    body: QuestionCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("admin", "editor")),
):
    """Create a new question (manual entry)."""
    return await service.create_question(db, body)


@router.get("", response_model=QuestionListResponse)
async def list_questions(
    section: Optional[str] = Query(None),
    skill: Optional[str] = Query(None),
    difficulty: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    type: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    offset: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Search and filter questions."""
    items, total = await service.list_questions(
        db, section=section, skill=skill, difficulty=difficulty,
        status=status, type=type, q=q, offset=offset, limit=limit,
    )
    return QuestionListResponse(items=items, total=total, offset=offset, limit=limit)


@router.get("/review", response_model=list[dict])
async def get_review_queue(
    upload_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("admin", "editor")),
):
    """Get draft questions for review, sorted by confidence ASC."""
    questions = await service.get_review_queue(db, upload_id)
    result = []
    for q in questions:
        item = {
            "id": q.id,
            "section": q.section,
            "type": q.type,
            "stem": "",
            "extraction_confidence": q.extraction_confidence,
            "status": q.status,
        }
        # Load current version for stem
        if q.current_version_id:
            from sqlalchemy import select
            from app.models import QuestionVersion
            vresult = await db.execute(
                select(QuestionVersion).where(QuestionVersion.id == q.current_version_id)
            )
            v = vresult.scalar_one_or_none()
            if v:
                item["stem"] = v.stem[:200]
                item["options"] = v.options
                item["correct_answer"] = v.correct_answer
                item["explanation"] = v.explanation
        result.append(item)
    return result


@router.get("/vocabulary")
async def get_vocabulary(
    section: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get skill vocabulary for tagging (grouped by section → domain → skill)."""
    skills = await service.get_skill_vocabulary(db, section)
    grouped = {}
    for s in skills:
        sec = s.section
        if sec not in grouped:
            grouped[sec] = {}
        domain = s.domain_label
        if domain not in grouped[sec]:
            grouped[sec][domain] = []
        grouped[sec][domain].append({
            "skill_key": s.skill_key,
            "skill_label": s.skill_label,
        })
    return grouped


@router.get("/{question_id}", response_model=QuestionResponse)
async def get_question(
    question_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get a question by ID with current version."""
    return await service.get_question(db, question_id)


@router.patch("/{question_id}", response_model=QuestionResponse)
async def update_question(
    question_id: str,
    body: QuestionUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("admin", "editor")),
):
    """Update a question. Creates a new version if published."""
    return await service.update_question(db, question_id, body)


@router.delete("/{question_id}")
async def delete_question(
    question_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("admin", "editor")),
):
    """Delete a question (blocked if referenced by attempts)."""
    await service.delete_question(db, question_id)
    return {"ok": True}


@router.post("/{question_id}/publish", response_model=QuestionResponse)
async def publish_question(
    question_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("admin", "editor")),
):
    """Publish a question (requires skill + difficulty + correct_answer)."""
    return await service.publish_question(db, question_id)


@router.post("/{question_id}/archive", response_model=QuestionResponse)
async def archive_question(
    question_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("admin", "editor")),
):
    """Archive a question."""
    return await service.archive_question(db, question_id)


@router.patch("/{question_id}/status")
async def update_status(
    question_id: str,
    new_status: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("admin", "editor")),
):
    """Change question status: draft, saved, reviewed, published."""
    return await service.update_question_status(db, question_id, new_status)


@router.post("/bulk/status")
async def bulk_update_status(
    body: BulkStatusRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("admin", "editor")),
):
    """Bulk update question status."""
    count = await service.bulk_update_status(db, body.ids, body.status)
    return {"updated": count}


@router.post("/bulk/tag")
async def bulk_tag(
    body: BulkTagRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("admin", "editor")),
):
    """Bulk tag questions with skill/difficulty."""
    count = await service.bulk_tag(db, body.ids, body.skill, body.difficulty)
    return {"updated": count}
