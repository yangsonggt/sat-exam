"""Exam runtime: attempt orchestration, adaptive routing, auto-save, grading.

This implements the section-adaptive Digital SAT engine described in DETAILED_DESIGN §2.
"""

import hashlib
import math
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Attempt,
    AttemptQuestion,
    AttemptAnswer,
    Exam,
    ExamModule,
    Question,
    QuestionVersion,
    ScoreConversion,
    AttemptResult,
)

# Section completion order for Digital SAT
SECTION_ORDER = ["rw", "math"]

# State machine transitions
STATE_TRANSITIONS = {
    "created": {
        "start_rw": "rw_m1_active",
    },
    "rw_m1_active": {
        "submit": "rw_routing",   # transient → immediately routes to M2
    },
    "rw_routing": {
        "route_harder": "rw_m2_active",
        "route_easier": "rw_m2_active",
    },
    "rw_m2_active": {
        "submit": "math_m1_active",
    },
    "math_m1_active": {
        "submit": "math_routing",
    },
    "math_routing": {
        "route_harder": "math_m2_active",
        "route_easier": "math_m2_active",
    },
    "math_m2_active": {
        "submit": "grading",
    },
    "grading": {
        "finish": "submitted",
    },
}


def _deterministic_sample(pool: list, count: int, seed: str) -> list:
    """Deterministic sample from pool using seed hash (for crash recovery)."""
    import random
    rng = random.Random(int(hashlib.md5(seed.encode()).hexdigest(), 16))
    if count >= len(pool):
        return list(pool)
    return rng.sample(pool, count)


async def start_attempt(db: AsyncSession, user_id: str, exam_id: str) -> Attempt:
    """Start a new exam attempt. Materializes R&W Module 1."""
    # Check no active attempt exists
    result = await db.execute(
        select(Attempt).where(
            Attempt.student_id == user_id,
            Attempt.exam_id == exam_id,
            Attempt.status.notin_(["submitted"]),
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "ALREADY_STARTED", "message": "You already have an active attempt for this exam"},
        )

    # Get exam
    exam_result = await db.execute(select(Exam).where(Exam.id == exam_id))
    exam = exam_result.scalar_one_or_none()
    if exam is None or exam.status != "published":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Exam not found or not published"},
        )

    # Create attempt
    attempt = Attempt(
        exam_id=exam_id,
        student_id=user_id,
        status="rw_m1_active",
        started_at=datetime.now(timezone.utc),
        module_starts={"rw_m1": datetime.now(timezone.utc).isoformat()},
    )
    db.add(attempt)
    await db.flush()

    # Materialize R&W Module 1
    rw_m1 = await _get_module(db, exam_id, "reading_writing", 1, "base")
    if rw_m1 is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "MISSING_MODULE", "message": "R&W Module 1 not found in exam blueprint"},
        )

    await _materialize_module(db, attempt.id, rw_m1)
    await db.commit()
    await db.refresh(attempt)
    return attempt


async def _get_module(
    db: AsyncSession, exam_id: str, section: str, module_no: int, form: str
) -> Optional[ExamModule]:
    """Get a specific exam module."""
    result = await db.execute(
        select(ExamModule).where(
            ExamModule.exam_id == exam_id,
            ExamModule.section == section,
            ExamModule.module_no == module_no,
            ExamModule.form == form,
        )
    )
    return result.scalar_one_or_none()


async def _materialize_module(
    db: AsyncSession, attempt_id: str, module: ExamModule
):
    """Run selection rules to pick questions and snapshot into attempt_questions."""
    for rule in module.selection_rules:
        # Query published questions matching the rule
        query = select(Question).where(
            Question.status == "published",
            Question.section == module.section,
        )
        if rule.skill:
            query = query.where(Question.skill == rule.skill)
        if rule.difficulty:
            query = query.where(Question.difficulty == rule.difficulty)

        result = await db.execute(query)
        questions = list(result.scalars().all())

        if len(questions) < rule.count:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "code": "POOL_INSUFFICIENT",
                    "message": f"Not enough published questions for rule: "
                               f"skill={rule.skill}, difficulty={rule.difficulty}, "
                               f"need={rule.count}, have={len(questions)}",
                },
            )

        # Deterministic sample
        seed = f"{attempt_id}:{module.id}:{rule.id}"
        chosen = _deterministic_sample(questions, rule.count, seed)

        for order, question in enumerate(chosen):
            # Get current version
            if question.current_version_id:
                aq = AttemptQuestion(
                    attempt_id=attempt_id,
                    question_version_id=question.current_version_id,
                    section=module.section,
                    module_no=module.module_no,
                    form=module.form,
                    question_order=order,
                )
                db.add(aq)


