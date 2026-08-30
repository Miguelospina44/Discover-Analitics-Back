from datetime import date
from uuid import uuid4

from app.domain.measures import AttendancePoint, quality_for_points


def test_quality_missing_when_empty() -> None:
    assert quality_for_points([]) == "missing"


def test_quality_ok_when_all_positive() -> None:
    points = [
        AttendancePoint(venue_id=uuid4(), night_date=date(2026, 8, 1), redeemed_tickets=12),
        AttendancePoint(venue_id=uuid4(), night_date=date(2026, 8, 2), redeemed_tickets=4),
    ]
    assert quality_for_points(points) == "ok"


def test_quality_partial_when_zero_night() -> None:
    points = [
        AttendancePoint(venue_id=uuid4(), night_date=date(2026, 8, 1), redeemed_tickets=0),
    ]
    assert quality_for_points(points) == "partial"
