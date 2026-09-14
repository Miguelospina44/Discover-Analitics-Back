from dataclasses import dataclass
from datetime import date

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings

SEED_BENCH_SQL = text(
    """
    SELECT
      (SELECT AVG(redeemed_tickets)::float
         FROM analytics.fact_nightly_attendance
        WHERE night_date >= :period_start AND night_date <= :period_end
      ) AS avg_tickets_per_venue_night,
      (SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY redeemed_tickets)
         FROM analytics.fact_nightly_attendance
        WHERE night_date >= :period_start AND night_date <= :period_end
      ) AS median_tickets_per_venue_night,
      (SELECT AVG(order_count)::float
         FROM analytics.fact_sales_by_night
        WHERE night_date >= :period_start AND night_date <= :period_end
      ) AS avg_orders_per_venue_night,
      (SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY order_count)
         FROM analytics.fact_sales_by_night
        WHERE night_date >= :period_start AND night_date <= :period_end
      ) AS median_orders_per_venue_night,
      (SELECT COUNT(DISTINCT account_id)
         FROM analytics.fact_nightly_attendance
        WHERE night_date >= :period_start AND night_date <= :period_end
      ) AS accounts_in_sample,
      (SELECT COUNT(*)
         FROM analytics.fact_nightly_attendance
        WHERE night_date >= :period_start AND night_date <= :period_end
      ) AS nights_in_sample,
      (SELECT SUM(headcount)::float
         FROM analytics.fact_attendance_by_gender
        WHERE night_date >= :period_start AND night_date <= :period_end
          AND gender = 'woman'
      ) AS sum_woman,
      (SELECT SUM(headcount)::float
         FROM analytics.fact_attendance_by_gender
        WHERE night_date >= :period_start AND night_date <= :period_end
          AND gender = 'man'
      ) AS sum_man,
      (SELECT SUM(headcount)::float
         FROM analytics.fact_attendance_by_gender
        WHERE night_date >= :period_start AND night_date <= :period_end
          AND gender = 'other'
      ) AS sum_other,
      (SELECT SUM(headcount)::float
         FROM analytics.fact_attendance_by_gender
        WHERE night_date >= :period_start AND night_date <= :period_end
          AND gender = 'undisclosed'
      ) AS sum_undisclosed,
      (SELECT SUM(headcount)::float
         FROM analytics.fact_attendance_by_gender
        WHERE night_date >= :period_start AND night_date <= :period_end
      ) AS sum_gender_total
    """
)

# Fase B: benchmarks derived from the read-only views over Discover `public`
# tables. The views expose tickets/orders per venue-night but carry NO gender
# breakdown, so gender shares are NULL here (see docs/phase-b-discover.md).
DISCOVER_BENCH_SQL = text(
    """
    SELECT
      (SELECT AVG(redeemed_tickets)::float
         FROM analytics.v_nightly_attendance
        WHERE night_date >= :period_start AND night_date <= :period_end
      ) AS avg_tickets_per_venue_night,
      (SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY redeemed_tickets)
         FROM analytics.v_nightly_attendance
        WHERE night_date >= :period_start AND night_date <= :period_end
      ) AS median_tickets_per_venue_night,
      (SELECT AVG(order_count)::float
         FROM analytics.v_sales_by_night
        WHERE night_date >= :period_start AND night_date <= :period_end
      ) AS avg_orders_per_venue_night,
      (SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY order_count)
         FROM analytics.v_sales_by_night
        WHERE night_date >= :period_start AND night_date <= :period_end
      ) AS median_orders_per_venue_night,
      (SELECT COUNT(DISTINCT account_id)
         FROM analytics.v_nightly_attendance
        WHERE night_date >= :period_start AND night_date <= :period_end
      ) AS accounts_in_sample,
      (SELECT COUNT(*)
         FROM analytics.v_nightly_attendance
        WHERE night_date >= :period_start AND night_date <= :period_end
      ) AS nights_in_sample,
      NULL::float AS sum_woman,
      NULL::float AS sum_man,
      NULL::float AS sum_other,
      NULL::float AS sum_undisclosed,
      NULL::float AS sum_gender_total
    """
)


@dataclass(frozen=True)
class GremialBenchmarks:
    avg_tickets_per_venue_night: float | None
    median_tickets_per_venue_night: float | None
    avg_orders_per_venue_night: float | None
    median_orders_per_venue_night: float | None
    accounts_in_sample: int
    nights_in_sample: int
    share_woman: float | None
    share_man: float | None
    share_other: float | None
    share_undisclosed: float | None


class BenchmarkRepository:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings | None = None,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()

    async def gremial(
        self,
        period_start: date,
        period_end: date,
    ) -> GremialBenchmarks:
        sql = SEED_BENCH_SQL if self._settings.uses_seed_facts else DISCOVER_BENCH_SQL
        result = await self._session.execute(
            sql,
            {"period_start": period_start, "period_end": period_end},
        )
        row = result.mappings().one()
        total = _f(row["sum_gender_total"]) or 0.0

        def share(key: str) -> float | None:
            part = _f(row[key])
            if part is None or total <= 0:
                return None
            return part / total

        return GremialBenchmarks(
            avg_tickets_per_venue_night=_f(row["avg_tickets_per_venue_night"]),
            median_tickets_per_venue_night=_f(row["median_tickets_per_venue_night"]),
            avg_orders_per_venue_night=_f(row["avg_orders_per_venue_night"]),
            median_orders_per_venue_night=_f(row["median_orders_per_venue_night"]),
            accounts_in_sample=int(row["accounts_in_sample"] or 0),
            nights_in_sample=int(row["nights_in_sample"] or 0),
            share_woman=share("sum_woman"),
            share_man=share("sum_man"),
            share_other=share("sum_other"),
            share_undisclosed=share("sum_undisclosed"),
        )


def _f(value: object) -> float | None:
    if value is None:
        return None
    return float(value)