async def get_attempt_state(db: AsyncSession, attempt_id: str) -> dict:
    """Get full attempt state for rehydration (DETAILED_DESIGN §7.1)."""
    result = await db.execute(select(Attempt).where(Attempt.id == attempt_id))
    attempt = result.scalar_one_or_none()
    if attempt is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Attempt not found"},
        )

    # Parse state to determine current section/module
    state = attempt.status
    section = None
    module_no = None
    form = None

    state_to_meta = {
        "rw_m1_active": ("rw", 1, "base"),
        "rw_m2_active": ("rw", 2, attempt.routing.get("rw", {}).get("chosen_form", "easier")),
        "math_m1_active": ("math", 1, "base"),
        "math_m2_active": ("math", 2, attempt.routing.get("math", {}).get("chosen_form", "easier")),
    }

    if state in state_to_meta:
        section, module_no, form = state_to_meta[state]

        # Compute remaining time
        module_key = f"{section}_m{module_no}"
        started_str = attempt.module_starts.get(module_key)
        remaining_ms = None
        total_ms = None
        exam_module = await _get_module(db, attempt.exam_id,
                                         "reading_writing" if section == "rw" else "math",
                                         module_no, form)
        if started_str and exam_module:
                try:
                    started_at = datetime.fromisoformat(started_str)
                    elapsed = (datetime.now(timezone.utc) - started_at).total_seconds()
                    total_ms = exam_module.time_limit_min * 60 * 1000
                    remaining_ms = max(0, total_ms - int(elapsed * 1000))
                except (ValueError, TypeError):
                    remaining_ms = None

        # Load questions for current module
        aq_result = await db.execute(
            select(AttemptQuestion)
            .where(
                AttemptQuestion.attempt_id == attempt_id,
                AttemptQuestion.section == ("reading_writing" if section == "rw" else "math"),
                AttemptQuestion.module_no == module_no,
                AttemptQuestion.form == form,
            )
            .order_by(AttemptQuestion.question_order)
        )
        attempt_questions = list(aq_result.scalars().all())

        questions_data = []
        answered_count = 0
        marked_count = 0

        for aq in attempt_questions:
            # Get question version
            vresult = await db.execute(
                select(QuestionVersion).where(QuestionVersion.id == aq.question_version_id)
            )
            version = vresult.scalar_one_or_none()

            # Get student's answer
            aresult = await db.execute(
                select(AttemptAnswer).where(AttemptAnswer.attempt_question_id == aq.id)
            )
            answer = aresult.scalar_one_or_none()

            q_data = {
                "aq_id": aq.id,
                "type": "multiple_choice" if (version and version.options) else "grid_in",
                "stem": version.stem if version else "",
                "passage": version.passage if version else None,
                "options": version.options if version else None,
                "your_answer": answer.answer if answer else None,
                "marked": False,  # We don't store marked separately (could add)
            }
            if answer:
                answered_count += 1
            questions_data.append(q_data)

        return {
            "id": attempt.id,
            "exam_id": attempt.exam_id,
            "state": state,
            "section": section,
            "module_no": module_no,
            "form": form,
            "remaining_ms": remaining_ms,
            "total_ms": exam_module.time_limit_min * 60 * 1000 if exam_module else None,
            "questions": questions_data,
            "question_palette": {
                "answered": answered_count,
                "unanswered": len(attempt_questions) - answered_count,
                "marked": marked_count,
                "total": len(attempt_questions),
            },
        }

    # Non-active states
    return {
        "id": attempt.id,
        "exam_id": attempt.exam_id,
        "state": state,
        "questions": [],
    }


