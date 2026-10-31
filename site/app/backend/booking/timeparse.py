from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from booking.errors import ApiError


def parse_when(raw: str, tz: str, field: str) -> datetime:
    """ISO date (midnight in tenant tz) or ISO datetime WITH offset; else 422."""
    try:
        if len(raw) == 10:
            return datetime.combine(date.fromisoformat(raw), time(0), tzinfo=ZoneInfo(tz))
        dt = datetime.fromisoformat(raw)
    except ValueError:
        raise ApiError("validation", f"{field}: invalid date/datetime", 422)
    if dt.tzinfo is None:
        raise ApiError("validation", f"{field}: datetime must include a UTC offset", 422)
    return dt
