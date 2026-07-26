"""Result analysis router: scoring, trends, weak-skill detection."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models import User, Attempt, AttemptResult, AttemptAnswer, AttemptQuestion, QuestionVersion, Question

router = APIRouter(prefix="/api/v1/results", tags=["results"])


@router.get("/{attempt_id}")
async def get_result(
    attempt_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get full analysis for an attempt."""
    result = await db.execute(select(Attempt).where(Attempt.id == attempt_id))
    attempt = result.scalar_one_or_none()
    if attempt is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND"})

    # Ownership check
    if user.role == "student" and str(user.id) != str(attempt.student_id):
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN"})

    # Get analysis
    aresult = await db.execute(select(AttemptResult).where(AttemptResult.attempt_id == attempt_id))
    analysis = aresult.scalar_one_or_none()

    # Per-question details
    aqs = await db.execute(
        select(AttemptQuestion).where(AttemptQuestion.attempt_id == attempt_id)
        .order_by(AttemptQuestion.section, AttemptQuestion.module_no, AttemptQuestion.question_order)
    )
    questions_detail = []
    for aq in aqs.scalars().all():
        vresult = await db.execute(select(QuestionVersion).where(QuestionVersion.id == aq.question_version_id))
        version = vresult.scalar_one_or_none()

        aresult2 = await db.execute(select(AttemptAnswer).where(AttemptAnswer.attempt_question_id == aq.id))
        answer = aresult2.scalar_one_or_none()

        questions_detail.append({
            "aq_id": aq.id,
            "section": aq.section,
            "module_no": aq.module_no,
            "form": aq.form,
            "stem": version.stem[:200] if version else "",
            "options": version.options if version else None,
            "correct_answer": version.correct_answer if version else "",
            "student_answer": answer.answer if answer else None,
            "is_correct": answer.is_correct if answer else False,
            "time_spent_sec": answer.time_spent_sec if answer else None,
        })

    return {
        "attempt_id": attempt.id,
        "exam_id": attempt.exam_id,
        "scaled": {"rw": attempt.scaled_rw, "math": attempt.scaled_math, "total": attempt.scaled_total},
        "raw": {"rw": attempt.raw_rw, "math": attempt.raw_math},
        "routing": attempt.routing,
        "domain_breakdown": analysis.domain_breakdown if analysis else {},
        "difficulty_breakdown": analysis.difficulty_breakdown if analysis else {},
        "weak_skills": analysis.weak_skills if analysis else {},
        "questions": questions_detail,
    }


@router.get("/me/trends")
async def get_trends(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get score trends across all submitted attempts."""
    result = await db.execute(
        select(Attempt).where(
            Attempt.student_id == user.id,
            Attempt.status == "submitted",
        ).order_by(Attempt.submitted_at.asc())
    )
    attempts = result.scalars().all()

    return [
        {
            "attempt_id": a.id,
            "exam_id": a.exam_id,
            "scaled_rw": a.scaled_rw,
            "scaled_math": a.scaled_math,
            "scaled_total": a.scaled_total,
            "submitted_at": a.submitted_at.isoformat() if a.submitted_at else None,
        }
        for a in attempts
    ]
