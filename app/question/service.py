"""Question service: CRUD, versioning, publish guard, search, review queue."""

from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Question, QuestionVersion
from app.question.schemas import QuestionCreate, QuestionUpdate


async def create_question(db: AsyncSession, data: QuestionCreate) -> Question:
    """Create a new question (draft)."""
    question = Question(
        section=data.section,
        type=data.type,
        skill=data.skill,
        difficulty=data.difficulty,
        status="draft",
    )
    db.add(question)
    await db.flush()

    # Create first version
    version = QuestionVersion(
        question_id=question.id,
        version_no=1,
        stem=data.stem,
        passage=data.passage,
        options=[c.model_dump() for c in data.options] if data.options else [],
        correct_answer=data.correct_answer,
        explanation=data.explanation,
    )
    db.add(version)
    await db.flush()

    question.current_version_id = version.id
    await db.commit()
    await db.refresh(question)
    return question


async def get_question(db: AsyncSession, question_id: str) -> Question:
    """Get a question by ID with current version."""
    result = await db.execute(
        select(Question).where(Question.id == question_id)
    )
    question = result.scalar_one_or_none()
    if question is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Question not found"},
        )
    # Load current version
    if question.current_version_id:
        vresult = await db.execute(
            select(QuestionVersion).where(QuestionVersion.id == question.current_version_id)
        )
        question.current_version = vresult.scalar_one_or_none()
    return question


async def update_question(
    db: AsyncSession, question_id: str, data: QuestionUpdate
) -> Question:
    """Update a question. Creates a new version if published."""
    question = await get_question(db, question_id)

    # Update metadata fields in-place
    if data.skill is not None:
        question.skill = data.skill
    if data.difficulty is not None:
        question.difficulty = data.difficulty

    # For content fields, create a new version if published
    content_changed = any(
        v is not None
        for v in [data.stem, data.passage, data.options, data.correct_answer, data.explanation]
    )

    if content_changed:
        # Get current version for baseline
        current_v = None
        if question.current_version_id:
            result = await db.execute(
                select(QuestionVersion).where(QuestionVersion.id == question.current_version_id)
            )
            current_v = result.scalar_one_or_none()

        new_version_no = (current_v.version_no + 1) if current_v else 1
        new_version = QuestionVersion(
            question_id=question.id,
            version_no=new_version_no,
            stem=data.stem if data.stem is not None else (current_v.stem if current_v else ""),
            passage=data.passage if data.passage is not None else (current_v.passage if current_v else None),
            options=(
                [c.model_dump() for c in data.options]
                if data.options is not None
                else (current_v.options if current_v else [])
            ),
            correct_answer=(
                data.correct_answer
                if data.correct_answer is not None
                else (current_v.correct_answer if current_v else "")
            ),
            explanation=(
                data.explanation
                if data.explanation is not None
                else (current_v.explanation if current_v else None)
            ),
        )
        db.add(new_version)
        await db.flush()
        question.current_version_id = new_version.id

    await db.commit()
    await db.refresh(question)
    return question


async def publish_question(db: AsyncSession, question_id: str) -> Question:
    """Publish a question. Requires skill + difficulty + correct_answer."""
    question = await get_question(db, question_id)

    # Get current version
    if question.current_version_id:
        vresult = await db.execute(
            select(QuestionVersion).where(QuestionVersion.id == question.current_version_id)
        )
        current_v = vresult.scalar_one_or_none()
    else:
        current_v = None

    # Validate publish requirements
    if not question.skill or not question.difficulty:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "QUESTION_INCOMPLETE",
                "message": "Skill and difficulty must be set before publishing",
            },
        )
    if not current_v or not current_v.correct_answer:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "QUESTION_INCOMPLETE",
                "message": "Correct answer must be set before publishing",
            },
        )

    question.status = "published"
    await db.commit()
    await db.refresh(question)
    return question


async def archive_question(db: AsyncSession, question_id: str) -> Question:
    """Archive a question (soft-delete)."""
    question = await get_question(db, question_id)
    question.status = "archived"
    await db.commit()
    await db.refresh(question)
    return question


