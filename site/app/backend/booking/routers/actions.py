from datetime import date, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends
from pydantic import AwareDatetime, BaseModel
from sqlalchemy.orm import Session

from booking import clock
from booking.db import get_session
from booking.errors import ApiError
from booking.ids import new_id
from booking.models import Booking, Client, GoodwillException, Staff, add_event
from booking.routers.deps import get_or_404, not_found
from booking.schemas import booking_out, client_out, iso
from booking.services.bookings import is_slot_free

router = APIRouter(prefix="/api/tenants/{tenant_id}")


class RescheduleIn(BaseModel):
    start: AwareDatetime
    staff_id: str | None = None
    reason: str = ""
    by: str = "agent"
    forfeit_prepayment: bool = False


class CancelIn(BaseModel):
    reason: str = ""
    by: str = "agent"
    forfeit_prepayment: bool = False


class RefundIn(BaseModel):
    amount: int
    reason: str = ""
    by: str = "agent"


class WaiveIn(BaseModel):
    reason: str = ""
    by: str = "agent"


class GoodwillIn(BaseModel):
    booking_id: str
    reason: str = ""
    by: str = "agent"


def _require_scheduled(b: Booking) -> None:
    if b.status != "scheduled":
        raise ApiError("invalid_state", f"booking is {b.status}", 409)


def _commit(session: Session, b: Booking) -> dict:
    session.commit()
    session.refresh(b)
    return booking_out(b, expand=True)


@router.post("/bookings/{booking_id}/reschedule")
def reschedule(tenant_id: str, booking_id: str, body: RescheduleIn,
               session: Session = Depends(get_session)):
    b = get_or_404(session, Booking, booking_id, tenant_id)
    _require_scheduled(b)
    staff = b.staff if body.staff_id is None else get_or_404(session, Staff, body.staff_id, tenant_id)
    if b.service_id not in {s.id for s in staff.services}:
        raise ApiError("validation", "staff does not provide this service", 422)
    new_end = body.start + timedelta(minutes=b.service.duration_min)
    if not is_slot_free(session, staff, body.start, new_end, exclude_booking_id=b.id):
        raise ApiError("slot_taken", "slot is not available", 409)
    tz = b.tenant.timezone
    note = f"{iso(b.start, tz)} → {iso(body.start, tz)}"
    if body.reason:
        note += f". {body.reason}"
    b.staff_id, b.start, b.end = staff.id, body.start, new_end
    if body.forfeit_prepayment and b.prepayment_status == "held":
        b.prepayment_status = "forfeited"
    session.flush()
    session.refresh(b)
    add_event(session, b, "rescheduled", body.by, note)
    return _commit(session, b)


@router.post("/bookings/{booking_id}/cancel")
def cancel(tenant_id: str, booking_id: str, body: CancelIn,
           session: Session = Depends(get_session)):
    b = get_or_404(session, Booking, booking_id, tenant_id)
    _require_scheduled(b)
    b.status = "cancelled"
    if body.forfeit_prepayment and b.prepayment_status == "held":
        b.prepayment_status = "forfeited"
    add_event(session, b, "cancelled", body.by, body.reason)
    return _commit(session, b)


@router.post("/bookings/{booking_id}/refund")
def refund(tenant_id: str, booking_id: str, body: RefundIn,
           session: Session = Depends(get_session)):
    b = get_or_404(session, Booking, booking_id, tenant_id)
    if b.prepayment_status != "held":
        raise ApiError("invalid_state", f"prepayment is {b.prepayment_status}", 409)
    if not 0 < body.amount <= b.prepayment_amount:
        raise ApiError("validation", "amount: must be > 0 and <= prepayment amount", 422)
    b.prepayment_status = "refunded"
    add_event(session, b, "refunded", body.by, f"{body.amount} UAH. {body.reason}".strip())
    return _commit(session, b)


@router.post("/bookings/{booking_id}/waive-no-show")
def waive_no_show(tenant_id: str, booking_id: str, body: WaiveIn,
                  session: Session = Depends(get_session)):
    b = get_or_404(session, Booking, booking_id, tenant_id)
    if b.status != "no_show" or b.no_show_fee_status != "charged":
        raise ApiError("invalid_state", "no charged no-show fee to waive", 409)
    b.no_show_fee_status = "waived"
    add_event(session, b, "no_show_waived", body.by, body.reason)
    return _commit(session, b)


@router.post("/clients/{client_id}/goodwill")
def goodwill(tenant_id: str, client_id: str, body: GoodwillIn,
             session: Session = Depends(get_session)):
    c = get_or_404(session, Client, client_id, tenant_id)
    b = get_or_404(session, Booking, body.booking_id, tenant_id)
    if b.client_id != c.id:
        raise not_found()
    today: date = clock.now().astimezone(ZoneInfo(c.tenant.timezone)).date()
    session.add(GoodwillException(id=new_id("gw"), client_id=c.id, booking_id=b.id,
                                  date=today, reason=body.reason))
    session.flush()
    add_event(session, b, "goodwill", body.by, body.reason)
    session.commit()
    session.refresh(c)
    return client_out(c, session, with_bookings=False)
