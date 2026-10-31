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
