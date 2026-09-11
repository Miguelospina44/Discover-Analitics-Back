from sqlalchemy import create_engine, text

from app.core.config import get_settings

get_settings.cache_clear()
settings = get_settings()
engine = create_engine(settings.alembic_database_url)
with engine.connect() as conn:
    rows = conn.execute(
        text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'analytics' ORDER BY 1"
        )
    ).fetchall()
    print("tables:", [row[0] for row in rows])
    count = conn.execute(text("SELECT COUNT(*) FROM analytics.fact_nightly_attendance")).scalar()
    print("fact_attendance_rows", count)
