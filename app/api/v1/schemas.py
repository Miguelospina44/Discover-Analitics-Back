from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class EngagementCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    client_name: str = Field(min_length=2, max_length=200)
    period_start: date
    period_end: date
    scope: str
    objectives: str


class EngagementOut(BaseModel):
    id: UUID
    account_id: UUID
    title: str
    client_name: str
    period_start: date
    period_end: date
    scope: str
    objectives: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class AttendancePointOut(BaseModel):
    venue_id: UUID
    night_date: date
    redeemed_tickets: int


class MeasureResponse(BaseModel):
    name: str
    title: str
    unit: str
    definition: str
    as_of: date | None
    data_quality: str
    points: list[AttendancePointOut]


class FindingCreate(BaseModel):
    engagement_id: UUID
    title: str
    evidence: str
    visual_id: str | None = None
    impact: str
    confidence: str


class FindingOut(BaseModel):
    id: UUID
    engagement_id: UUID
    title: str
    evidence: str
    visual_id: str | None
    impact: str
    confidence: str
    review_status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class RecommendationCreate(BaseModel):
    engagement_id: UUID
    finding_id: UUID | None = None
    action: str
    expected_impact: str
    effort: str
    priority: str
    owner: str
    due_date: date | None = None


class RecommendationOut(BaseModel):
    id: UUID
    engagement_id: UUID
    finding_id: UUID | None
    action: str
    expected_impact: str
    effort: str
    priority: str
    owner: str
    due_date: date | None
    status: str

    model_config = {"from_attributes": True}


class HealthResponse(BaseModel):
    status: str
    app: str


class ReadyResponse(BaseModel):
    status: str
    database: str
