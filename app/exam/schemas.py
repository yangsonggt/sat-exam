"""Exam blueprint schemas."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class SelectionRuleSchema(BaseModel):
    skill: Optional[str] = None
    difficulty: Optional[str] = None
    count: int


class ExamModuleSchema(BaseModel):
    id: Optional[str] = None
    section: str  # reading_writing, math
    module_no: int  # 1 or 2
    form: str  # base, easier, harder
    time_limit_min: int
    question_count: int
    selection_rules: list[SelectionRuleSchema] = []


class ExamCreate(BaseModel):
    title: str
    description: Optional[str] = None
    modules: list[ExamModuleSchema]
    routing_threshold_rw: Optional[float] = None
    routing_threshold_math: Optional[float] = None
    timer_mode: str = "strict"


class ExamUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    routing_threshold_rw: Optional[float] = None
    routing_threshold_math: Optional[float] = None
    timer_mode: Optional[str] = None


class ExamResponse(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    status: str
    routing_threshold_rw: Optional[float] = None
    routing_threshold_math: Optional[float] = None
    timer_mode: str
    created_at: datetime
    updated_at: datetime
    modules: list[ExamModuleSchema] = []

    class Config:
        from_attributes = True


class ExamListResponse(BaseModel):
    items: list[ExamResponse]
    total: int
    offset: int
    limit: int
