from typing import Literal

from fastapi import APIRouter, Depends, Query, Response
from pydantic import AwareDatetime, BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from booking.db import get_session
from booking.errors import ApiError
from booking.models import Booking, Client, Service, Staff
from booking.routers.deps import get_or_404, get_tenant_or_404
from booking.schemas import booking_out
from booking.services.bookings import create_booking, get_or_create_client, mark_status
from booking.timeparse import parse_when

router = APIRouter(prefix="/api/tenants/{tenant_id}/bookings")


class NewClient(BaseModel):
    name: str
    phone: str


class BookingIn(BaseModel):
    client_id: str | None = None
    client: NewClient | None = None
    service_id: str
    staff_id: str
    start: AwareDatetime
    by: str = "human:admin"


class BookingPatch(BaseModel):
    status: Literal["completed", "no_show"] | None = None
    notes: str | None = None
    by: str = "human:admin"


def _list_item(b: Booking) -> dict:
    out = booking_out(b, expand=False)
    out["client_name"] = b.client.name
    out["staff_name"] = b.staff.name
    out["service_name"] = b.service.name
    return out


@router.get("")
def list_bookings(tenant_id: str, from_: str | None = Query(None, alias="from"),
                  to: str | None = None, staff_id: str | None = None,
                  status: str | None = None, session: Session = Depends(get_session)):
    tenant = get_tenant_or_404(session, tenant_id)
    q = select(Booking).where(Booking.tenant_id == tenant_id).order_by(Booking.start, Booking.id)
    if from_ is not None:
        q = q.where(Booking.start >= parse_when(from_, tenant.timezone, "from"))
    if to is not None:
        q = q.where(Booking.start < parse_when(to, tenant.timezone, "to"))
    if staff_id is not None:
        q = q.where(Booking.staff_id == staff_id)
    if status is not None:
        q = q.where(Booking.status == status)
    return [_list_item(b) for b in session.scalars(q)]


@router.get("/{booking_id}")
def get_booking(tenant_id: str, booking_id: str, session: Session = Depends(get_session)):
    b = get_or_404(session, Booking, booking_id, tenant_id)
    return booking_out(b, expand=True)


@router.post("", status_code=201)
def post_booking(tenant_id: str, body: BookingIn, session: Session = Depends(get_session)):
    tenant = get_tenant_or_404(session, tenant_id)
    if (body.client_id is None) == (body.client is None):
        raise ApiError("validation", "provide exactly one of client_id or client", 422)
    service = get_or_404(session, Service, body.service_id, tenant_id)
    staff = get_or_404(session, Staff, body.staff_id, tenant_id)
    if body.client_id is not None:
        client = get_or_404(session, Client, body.client_id, tenant_id)
    else:
        client = get_or_create_client(session, tenant_id, body.client.name, body.client.phone)
    try:
        b = create_booking(session, tenant, client, staff, service, body.start, body.by)
        session.commit()
    except Exception:
        session.rollback()
        raise
    return booking_out(b, expand=True)


@router.patch("/{booking_id}")
def patch_booking(tenant_id: str, booking_id: str, body: BookingPatch,
                  session: Session = Depends(get_session)):
    b = get_or_404(session, Booking, booking_id, tenant_id)
    try:
        if body.status is not None:
            mark_status(session, b, b.tenant, body.status, body.by)
        if body.notes is not None:
            b.notes = body.notes
        session.commit()
    except Exception:
        session.rollback()
        raise
    session.refresh(b)
    return booking_out(b, expand=True)


@router.delete("/{booking_id}", status_code=204)
def delete_booking(tenant_id: str, booking_id: str, session: Session = Depends(get_session)):
    b = get_or_404(session, Booking, booking_id, tenant_id)
    session.delete(b)
    session.commit()
    return Response(status_code=204)
