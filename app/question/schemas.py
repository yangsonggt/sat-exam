"""Question schemas."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class ChoiceSchema(BaseModel):
    label: str
    text: str


class QuestionCreate(BaseModel):
    section: str  # reading_writing, math
    type: str  # multiple_choice, grid_in
    stem: str
    passage: Optional[str] = None
    options: Optional[list[ChoiceSchema]] = None
    correct_answer: str
    explanation: Optional[str] = None
    skill: Optional[str] = None
    difficulty: Optional[str] = None


class QuestionUpdate(BaseModel):
    stem: Optional[str] = None
    passage: Optional[str] = None
    options: Optional[list[ChoiceSchema]] = None
    correct_answer: Optional[str] = None
    explanation: Optional[str] = None
    skill: Optional[str] = None
    difficulty: Optional[str] = None


class QuestionVersionResponse(BaseModel):
    id: str
    version_no: int
    stem: str
    passage: Optional[str] = None
    options: Optional[list[ChoiceSchema]] = None
    correct_answer: str
    explanation: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class QuestionResponse(BaseModel):
    id: str
    section: str
    type: str
    skill: Optional[str] = None
    difficulty: Optional[str] = None
    status: str
    source_upload_id: Optional[str] = None
    extraction_confidence: Optional[float] = None
    current_version_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    current_version: Optional[QuestionVersionResponse] = None

    class Config:
        from_attributes = True


class QuestionListResponse(BaseModel):
    items: list[QuestionResponse]
    total: int
    offset: int
    limit: int


class BulkActionRequest(BaseModel):
    ids: list[str]


class BulkStatusRequest(BulkActionRequest):
    status: str  # published, archived


class BulkTagRequest(BulkActionRequest):
    skill: Optional[str] = None
    difficulty: Optional[str] = None


class ReviewItem(BaseModel):
    """Question in the review queue with confidence score."""
    id: str
    section: str
    type: str
    stem: str
    options: Optional[dict] = None
    correct_answer: Optional[str] = None
    explanation: Optional[str] = None
    extraction_confidence: Optional[float] = None
    answer_match_status: str = "unmatched"  # matched, unmatched
    source_page: Optional[int] = None
