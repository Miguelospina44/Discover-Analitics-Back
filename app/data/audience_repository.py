"""Lectura de la segmentación ANÓNIMA de audiencia (Fase D).

INVARIANTE DE PRIVACIDAD: este repositorio SOLO devuelve agregados anónimos
(conteos y shares por bucket). Nunca selecciona ni expone datos personales: la
tabla analytics.fact_audience_profile no los contiene. Toda la SQL es
parametrizada. Espeja el estilo de benchmark_repository/gender_repository.
"""

from datetime import date
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.domain.measures import (
    AudienceDimension,
    AudienceProfile,
    AudienceSegment,
)

# Columna física por cada dimensión anónima expuesta.
_DIMENSIONS: tuple[AudienceDimension, ...] = ("gender", "age_band", "zone", "recurrence")


def _audience_sql(*, all_accounts: bool) -> text:
    """SUM(headcount) por cada dimensión, agregando sobre las noches del período.

    Un UNION ALL por dimensión evita cuatro round-trips y mantiene la SQL
    parametrizada (los nombres de columna son de una lista fija, no input).
    """
    where = ["night_date >= :period_start", "night_date <= :period_end"]
    if not all_accounts:
        where.append("account_id = :account_id")
    where_sql = " AND ".join(where)
    blocks = [
        f"""
        SELECT '{dimension}' AS dimension, {dimension} AS bucket_key,
               SUM(headcount)::int AS headcount
        FROM analytics.fact_audience_profile
        WHERE {where_sql}
        GROUP BY {dimension}
        """
        for dimension in _DIMENSIONS
    ]
    return text(
        " UNION ALL ".join(blocks) + " ORDER BY dimension ASC, headcount DESC, bucket_key ASC"
    )


class AudienceRepository:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings | None = None,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()

    async def profile_for_scope(
        self,
        account_id: UUID | None,
        period_start: date,
        period_end: date,
    ) -> AudienceProfile:
        params: dict = {"period_start": period_start, "period_end": period_end}
        if account_id is not None:
            params["account_id"] = account_id

        sql = _audience_sql(all_accounts=account_id is None)
        result = await self._session.execute(sql, params)
        rows = result.mappings().all()

        totals: dict[str, int] = {}
        for row in rows:
            totals[row["dimension"]] = totals.get(row["dimension"], 0) + int(row["headcount"])

        segments: list[AudienceSegment] = []
        for row in rows:
            dimension = str(row["dimension"])
            if dimension not in _DIMENSIONS:
                continue
            count = int(row["headcount"])
            total = totals.get(dimension, 0)
            segments.append(
                AudienceSegment(
                    dimension=dimension,  # type: ignore[arg-type]
                    key=str(row["bucket_key"]),
                    headcount=count,
                    share=(count / total) if total else 0.0,
                )
            )
        return AudienceProfile(segments=segments)
