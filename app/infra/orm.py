from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.roles import ALLOWED_ROLES
from app.infra.db import Base

# Reused across every tenant-scoped table so account_id is a real FK, mirroring
# migration 0006. Reference by string so class declaration order does not matter.
_ACCOUNT_FK = "analytics.accounts.id"


def _account_fk(name: str) -> ForeignKey:
    return ForeignKey(_ACCOUNT_FK, name=name, ondelete="RESTRICT")


_ROLES_CSV = ", ".join(f"'{role}'" for role in sorted(ALLOWED_ROLES))


class AnalyticsUser(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(f"role IN ({_ROLES_CSV})", name="ck_users_role_allowed"),
        {"schema": "analytics"},
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    account_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), _account_fk("fk_users_account"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Account(Base):
    __tablename__ = "accounts"
    __table_args__ = {"schema": "analytics"}

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Engagement(Base):
    __tablename__ = "engagements"
    __table_args__ = {"schema": "analytics"}

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    account_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), _account_fk("fk_engagements_account"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    client_name: Mapped[str] = mapped_column(String(200), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    scope: Mapped[str] = mapped_column(Text, nullable=False)
    objectives: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Finding(Base):
    __tablename__ = "findings"
    __table_args__ = {"schema": "analytics"}

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    account_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), _account_fk("fk_findings_account"), nullable=False, index=True
    )
    engagement_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("analytics.engagements.id"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    evidence: Mapped[str] = mapped_column(Text, nullable=False)
    visual_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    impact: Mapped[str] = mapped_column(String(32), nullable=False)
    confidence: Mapped[str] = mapped_column(String(32), nullable=False)
    review_status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Recommendation(Base):
    __tablename__ = "recommendations"
    __table_args__ = {"schema": "analytics"}

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    account_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), _account_fk("fk_recommendations_account"), nullable=False, index=True
    )
    engagement_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("analytics.engagements.id"), nullable=False
    )
    finding_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("analytics.findings.id"), nullable=True
    )
    action: Mapped[str] = mapped_column(Text, nullable=False)
    expected_impact: Mapped[str] = mapped_column(Text, nullable=False)
    effort: Mapped[str] = mapped_column(String(32), nullable=False)
    priority: Mapped[str] = mapped_column(String(32), nullable=False)
    owner: Mapped[str] = mapped_column(String(120), nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending_decision")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DimVenue(Base):
    __tablename__ = "dim_venues"
    __table_args__ = {"schema": "analytics"}

    venue_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    account_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), _account_fk("fk_dim_venues_account"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    city: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


_EVENT_TYPES = ("regular", "especial", "privado", "festival", "otro")
_EVENT_TYPES_CSV = ", ".join(f"'{t}'" for t in _EVENT_TYPES)


class DimEvent(Base):
    __tablename__ = "dim_event"
    __table_args__ = (
        CheckConstraint(
            f"event_type IN ({_EVENT_TYPES_CSV})", name="ck_dim_event_type_allowed"
        ),
        UniqueConstraint(
            "venue_id", "event_date", "name", name="uq_dim_event_venue_date_name"
        ),
        {"schema": "analytics"},
    )

    event_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    account_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), _account_fk("fk_dim_event_account"), nullable=False, index=True
    )
    venue_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("analytics.dim_venues.venue_id"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False, default="regular")
    event_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FactNightlyAttendance(Base):
    __tablename__ = "fact_nightly_attendance"
    __table_args__ = {"schema": "analytics"}

    account_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), _account_fk("fk_fact_nightly_attendance_account"), primary_key=True
    )
    venue_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("analytics.dim_venues.venue_id"), primary_key=True
    )
    night_date: Mapped[date] = mapped_column(Date, primary_key=True)
    redeemed_tickets: Mapped[int] = mapped_column(Integer, nullable=False)


class FactSalesByNight(Base):
    __tablename__ = "fact_sales_by_night"
    __table_args__ = {"schema": "analytics"}

    account_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), _account_fk("fk_fact_sales_by_night_account"), primary_key=True
    )
    venue_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("analytics.dim_venues.venue_id"), primary_key=True
    )
    night_date: Mapped[date] = mapped_column(Date, primary_key=True)
    order_count: Mapped[int] = mapped_column(Integer, nullable=False)
    revenue_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)


class FactAttendanceByGender(Base):
    __tablename__ = "fact_attendance_by_gender"
    __table_args__ = {"schema": "analytics"}

    account_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), _account_fk("fk_fact_attendance_by_gender_account"), primary_key=True
    )
    night_date: Mapped[date] = mapped_column(Date, primary_key=True)
    gender: Mapped[str] = mapped_column(String(32), primary_key=True)
    headcount: Mapped[int] = mapped_column(Integer, nullable=False)


class FactAttendanceDetail(Base):
    __tablename__ = "fact_attendance_detail"
    __table_args__ = {"schema": "analytics"}

    account_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), _account_fk("fk_fact_attendance_detail_account"), primary_key=True
    )
    venue_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("analytics.dim_venues.venue_id"), primary_key=True
    )
    night_date: Mapped[date] = mapped_column(Date, primary_key=True)
    gender: Mapped[str] = mapped_column(String(32), primary_key=True)
    headcount: Mapped[int] = mapped_column(Integer, nullable=False)