async def save_answer(
    db: AsyncSession, attempt_id: str, aq_id: str, answer: str, marked: bool = False
) -> dict:
    """Auto-save an answer (DETAILED_DESIGN §7.2)."""
    # Validate attempt is active
    result = await db.execute(select(Attempt).where(Attempt.id == attempt_id))
    attempt = result.scalar_one_or_none()
    if attempt is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Attempt not found"})

    if not attempt.status.endswith("_active"):
        raise HTTPException(
            status_code=409,
            detail={"code": "ATTEMPT_NOT_ACTIVE", "message": "Attempt is not in an active module state"},
        )

    # Validate attempt_question belongs to this attempt
    aq_result = await db.execute(
        select(AttemptQuestion).where(
            AttemptQuestion.id == aq_id,
            AttemptQuestion.attempt_id == attempt_id,
        )
    )
    aq = aq_result.scalar_one_or_none()
    if aq is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND", "message": "Question not found in this attempt"},
        )

    # Upsert answer
    ans_result = await db.execute(
        select(AttemptAnswer).where(AttemptAnswer.attempt_question_id == aq_id)
    )
    existing = ans_result.scalar_one_or_none()

    if existing:
        existing.answer = answer
        existing.answered_at = datetime.now(timezone.utc)
    else:
        new_ans = AttemptAnswer(
            attempt_question_id=aq_id,
            answer=answer,
            answered_at=datetime.now(timezone.utc),
        )
        db.add(new_ans)

    await db.commit()

    # Count unanswered
    unanswered_result = await db.execute(
        select(func.count(AttemptQuestion.id)).where(
            AttemptQuestion.attempt_id == attempt_id,
            ~AttemptQuestion.id.in_(
                select(AttemptAnswer.attempt_question_id).where(
                    AttemptAnswer.attempt_question_id.in_(
                        select(AttemptQuestion.id).where(AttemptQuestion.attempt_id == attempt_id)
                    )
                )
            ),
        )
    )
    unanswered = unanswered_result.scalar()

    return {"saved": True, "unanswered": unanswered}


async def submit_module(db: AsyncSession, attempt_id: str) -> dict:
    """Submit current module: grade, route (if M1), advance to next module (DETAILED_DESIGN §7.3)."""
    result = await db.execute(select(Attempt).where(Attempt.id == attempt_id))
    attempt = result.scalar_one_or_none()
    if attempt is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND"})

    current_state = attempt.status

    if current_state not in ("rw_m1_active", "rw_m2_active", "math_m1_active", "math_m2_active"):
        raise HTTPException(
            status_code=409,
            detail={"code": "ATTEMPT_NOT_ACTIVE", "message": f"Cannot submit from state '{current_state}'"},
        )

    # Determine section and module
    is_m1 = current_state in ("rw_m1_active", "math_m1_active")
    section_key = current_state.split("_")[0]  # "rw" or "math"
    section_full = "reading_writing" if section_key == "rw" else "math"
    module_no = 1 if is_m1 else 2

    # Get exam for routing threshold
    exam_result = await db.execute(select(Exam).where(Exam.id == attempt.exam_id))
    exam = exam_result.scalar_one_or_none()

    # Get the form
    form = "base" if is_m1 else attempt.routing.get(section_key, {}).get("chosen_form", "easier")

    # Grade current module
    aq_result = await db.execute(
        select(AttemptQuestion).where(
            AttemptQuestion.attempt_id == attempt_id,
            AttemptQuestion.section == section_full,
            AttemptQuestion.module_no == module_no,
            AttemptQuestion.form == form,
        )
    )
    attempt_questions = list(aq_result.scalars().all())

    correct_count = 0
    for aq in attempt_questions:
        ans_result = await db.execute(
            select(AttemptAnswer).where(AttemptAnswer.attempt_question_id == aq.id)
        )
        ans = ans_result.scalar_one_or_none()

        if ans and ans.answer:
            # Get correct answer from question version
            vresult = await db.execute(
                select(QuestionVersion).where(QuestionVersion.id == aq.question_version_id)
            )
            version = vresult.scalar_one_or_none()

            if version:
                is_correct = (ans.answer.strip().upper() == version.correct_answer.strip().upper())
                ans.is_correct = is_correct
                if is_correct:
                    correct_count += 1
            else:
                ans.is_correct = False
        else:
            # Unanswered
            if ans is None:
                ans = AttemptAnswer(
                    attempt_question_id=aq.id,
                    answer=None,
                    is_correct=False,
                )
                db.add(ans)

    await db.flush()

    response = {
        "module": f"{section_key}_m{module_no}",
        "m1_score" if is_m1 else "m2_score": correct_count,
        "total": len(attempt_questions),
    }

    if is_m1:
        # Route to M2
        threshold = getattr(exam, f"routing_threshold_{section_key}") or math.ceil(len(attempt_questions) / 2)
        chosen_form = "harder" if correct_count >= threshold else "easier"

        # Record routing decision
        routing = dict(attempt.routing)
        routing[section_key] = {
            "m1_score": correct_count,
            "threshold": threshold,
            "chosen_form": chosen_form,
        }
        attempt.routing = routing

        response["threshold"] = threshold
        response["chosen_form"] = chosen_form

        # Materialize M2 of the chosen form
        m2_module = await _get_module(db, attempt.exam_id, section_full, 2, chosen_form)
        if m2_module:
            await _materialize_module(db, attempt_id, m2_module)

        # Record M2 start time
        module_starts = dict(attempt.module_starts)
        module_starts[f"{section_key}_m2"] = datetime.now(timezone.utc).isoformat()
        attempt.module_starts = module_starts

        # Advance state
        attempt.status = f"{section_key}_m2_active"
        response["next_state"] = f"{section_key}_m2_active"

    else:
        # M2 submitted — advance to next section or finish
        if section_key == "rw":
            # Advance to Math M1
            m1_module = await _get_module(db, attempt.exam_id, "math", 1, "base")
            if m1_module:
                await _materialize_module(db, attempt_id, m1_module)

            module_starts = dict(attempt.module_starts)
            module_starts["math_m1"] = datetime.now(timezone.utc).isoformat()
            attempt.module_starts = module_starts

            attempt.status = "math_m1_active"
            response["next_state"] = "math_m1_active"
        else:
            # Math M2 — final scoring
            attempt.status = "submitted"
            attempt.submitted_at = datetime.now(timezone.utc)
            response["next_state"] = "submitted"

            # Trigger scoring
            await _score_attempt(db, attempt, exam)

            response["result_url"] = f"/api/v1/attempts/{attempt_id}/analysis"

    await db.commit()
    return response


