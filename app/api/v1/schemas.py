from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MeResponse(BaseModel):
    email: EmailStr
    role: str
    account_id: UUID
    account_name: str | None


class AccountOut(BaseModel):
    id: UUID
    name: str
    slug: str

    model_config = {"from_attributes": True}


class VenueOut(BaseModel):
    venue_id: UUID
    account_id: UUID
    name: str
    city: str

    model_config = {"from_attributes": True}


class EventOut(BaseModel):
    event_id: UUID
    account_id: UUID
    venue_id: UUID
    name: str
    event_type: str
    event_date: date
    created_at: datetime

    model_config = {"from_attributes": True}


class EventPerformanceOut(BaseModel):
    redeemed_tickets: int | None = None
    order_count: int | None = None
    revenue_cents: int | None = None
    headcount_woman: int | None = None
    headcount_man: int | None = None
    headcount_other: int | None = None
    headcount_undisclosed: int | None = None
    headcount_total: int | None = None


class EventPerformanceResponse(BaseModel):
    name: str
    title: str
    unit: str
    definition: str
    as_of: date | None
    data_quality: str
    data_source: str
    scope: str
    event: EventOut
    performance: EventPerformanceOut


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
    account_id: UUID | None = None


class SalesPointOut(BaseModel):
    venue_id: UUID
    night_date: date
    order_count: int
    revenue_cents: int
    account_id: UUID | None = None


class MeasureResponse(BaseModel):
    name: str
    title: str
    unit: str
    definition: str
    as_of: date | None
    data_quality: str
    data_source: str
    scope: str
    points: list[AttendancePointOut]


class SalesMeasureResponse(BaseModel):
    name: str
    title: str
    unit: str
    definition: str
    as_of: date | None
    data_quality: str
    data_source: str
    scope: str
    points: list[SalesPointOut]


class GremialBenchmarksResponse(BaseModel):
    period_start: date
    period_end: date
    avg_tickets_per_venue_night: float | None
    median_tickets_per_venue_night: float | None
    avg_orders_per_venue_night: float | None
    median_orders_per_venue_night: float | None
    accounts_in_sample: int
    nights_in_sample: int
    share_woman: float | None = None
    share_man: float | None = None
    share_other: float | None = None
    share_undisclosed: float | None = None
    note: str = (
        "Promedios anónimos del ecosistema. Sin nombres de clientes ni breakdown por venue ajeno."
    )


class GenderPointOut(BaseModel):
    gender: str
    headcount: int
    share: float
    account_id: UUID | None = None


class GenderMeasureResponse(BaseModel):
    name: str
    title: str
    unit: str
    definition: str
    as_of: date | None
    data_quality: str
    data_source: str
    scope: str
    points: list[GenderPointOut]


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
