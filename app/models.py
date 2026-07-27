"""All SQLAlchemy ORM models for the SAT Exam System."""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def new_uuid() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.utcnow()


# ═══════════════════════════════════════════════════════════
# Auth
# ═══════════════════════════════════════════════════════════

class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="student")  # admin, editor, student
    display_name: Mapped[Optional[str]] = mapped_column(String(100))
    grade: Mapped[Optional[str]] = mapped_column(String(50))
    school: Mapped[Optional[str]] = mapped_column(String(200))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    # Relationships
    uploads = relationship("Upload", back_populates="uploader")
    exams_created = relationship("Exam", back_populates="creator")
    attempts = relationship("Attempt", back_populates="student", foreign_keys="Attempt.student_id")
    practice_plans = relationship("PracticePlan", back_populates="student")


# ═══════════════════════════════════════════════════════════
# Upload
# ═══════════════════════════════════════════════════════════

class Upload(Base):
    __tablename__ = "uploads"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_uuid)
    uploader_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(1000), nullable=False)
    checksum: Mapped[Optional[str]] = mapped_column(String(64), unique=True)
    file_size: Mapped[Optional[int]] = mapped_column(Integer)
    mime_type: Mapped[Optional[str]] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), default="uploaded")  # uploaded, parsing, parsed, failed
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    uploader = relationship("User", back_populates="uploads")
    parse_jobs = relationship("ParseJob", back_populates="upload")
    questions = relationship("Question", back_populates="source_upload")


class ParseJob(Base):
    __tablename__ = "parse_jobs"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_uuid)
    upload_id: Mapped[str] = mapped_column(ForeignKey("uploads.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending, running, done, failed
    error: Mapped[Optional[str]] = mapped_column(Text)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    upload = relationship("Upload", back_populates="parse_jobs")


class ParseActivity(Base):
    """Persistent record of background OCR parse jobs (survives server restart)."""
    __tablename__ = "parse_activities"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_uuid)
    job_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    filename: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20), default="saving")  # saving, parsing, importing, done, error
    error: Mapped[Optional[str]] = mapped_column(Text)
    questions_parsed: Mapped[Optional[int]] = mapped_column(Integer)
    questions_imported: Mapped[Optional[int]] = mapped_column(Integer)
    questions_skipped: Mapped[Optional[int]] = mapped_column(Integer)
    answers_matched: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, onupdate=utcnow)


# ═══════════════════════════════════════════════════════════
# Questions (with versioning)
# ═══════════════════════════════════════════════════════════

class Question(Base):
    __tablename__ = "questions"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_uuid)
    section: Mapped[str] = mapped_column(String(20), nullable=False)  # reading_writing, math
    type: Mapped[str] = mapped_column(String(20), nullable=False)  # multiple_choice, grid_in
    skill: Mapped[Optional[str]] = mapped_column(String(100))  # editor-assigned at review
    difficulty: Mapped[Optional[str]] = mapped_column(String(10))  # easy, medium, hard
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")  # draft, saved, reviewed, published, archived
    source_upload_id: Mapped[Optional[str]] = mapped_column(ForeignKey("uploads.id"))
    current_version_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False))
    extraction_confidence: Mapped[Optional[float]] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    source_upload = relationship("Upload", back_populates="questions")
    versions = relationship("QuestionVersion", back_populates="question",
                            order_by="QuestionVersion.version_no")


class QuestionVersion(Base):
    __tablename__ = "question_versions"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_uuid)
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"), nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    stem: Mapped[str] = mapped_column(Text, nullable=False)
    passage: Mapped[Optional[str]] = mapped_column(Text)
    options: Mapped[dict] = mapped_column(JSON, nullable=False)  # [{"label":"A","text":"..."}]
    correct_answer: Mapped[str] = mapped_column(String(50), nullable=False)
    explanation: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    question = relationship("Question", back_populates="versions")

    __table_args__ = (
        UniqueConstraint("question_id", "version_no", name="uq_question_version"),
    )


class SkillVocabulary(Base):
    __tablename__ = "skill_vocabulary"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    section: Mapped[str] = mapped_column(String(20), nullable=False)
    domain_key: Mapped[str] = mapped_column(String(100), nullable=False)
    domain_label: Mapped[str] = mapped_column(String(200), nullable=False)
    skill_key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    skill_label: Mapped[str] = mapped_column(String(200), nullable=False)
    display_order: Mapped[Optional[int]] = mapped_column(Integer)