async def delete_question(db: AsyncSession, question_id: str) -> None:
    """Delete a question. Blocked if referenced by any attempt."""
    question = await get_question(db, question_id)

    # Check if referenced by any attempt
    from app.models import AttemptQuestion
    result = await db.execute(
        select(func.count(AttemptQuestion.id)).where(
            AttemptQuestion.question_version_id.in_(
                select(QuestionVersion.id).where(QuestionVersion.question_id == question_id)
            )
        )
    )
    ref_count = result.scalar()
    if ref_count > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "REFERENCED_BY_ATTEMPT",
                "message": f"Cannot delete: referenced by {ref_count} exam attempt(s). Archive instead.",
            },
        )

    await db.delete(question)
    await db.commit()


async def list_questions(
    db: AsyncSession,
    section: Optional[str] = None,
    skill: Optional[str] = None,
    difficulty: Optional[str] = None,
    status: Optional[str] = None,
    type: Optional[str] = None,
    q: Optional[str] = None,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[Question], int]:
    """Search and filter questions with pagination."""
    query = select(Question)
    count_query = select(func.count(Question.id))

    if section:
        query = query.where(Question.section == section)
        count_query = count_query.where(Question.section == section)
    if skill:
        query = query.where(Question.skill == skill)
        count_query = count_query.where(Question.skill == skill)
    if difficulty:
        query = query.where(Question.difficulty == difficulty)
        count_query = count_query.where(Question.difficulty == difficulty)
    if status:
        query = query.where(Question.status == status)
        count_query = count_query.where(Question.status == status)
    if type:
        query = query.where(Question.type == type)
        count_query = count_query.where(Question.type == type)
    if q:
        # Search in stem via current_version
        search_filter = Question.current_version_id.in_(
            select(QuestionVersion.id).where(
                or_(
                    QuestionVersion.stem.ilike(f"%{q}%"),
                    QuestionVersion.passage.ilike(f"%{q}%"),
                )
            )
        )
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)

    # Get total
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # Get page
    result = await db.execute(
        query.order_by(Question.created_at.desc()).offset(offset).limit(limit)
    )
    questions = list(result.scalars().all())

    # Load current versions
    version_ids = [q.current_version_id for q in questions if q.current_version_id]
    if version_ids:
        vresult = await db.execute(
            select(QuestionVersion).where(QuestionVersion.id.in_(version_ids))
        )
        versions = {v.id: v for v in vresult.scalars().all()}
        for q in questions:
            q.current_version = versions.get(q.current_version_id)

    return questions, total


async def get_review_queue(
    db: AsyncSession, upload_id: Optional[str] = None
) -> list[Question]:
    """Get draft questions for review, sorted by confidence (lowest first)."""
    query = select(Question).where(Question.status == "draft")
    if upload_id:
        query = query.where(Question.source_upload_id == upload_id)
    query = query.order_by(Question.extraction_confidence.asc().nulls_first())

    result = await db.execute(query)
    return list(result.scalars().all())


async def bulk_update_status(
    db: AsyncSession, question_ids: list[str], new_status: str
) -> int:
    """Bulk update question status. Returns count of updated."""
    result = await db.execute(
        select(Question).where(Question.id.in_(question_ids))
    )
    questions = result.scalars().all()
    for q in questions:
        q.status = new_status
    await db.commit()
    return len(questions)


async def bulk_tag(
    db: AsyncSession, question_ids: list[str], skill: Optional[str], difficulty: Optional[str]
) -> int:
    """Bulk tag questions with skill/difficulty. Returns count of updated."""
    result = await db.execute(
        select(Question).where(Question.id.in_(question_ids))
    )
    questions = result.scalars().all()
    for q in questions:
        if skill is not None:
            q.skill = skill
        if difficulty is not None:
            q.difficulty = difficulty
    await db.commit()
    return len(questions)


async def get_skill_vocabulary(db: AsyncSession, section: Optional[str] = None):
    """Get skill vocabulary, optionally filtered by section."""
    from app.models import SkillVocabulary
    query = select(SkillVocabulary).order_by(SkillVocabulary.display_order)
    if section:
        query = query.where(SkillVocabulary.section == section)
    result = await db.execute(query)
    return list(result.scalars().all())
