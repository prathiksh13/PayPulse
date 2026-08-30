from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from sqlalchemy.orm import Query


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime | date | None) -> str | None:
    """Serialize a timestamp as a timezone-qualified ISO-8601 string (UTC).

    SQLite stores DateTime(timezone=True) columns as naive UTC strings, which
    lost their offset when re-serialized with plain isoformat(). Clients then
    parsed them as LOCAL time and every timestamp showed ~5.5h off. We treat
    naive values as UTC and always emit an explicit ``Z`` so frontends convert
    to the user's timezone consistently."""
    if dt is None:
        return None
    if isinstance(dt, str):
        return dt
    if isinstance(dt, date) and not isinstance(dt, datetime):
        return dt.isoformat()
    if not isinstance(dt, datetime):
        return str(dt)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def to_float(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_date(value: str | None, default: date | None = None) -> date | None:
    if not value:
        return default
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return default


def resolve_range(from_date: str | None, to_date: str | None) -> tuple[datetime, datetime | None]:
    """Returns an inclusive start and an exclusive end (UTC)."""
    today = now_utc().date()
    start = parse_date(from_date, today - timedelta(days=29))
    end = parse_date(to_date, today)
    if end is None:
        end = start + timedelta(days=29)
    start_dt = datetime.combine(start, time.min, tzinfo=timezone.utc)
    end_dt = datetime.combine(end + timedelta(days=1), time.min, tzinfo=timezone.utc)
    return start_dt, end_dt


def calendar_days(start: datetime, end: datetime | None) -> list[date]:
    """Return every UTC calendar date covered by an inclusive range."""
    if end is None:
        return []
    current = start.astimezone(timezone.utc).date()
    last = (end - timedelta(microseconds=1)).astimezone(timezone.utc).date()
    return [current + timedelta(days=offset) for offset in range((last - current).days + 1)]


def pagination(page: int | None, limit: int | None) -> tuple[int, int]:
    page = page or 1
    limit = limit or 100
    if page < 1:
        page = 1
    if limit < 1:
        limit = 1
    if limit > 500:
        limit = 500
    return page, limit


def paginate(query: Query, page: int | None, limit: int | None) -> dict:
    page, limit = pagination(page, limit)
    total = query.count()
    items = query.offset((page - 1) * limit).limit(limit).all()
    return {
        "items": items,
        "total": total,
        "page": page,
        "limit": limit,
        "has_more": (page * limit) < total,
    }


def first_day_of_month(d: date) -> date:
    return d.replace(day=1)


def previous_period(start: datetime, end: datetime) -> tuple[datetime, datetime]:
    span = end - start
    return start - span, end - span
