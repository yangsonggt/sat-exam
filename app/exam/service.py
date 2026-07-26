"""Exam blueprint service: CRUD, pool validation, selection rules."""

from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Exam,
    ExamModule,
    ExamSelectionRule,
    Question,
)
from sqlalchemy.orm import selectinload
from app.exam.schemas import ExamCreate, ExamUpdate


async def create_exam(db: AsyncSession, data: ExamCreate, user_id: str) -> Exam:
    """Create an exam blueprint with modules and selection rules."""
    exam = Exam(
        title=data.title,
        description=data.description,
        routing_threshold_rw=data.routing_threshold_rw,
        routing_threshold_math=data.routing_threshold_math,
        timer_mode=data.timer_mode,
        created_by=user_id,
        status="draft",
    )
    db.add(exam)
    await db.flush()

    for mod_data in data.modules:
        module = ExamModule(
            exam_id=exam.id,
            section=mod_data.section,
            module_no=mod_data.module_no,
            form=mod_data.form,
            time_limit_min=mod_data.time_limit_min,
            question_count=mod_data.question_count,
        )
        db.add(module)
        await db.flush()

        for rule_data in mod_data.selection_rules:
            rule = ExamSelectionRule(
                exam_module_id=module.id,
                skill=rule_data.skill,
                difficulty=rule_data.difficulty,
                count=rule_data.count,
            )
            db.add(rule)

    await db.commit()
    await db.refresh(exam)
    return exam


async def get_exam(db: AsyncSession, exam_id: str) -> Exam:
    """Get an exam by ID with modules and selection rules."""
    result = await db.execute(
        select(Exam)
        .options(selectinload(Exam.modules).selectinload(ExamModule.selection_rules))
        .where(Exam.id == exam_id)
    )
    exam = result.scalar_one_or_none()
    if exam is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Exam not found"},
        )
    return exam


async def list_exams(
    db: AsyncSession, status_filter: Optional[str] = None,
    offset: int = 0, limit: int = 50,
) -> tuple[list[Exam], int]:
    """List exams with pagination."""
    count_q = select(func.count(Exam.id))
    q = select(Exam)

    if status_filter:
        count_q = count_q.where(Exam.status == status_filter)
        q = q.where(Exam.status == status_filter)

    total_result = await db.execute(count_q)
    total = total_result.scalar()

    result = await db.execute(
        q.order_by(Exam.created_at.desc()).offset(offset).limit(limit)
    )
    return list(result.scalars().all()), total


async def validate_publish(db: AsyncSession, exam_id: str) -> list[dict]:
    """Check that every module's selection rules can be satisfied by the published pool.
    
    Returns list of validation errors (empty = all good).
    """
    exam = await get_exam(db, exam_id)
    errors = []

    for module in exam.modules:
        for rule in module.selection_rules:
            # Count published questions matching the rule
            query = select(func.count(Question.id)).where(
                Question.status == "published",
                Question.section == module.section,
            )
            if rule.skill:
                query = query.where(Question.skill == rule.skill)
            if rule.difficulty:
                query = query.where(Question.difficulty == rule.difficulty)

            result = await db.execute(query)
            available = result.scalar()

            if available < rule.count:
                errors.append({
                    "module": f"{module.section}_m{module.module_no}_{module.form}",
                    "rule": {
                        "skill": rule.skill,
                        "difficulty": rule.difficulty,
                        "required": rule.count,
                        "available": available,
                    },
                })

    return errors


async def publish_exam(db: AsyncSession, exam_id: str) -> Exam:
    """Validate pool sufficiency, then publish the exam."""
    errors = await validate_publish(db, exam_id)
    if errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "POOL_INSUFFICIENT",
                "message": "Some selection rules cannot be satisfied by the published question pool",
                "errors": errors,
            },
        )

    exam = await get_exam(db, exam_id)
    exam.status = "published"
    await db.commit()
    await db.refresh(exam)
    return exam


async def update_exam(db: AsyncSession, exam_id: str, data: ExamUpdate) -> Exam:
    """Update exam metadata."""
    exam = await get_exam(db, exam_id)
    if data.title is not None:
        exam.title = data.title
    if data.description is not None:
        exam.description = data.description
    if data.routing_threshold_rw is not None:
        exam.routing_threshold_rw = data.routing_threshold_rw
    if data.routing_threshold_math is not None:
        exam.routing_threshold_math = data.routing_threshold_math
    if data.timer_mode is not None:
        exam.timer_mode = data.timer_mode
    await db.commit()
    await db.refresh(exam)
    return exam


async def delete_exam(db: AsyncSession, exam_id: str) -> None:
    """Delete an exam. Blocked if it has attempts."""
    exam = await get_exam(db, exam_id)

    from app.models import Attempt
    result = await db.execute(
        select(func.count(Attempt.id)).where(Attempt.exam_id == exam_id)
    )
    attempt_count = result.scalar()
    if attempt_count > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "HAS_ATTEMPTS",
                "message": f"Cannot delete: exam has {attempt_count} attempt(s)",
            },
        )

    await db.delete(exam)
    await db.commit()