# ═══════════════════════════════════════════════════════════
# Exams (blueprint model)
# ═══════════════════════════════════════════════════════════

class Exam(Base):
    __tablename__ = "exams"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_uuid)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")  # draft, saved, reviewed, published, archived
    routing_threshold_rw: Mapped[Optional[float]] = mapped_column(Float)
    routing_threshold_math: Mapped[Optional[float]] = mapped_column(Float)
    timer_mode: Mapped[str] = mapped_column(String(20), default="strict")  # strict, optional
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    creator = relationship("User", back_populates="exams_created")
    modules = relationship("ExamModule", back_populates="exam")
    attempts = relationship("Attempt", back_populates="exam")


class ExamModule(Base):
    __tablename__ = "exam_modules"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_uuid)
    exam_id: Mapped[str] = mapped_column(ForeignKey("exams.id", ondelete="CASCADE"), nullable=False)
    section: Mapped[str] = mapped_column(String(20), nullable=False)  # reading_writing, math
    module_no: Mapped[int] = mapped_column(Integer, nullable=False)  # 1 (routing) or 2 (adaptive)
    form: Mapped[str] = mapped_column(String(10), default="base")  # base, easier, harder
    time_limit_min: Mapped[int] = mapped_column(Integer, nullable=False)
    question_count: Mapped[int] = mapped_column(Integer, nullable=False)

    exam = relationship("Exam", back_populates="modules")
    selection_rules = relationship("ExamSelectionRule", back_populates="module")

    __table_args__ = (
        UniqueConstraint("exam_id", "section", "module_no", "form", name="uq_exam_module"),
    )


class ExamSelectionRule(Base):
    __tablename__ = "exam_selection_rules"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_uuid)
    exam_module_id: Mapped[str] = mapped_column(
        ForeignKey("exam_modules.id", ondelete="CASCADE"), nullable=False
    )
    skill: Mapped[Optional[str]] = mapped_column(String(100))
    difficulty: Mapped[Optional[str]] = mapped_column(String(10))
    count: Mapped[int] = mapped_column(Integer, nullable=False)

    module = relationship("ExamModule", back_populates="selection_rules")


# ═══════════════════════════════════════════════════════════
# Attempts
# ═══════════════════════════════════════════════════════════

class Attempt(Base):
    __tablename__ = "attempts"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_uuid)
    exam_id: Mapped[str] = mapped_column(ForeignKey("exams.id"), nullable=False)
    student_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="in_progress")
    # Detailed state for section-adaptive engine: created, rw_m1_active, rw_routing,
    # rw_m2_active, math_m1_active, math_routing, math_m2_active, grading, submitted
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    # Module start times as JSON: {"rw_m1":"2026-...", "rw_m2":"2026-...", ...}
    module_starts: Mapped[dict] = mapped_column(JSON, default=dict)
    # Routing decisions: {"rw":{"m1_score":19,"threshold":14,"chosen_form":"harder"}, ...}
    routing: Mapped[dict] = mapped_column(JSON, default=dict)
    # Final scores
    raw_rw: Mapped[Optional[int]] = mapped_column(Integer)
    scaled_rw: Mapped[Optional[int]] = mapped_column(Integer)
    raw_math: Mapped[Optional[int]] = mapped_column(Integer)
    scaled_math: Mapped[Optional[int]] = mapped_column(Integer)
    scaled_total: Mapped[Optional[int]] = mapped_column(Integer)

    exam = relationship("Exam", back_populates="attempts")
    student = relationship("User", back_populates="attempts", foreign_keys=[student_id])
    questions = relationship("AttemptQuestion", back_populates="attempt")
    result = relationship("AttemptResult", back_populates="attempt", uselist=False)

    __table_args__ = (
        UniqueConstraint("student_id", "exam_id", name="uq_active_attempt"),
    )


class AttemptQuestion(Base):
    __tablename__ = "attempt_questions"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_uuid)
    attempt_id: Mapped[str] = mapped_column(
        ForeignKey("attempts.id", ondelete="CASCADE"), nullable=False
    )
    question_version_id: Mapped[str] = mapped_column(
        ForeignKey("question_versions.id"), nullable=False
    )
    section: Mapped[str] = mapped_column(String(20), nullable=False)
    module_no: Mapped[int] = mapped_column(Integer, nullable=False)
    form: Mapped[str] = mapped_column(String(10), nullable=False)
    question_order: Mapped[int] = mapped_column(Integer, nullable=False)

    attempt = relationship("Attempt", back_populates="questions")
    answer = relationship("AttemptAnswer", back_populates="attempt_question", uselist=False)


