from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from booking import clock
from booking.models import Booking


def has_future_scheduled(session: Session, **filter) -> bool:
    """True if any scheduled booking starting now or later matches the column filters."""
    q = select(Booking.id).where(
        Booking.start >= clock.now(), Booking.status == "scheduled"
    )
    for col, val in filter.items():
        q = q.where(getattr(Booking, col) == val)
    return session.scalars(q.limit(1)).first() is not None


def is_slot_free(session: Session, staff, start: datetime, end: datetime,
                 exclude_booking_id: str | None = None) -> bool:
    """Single source of truth: inside the staff schedule, not in the past, no overlap
    with the staff's `scheduled` bookings."""
    if start < clock.now() or end <= start:
        return False
    tz = ZoneInfo(staff.tenant.timezone)
    ls, le = start.astimezone(tz), end.astimezone(tz)
    if ls.date() != le.date():
        return False
    row = next((r for r in staff.schedule if r.weekday == ls.weekday()), None)
    if row is None or ls.time() < row.start_time or le.time() > row.end_time:
        return False
    q = select(Booking.id).where(
        Booking.staff_id == staff.id, Booking.status == "scheduled",
        Booking.start < end, Booking.end > start,
    )
    if exclude_booking_id is not None:
        q = q.where(Booking.id != exclude_booking_id)
    return session.scalars(q.limit(1)).first() is None