async def _score_attempt(db: AsyncSession, attempt: Attempt, exam: Exam):
    """Compute raw and scaled scores, create AttemptResult."""
    # Count correct per section
    rw_correct = 0
    math_correct = 0

    all_aqs_result = await db.execute(
        select(AttemptQuestion).where(AttemptQuestion.attempt_id == attempt.id)
    )
    for aq in all_aqs_result.scalars().all():
        ans_result = await db.execute(
            select(AttemptAnswer).where(AttemptAnswer.attempt_question_id == aq.id)
        )
        ans = ans_result.scalar_one_or_none()
        if ans and ans.is_correct:
            if aq.section == "reading_writing":
                rw_correct += 1
            else:
                math_correct += 1

    # Look up scaled scores from conversion tables
    rw_form = attempt.routing.get("rw", {}).get("chosen_form", "easier")
    math_form = attempt.routing.get("math", {}).get("chosen_form", "easier")

    rw_scaled = await _lookup_scaled(db, "reading_writing", rw_form, rw_correct)
    math_scaled = await _lookup_scaled(db, "math", math_form, math_correct)

    attempt.raw_rw = rw_correct
    attempt.scaled_rw = rw_scaled
    attempt.raw_math = math_correct
    attempt.scaled_math = math_scaled
    attempt.scaled_total = (rw_scaled or 200) + (math_scaled or 200)

    # Create result record
    result = AttemptResult(
        attempt_id=attempt.id,
        domain_breakdown={},
        difficulty_breakdown={},
        weak_skills={},
    )
    db.add(result)


async def _lookup_scaled(
    db: AsyncSession, section: str, form: str, raw: int
) -> Optional[int]:
    """Look up scaled score from conversions table."""
    result = await db.execute(
        select(ScoreConversion.scaled_score).where(
            ScoreConversion.section == section,
            ScoreConversion.module2_form == form,
            ScoreConversion.raw_score == raw,
        )
    )
    scaled = result.scalar_one_or_none()
    if scaled is None:
        # Fallback: linear approximation for missing conversion data
        max_raw = 54 if section == "reading_writing" else 44
        scaled = round(200 + (raw / max_raw) * 600)
    return scaled