class AttemptAnswer(Base):
    __tablename__ = "attempt_answers"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_uuid)
    attempt_question_id: Mapped[str] = mapped_column(
        ForeignKey("attempt_questions.id", ondelete="CASCADE"), nullable=False
    )
    answer: Mapped[Optional[str]] = mapped_column(String(50))
    is_correct: Mapped[Optional[bool]] = mapped_column(Boolean)
    time_spent_sec: Mapped[Optional[int]] = mapped_column(Integer)
    answered_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    attempt_question = relationship("AttemptQuestion", back_populates="answer")

    __table_args__ = (
        UniqueConstraint("attempt_question_id", name="uq_attempt_answer"),
    )


# ═══════════════════════════════════════════════════════════
# Results
# ═══════════════════════════════════════════════════════════

class ScoreConversion(Base):
    __tablename__ = "score_conversions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    section: Mapped[str] = mapped_column(String(20), nullable=False)
    module2_form: Mapped[str] = mapped_column(String(10), nullable=False)  # easier, harder
    raw_score: Mapped[int] = mapped_column(Integer, nullable=False)
    scaled_score: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        UniqueConstraint("section", "module2_form", "raw_score", name="uq_score_conversion"),
    )


class AttemptResult(Base):
    __tablename__ = "attempt_results"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_uuid)
    attempt_id: Mapped[str] = mapped_column(
        ForeignKey("attempts.id"), unique=True, nullable=False
    )
    domain_breakdown: Mapped[Optional[dict]] = mapped_column(JSON)
    difficulty_breakdown: Mapped[Optional[dict]] = mapped_column(JSON)
    weak_skills: Mapped[Optional[dict]] = mapped_column(JSON)
    scored_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    attempt = relationship("Attempt", back_populates="result")


# ═══════════════════════════════════════════════════════════
# Practice Plans
# ═══════════════════════════════════════════════════════════

class PracticePlan(Base):
    __tablename__ = "practice_plans"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    source_attempt_id: Mapped[Optional[str]] = mapped_column(ForeignKey("attempts.id"))
    title: Mapped[Optional[str]] = mapped_column(String(500))
    target_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active, archived, completed
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    student = relationship("User", back_populates="practice_plans")
    tasks = relationship("PracticeTask", back_populates="plan")


class PracticeTask(Base):
    __tablename__ = "practice_tasks"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_uuid)
    plan_id: Mapped[str] = mapped_column(
        ForeignKey("practice_plans.id", ondelete="CASCADE"), nullable=False
    )
    skill: Mapped[str] = mapped_column(String(100), nullable=False)
    difficulty: Mapped[Optional[str]] = mapped_column(String(10))
    target_count: Mapped[int] = mapped_column(Integer, nullable=False)
    completed_count: Mapped[int] = mapped_column(Integer, default=0)
    priority: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending, in_progress, completed

    plan = relationship("PracticePlan", back_populates="tasks")
    questions = relationship("PracticeTaskQuestion", back_populates="task")


class PracticeTaskQuestion(Base):
    __tablename__ = "practice_task_questions"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_uuid)
    task_id: Mapped[str] = mapped_column(
        ForeignKey("practice_tasks.id", ondelete="CASCADE"), nullable=False
    )
    question_version_id: Mapped[str] = mapped_column(
        ForeignKey("question_versions.id"), nullable=False
    )
    question_order: Mapped[int] = mapped_column(Integer, nullable=False)

    task = relationship("PracticeTask", back_populates="questions")
    answer = relationship("PracticeAnswer", back_populates="task_question", uselist=False)


class PracticeAnswer(Base):
    __tablename__ = "practice_answers"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=new_uuid)
    practice_task_question_id: Mapped[str] = mapped_column(
        ForeignKey("practice_task_questions.id", ondelete="CASCADE"), nullable=False
    )
    answer: Mapped[Optional[str]] = mapped_column(String(50))
    is_correct: Mapped[Optional[bool]] = mapped_column(Boolean)
    time_spent_sec: Mapped[Optional[int]] = mapped_column(Integer)
    answered_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    task_question = relationship("PracticeTaskQuestion", back_populates="answer")

    __table_args__ = (
        UniqueConstraint("practice_task_question_id", name="uq_practice_answer"),
    )
