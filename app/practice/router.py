"""Practice plan and execution router."""

from pydantic import BaseModel

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models import User
from app.practice import service

router = APIRouter(prefix="/api/v1/practice", tags=["practice"])


class GeneratePlanRequest(BaseModel):
    attempt_id: str
    target_days: int = 28


class AnswerRequest(BaseModel):
    ptq_id: str
    answer: str


@router.post("/plans")
async def generate_plan(
    body: GeneratePlanRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Generate a practice plan from an attempt's weak skills."""
    plan = await service.generate_plan(db, user.id, body.attempt_id, body.target_days)
    tasks = []
    for t in plan.tasks:
        tasks.append({
            "id": t.id,
            "skill": t.skill,
            "target_count": t.target_count,
            "completed_count": t.completed_count,
            "priority": t.priority,
            "status": t.status,
        })
    return {"plan_id": plan.id, "title": plan.title, "tasks": tasks}


@router.get("/plans")
async def list_plans(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List current user's practice plans."""
    plans = await service.list_plans(db, user.id)
    return [{"id": p.id, "title": p.title, "status": p.status} for p in plans]


@router.get("/plans/{plan_id}")
async def get_plan(
    plan_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get plan detail with tasks."""
    plan = await service.get_plan(db, plan_id)
    # Ownership check
    if user.role == "student" and str(user.id) != str(plan.user_id):
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN"})
    tasks = []
    for t in plan.tasks:
        tasks.append({
            "id": t.id,
            "skill": t.skill,
            "target_count": t.target_count,
            "completed_count": t.completed_count,
            "priority": t.priority,
            "status": t.status,
        })
    return {"plan_id": plan.id, "title": plan.title, "tasks": tasks}


@router.post("/tasks/{task_id}/start")
async def start_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Start a practice task."""
    return await service.start_task(db, task_id)


@router.post("/tasks/{task_id}/answer")
async def answer_question(
    task_id: str,
    body: AnswerRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Answer a practice question (immediate grading)."""
    return await service.answer_task_question(db, task_id, body.ptq_id, body.answer)


@router.post("/tasks/{task_id}/complete")
async def complete_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Complete a practice task."""
    return await service.complete_task(db, task_id)
