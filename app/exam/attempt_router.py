"""Attempt router: start, rehydrate, answer, submit, analysis."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models import User
from app.exam import runtime

router = APIRouter(prefix="/api/v1", tags=["attempts"])


class AnswerRequest(BaseModel):
    aq_id: str
    answer: str
    marked: bool = False


@router.post("/exams/{exam_id}/attempts")
async def start_attempt(
    exam_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Start a new exam attempt."""
    attempt = await runtime.start_attempt(db, user.id, exam_id)
    state = await runtime.get_attempt_state(db, attempt.id)
    return state


@router.get("/attempts/{attempt_id}")
async def get_attempt(
    attempt_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Rehydrate attempt state (timer, questions, answers)."""
    state = await runtime.get_attempt_state(db, attempt_id)
    # Ownership check
    if str(user.id) != str(state.get("student_id", user.id)) and user.role == "student":
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN"})
    return state


@router.post("/attempts/{attempt_id}/answers")
async def save_answer(
    attempt_id: str,
    body: AnswerRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Auto-save an answer."""
    return await runtime.save_answer(db, attempt_id, body.aq_id, body.answer, body.marked)


@router.post("/attempts/{attempt_id}/modules/current/submit")
async def submit_module(
    attempt_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Submit current module: grade, route (if M1), advance."""
    return await runtime.submit_module(db, attempt_id)


@router.get("/attempts/{attempt_id}/analysis")
async def get_analysis(
    attempt_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get attempt analysis results."""
    from app.models import Attempt, AttemptResult
    from sqlalchemy import select

    result = await db.execute(
        select(AttemptResult).where(AttemptResult.attempt_id == attempt_id)
    )
    analysis = result.scalar_one_or_none()

    att_result = await db.execute(select(Attempt).where(Attempt.id == attempt_id))
    attempt = att_result.scalar_one_or_none()

    if attempt is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND"})

    return {
        "attempt_id": attempt.id,
        "scaled": {
            "rw": attempt.scaled_rw,
            "math": attempt.scaled_math,
            "total": attempt.scaled_total,
        },
        "raw": {
            "rw": attempt.raw_rw,
            "math": attempt.raw_math,
        },
        "routing": attempt.routing,
        "domain_breakdown": analysis.domain_breakdown if analysis else {},
        "difficulty_breakdown": analysis.difficulty_breakdown if analysis else {},
        "weak_skills": analysis.weak_skills if analysis else {},
        "status": attempt.status,
    }
