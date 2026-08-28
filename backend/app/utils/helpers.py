from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from sqlalchemy.orm import Query


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime | date | None) -> str | None:
    if dt is None:
        return None
    if isinstance(dt, date) and not isinstance(dt, datetime):
        return dt.isoformat()
    return dt.isoformat()


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
    today = date.today()
    start = parse_date(from_date, today - timedelta(days=29))
    end = parse_date(to_date, today)
    if end is None:
        end = start + timedelta(days=29)
    start_dt = datetime.combine(start, time.min, tzinfo=timezone.utc)
    end_dt = datetime.combine(end + timedelta(days=1), time.min, tzinfo=timezone.utc)
    return start_dt, end_dt


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