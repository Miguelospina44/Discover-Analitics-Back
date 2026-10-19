"""Gender × age-band audience. Seed is marked demo; Discover reads the allowlisted view."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from uuid import UUID

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.domain.analytics_scope import (
    AnalyticsScope,
    event_ids_clause,
    resolve_scope,
)
from app.domain.audience import (
    DEMO_LABEL,
    SEED_DEMO_CELLS,
    AudienceCell,
    apply_k_anonymity,
    with_shares,
)


@dataclass(frozen=True)
class AudiencePoint:
    gender: str
    age_band: str
    headcount: int
    share: float


@dataclass(frozen=True)
class AudienceQueryResult:
    points: list[AudiencePoint]
    quality: str
    is_demo: bool
    demo_label: str | None
    suppressed: bool


def _bind_events(sql: text, scope: AnalyticsScope) -> text:
    if scope.requires_event_filter:
        return sql.bindparams(bindparam("event_ids", expanding=True))
    return sql


def _to_result(cells: list[AudienceCell], *, is_demo: bool) -> AudienceQueryResult:
    published = apply_k_anonymity(cells)
    suppressed = len(published) != len(cells) or (not published and bool(cells))
    points = [
        AudiencePoint(
            gender=cell.gender,
            age_band=cell.age_band,
            headcount=cell.headcount,
            share=round(share, 4),
        )
        for cell, share in with_shares(published)
    ]
    quality = "ok" if points else "missing"
    return AudienceQueryResult(
        points=points,
        quality=quality,
        is_demo=is_demo,
        demo_label=DEMO_LABEL if is_demo else None,
        suppressed=suppressed,
    )


class AudienceRepository:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings | None = None,
    ) -> None:
        self._session = session
        self._settings = settings or get_settings()

    async def list_gender_age(
        self,
        account_id: UUID,
        period_start: date,
        period_end: date,
        venue_id: UUID | None = None,
        scope: AnalyticsScope | None = None,
    ) -> AudienceQueryResult:
        resolved = resolve_scope(account_id, scope)
        if self._settings.uses_seed_facts:
            if resolved.requires_event_filter and not resolved.event_ids:
                return _to_result([], is_demo=True)
            return _to_result(list(SEED_DEMO_CELLS), is_demo=True)

        where = [
            "account_id = :account_id",
            "event_date >= :period_start",
            "event_date <= :period_end",
        ]
        params: dict = {
            "account_id": account_id,
            "period_start": period_start,
            "period_end": period_end,
        }
        if venue_id is not None:
            if not resolved.allows_venue_grain:
                return _to_result([], is_demo=False)
            where.append("venue_id = :venue_id")
            params["venue_id"] = venue_id
        if not event_ids_clause(where, params, resolved):
            return _to_result([], is_demo=False)

        sql = text(
            f"""
            SELECT gender, age_band, SUM(headcount)::int AS headcount
            FROM analytics.v_audience_by_gender_age
            WHERE {" AND ".join(where)}
            GROUP BY gender, age_band
            ORDER BY gender, age_band
            """
        )
        result = await self._session.execute(_bind_events(sql, resolved), params)
        cells = [
            AudienceCell(
                gender=str(row["gender"]),
                age_band=str(row["age_band"]),
                headcount=int(row["headcount"]),
            )
            for row in result.mappings().all()
        ]
        return _to_result(cells, is_demo=False)
