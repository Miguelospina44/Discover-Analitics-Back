from datetime import date
from uuid import uuid4

from app.data.sales_repository import SalesPoint, quality_for_sales
from app.domain.measures import SALES_BY_NIGHT


def test_sales_meta_exists() -> None:
    assert SALES_BY_NIGHT.name == "sales_by_night"


def test_sales_quality() -> None:
    assert quality_for_sales([]) == "missing"
    ok = [
        SalesPoint(uuid4(), date(2026, 8, 1), 3, 1000),
        SalesPoint(uuid4(), date(2026, 8, 2), 5, 2000),
    ]
    assert quality_for_sales(ok) == "ok"
    partial = [SalesPoint(uuid4(), date(2026, 8, 1), 0, 0)]
    assert quality_for_sales(partial) == "partial"
