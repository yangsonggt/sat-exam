"""Practice plan and execution service."""

from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    PracticePlan,
    PracticeTask,
    PracticeTaskQuestion,
    PracticeAnswer,
    Attempt,
    AttemptQuestion,
    AttemptResult,
    Question,
    QuestionVersion,
)


async def generate_plan(
    db: AsyncSession, user_id: str, attempt_id: str, target_days: int = 28
) -> PracticePlan:
    """Generate a practice plan from an attempt's weak skills."""
    # Get attempt analysis
    result = await db.execute(
        select(AttemptResult).where(AttemptResult.attempt_id == attempt_id)
    )
    analysis = result.scalar_one_or_none()
    if analysis is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND", "message": "Attempt analysis not found"},
        )

    weak_skills: dict = analysis.weak_skills or {}
    if not weak_skills:
        raise HTTPException(
            status_code=400,
            detail={"code": "NO_WEAK_SKILLS", "message": "No weak skills detected in this attempt"},
        )

    # Get source attempt's used question IDs to exclude them
    used_qs = await db.execute(
        select(AttemptQuestion.question_version_id).where(
            AttemptQuestion.attempt_id == attempt_id
        )
    )
    used_version_ids = {row[0] for row in used_qs.all()}

    # Create plan
    plan = PracticePlan(
        user_id=user_id,
        source_attempt_id=attempt_id,
        title=f"Practice Plan",
        status="active",
    )
    db.add(plan)
    await db.flush()

    # Sort skills by accuracy (worst first)
    sorted_skills = sorted(weak_skills.items(), key=lambda x: x[1])
    for priority, (skill_key, accuracy) in enumerate(sorted_skills):
        if accuracy >= 60:
            continue  # Skip skills above threshold

        target = max(5, int((60 - accuracy) * 3))  # More questions for weaker skills

        # Find published questions for this skill
        q_result = await db.execute(
            select(Question).where(
                Question.status == "published",
                Question.skill == skill_key,
                ~Question.current_version_id.in_(used_version_ids) if used_version_ids else True,
            ).limit(target * 2)
        )
        available = list(q_result.scalars().all())

        if not available:
            # Gap: no questions available
            continue

        picked = available[:min(target, len(available))]

        task = PracticeTask(
            plan_id=plan.id,
            skill=skill_key,
            difficulty=None,
            target_count=len(picked),
            priority=priority,
            status="pending",
        )
        db.add(task)
        await db.flush()

        for order, q in enumerate(picked):
            ptq = PracticeTaskQuestion(
                task_id=task.id,
                question_version_id=q.current_version_id,
                question_order=order,
            )
            db.add(ptq)

    await db.commit()
    await db.refresh(plan)
    return plan


async def get_plan(db: AsyncSession, plan_id: str) -> PracticePlan:
    result = await db.execute(select(PracticePlan).where(PracticePlan.id == plan_id))
    plan = result.scalar_one_or_none()
    if plan is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND"})
    return plan


async def list_plans(db: AsyncSession, user_id: str) -> list[PracticePlan]:
    result = await db.execute(
        select(PracticePlan)
        .where(PracticePlan.user_id == user_id)
        .order_by(PracticePlan.created_at.desc())
    )
    return list(result.scalars().all())


async def start_task(db: AsyncSession, task_id: str) -> dict:
    """Start a practice task, return first question."""
    result = await db.execute(select(PracticeTask).where(PracticeTask.id == task_id))
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND"})

    task.status = "in_progress"
    await db.commit()

    # Get first question
    ptq_result = await db.execute(
        select(PracticeTaskQuestion)
        .where(PracticeTaskQuestion.task_id == task_id)
        .order_by(PracticeTaskQuestion.question_order)
        .limit(1)
    )
    first = ptq_result.scalar_one_or_none()
    if first is None:
        raise HTTPException(status_code=404, detail={"code": "NO_QUESTIONS"})

    vresult = await db.execute(
        select(QuestionVersion).where(QuestionVersion.id == first.question_version_id)
    )
    version = vresult.scalar_one_or_none()

    return {
        "task_id": task.id,
        "skill": task.skill,
        "total_questions": task.target_count,
        "first_question": {
            "ptq_id": first.id,
            "type": "multiple_choice" if (version and version.options) else "grid_in",
            "stem": version.stem if version else "",
            "options": version.options if version else None,
        },
    }


async def answer_task_question(
    db: AsyncSession, task_id: str, ptq_id: str, answer: str
) -> dict:
    """Grade an answer immediately (practice mode)."""
    # Get the task question
    result = await db.execute(
        select(PracticeTaskQuestion).where(PracticeTaskQuestion.id == ptq_id)
    )
    ptq = result.scalar_one_or_none()
    if ptq is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND"})

    # Get correct answer
    vresult = await db.execute(
        select(QuestionVersion).where(QuestionVersion.id == ptq.question_version_id)
    )
    version = vresult.scalar_one_or_none()
    is_correct = (answer.strip().upper() == version.correct_answer.strip().upper()) if version else False

    # Upsert answer
    ans_result = await db.execute(
        select(PracticeAnswer).where(PracticeAnswer.practice_task_question_id == ptq_id)
    )
    existing = ans_result.scalar_one_or_none()
    if existing:
        existing.answer = answer
        existing.is_correct = is_correct
    else:
        db.add(PracticeAnswer(
            practice_task_question_id=ptq_id,
            answer=answer,
            is_correct=is_correct,
        ))

    # Update task progress
    count_result = await db.execute(
        select(func.count(PracticeAnswer.id)).where(
            PracticeAnswer.practice_task_question_id.in_(
                select(PracticeTaskQuestion.id).where(PracticeTaskQuestion.task_id == task_id)
            )
        )
    )
    completed = count_result.scalar()

    task_result = await db.execute(select(PracticeTask).where(PracticeTask.id == task_id))
    task = task_result.scalar_one_or_none()
    if task:
        task.completed_count = completed

    await db.commit()

    return {
        "is_correct": is_correct,
        "correct_answer": version.correct_answer if version else "",
        "explanation": version.explanation if version else "",
        "completed": completed,
        "total": task.target_count if task else 0,
    }


async def complete_task(db: AsyncSession, task_id: str) -> dict:
    """Mark a task as complete."""
    result = await db.execute(select(PracticeTask).where(PracticeTask.id == task_id))
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404)

    task.status = "completed"
    await db.commit()
    return {"ok": True, "task_id": task_id}
