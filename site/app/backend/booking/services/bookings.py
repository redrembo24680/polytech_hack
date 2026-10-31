from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from booking import clock
from booking.errors import ApiError
from booking.ids import new_id
from booking.models import Booking, Client, Service, Staff, Tenant, add_event
from booking.phone import normalize_phone


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


def get_or_create_client(session: Session, tenant_id: str, name: str, phone_raw: str) -> Client:
    phone = normalize_phone(phone_raw)
    if not phone:
        raise ApiError("validation", "client.phone: must contain digits", 422)
    existing = session.scalars(
        select(Client).where(Client.tenant_id == tenant_id, Client.phone == phone)
    ).first()
    if existing is not None:
        return existing
    c = Client(id=new_id("cl"), tenant_id=tenant_id, name=name, phone=phone)
    session.add(c)
    session.flush()
    return c


def create_booking(session: Session, tenant: Tenant, client: Client, staff: Staff,
                   service: Service, start: datetime, by: str) -> Booking:
    if service.id not in {s.id for s in staff.services}:
        raise ApiError("validation", "staff does not provide this service", 422)
    end = start + timedelta(minutes=service.duration_min)
    if not is_slot_free(session, staff, start, end):
        raise ApiError("slot_taken", "slot is not available", 409)
    required = tenant.policy.get("prepayment_required", False)
    b = Booking(
        id=new_id("b"), tenant_id=tenant.id, client_id=client.id, staff_id=staff.id,
        service_id=service.id, start=start, end=end, status="scheduled",
        prepayment_amount=service.price if required else 0,
        prepayment_status="held" if required else "none",
    )
    session.add(b)
    session.flush()
    add_event(session, b, "created", by)
    return b


def mark_status(session: Session, booking: Booking, tenant: Tenant, status: str,
                by: str, note: str = "") -> Booking:
    if booking.status != "scheduled":
        raise ApiError("invalid_state", f"booking is {booking.status}", 409)
    booking.status = status
    if status == "no_show":
        booking.no_show_fee_amount = tenant.policy.get("no_show_fee", 0)
        booking.no_show_fee_status = "charged"
    add_event(session, booking, status, by, note)
    return booking
