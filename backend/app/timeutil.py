from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from .config import get_settings


def tz() -> ZoneInfo:
    return ZoneInfo(get_settings().timezone)


def local_today() -> date:
    return datetime.now(tz()).date()


def day_range_utc(day: date) -> tuple[datetime, datetime]:
    """Beginn und Ende (exklusiv) eines Praxis-Kalendertags als UTC-Zeitpunkte."""
    start = datetime.combine(day, time.min, tzinfo=tz())
    end = datetime.combine(day + timedelta(days=1), time.min, tzinfo=tz())
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)


def to_utc(dt: datetime) -> datetime:
    """Zeitangaben ohne Zeitzone gelten als Praxis-Ortszeit."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=tz())
    return dt.astimezone(timezone.utc)


def as_utc(dt: datetime) -> datetime:
    """Aus der Datenbank gelesene Zeiten (SQLite liefert naive Werte) sind immer UTC."""
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
