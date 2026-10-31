from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from booking.db import get_session
from booking.errors import ApiError
from booking.ids import new_id
from booking.models import Client
from booking.phone import normalize_phone
from booking.routers.deps import get_or_404, get_tenant_or_404
from booking.schemas import client_out
from booking.services.bookings import has_future_scheduled

router = APIRouter(prefix="/api/tenants/{tenant_id}/clients")


class ClientIn(BaseModel):
    name: str
    phone: str
    notes: str = ""


class ClientPatch(BaseModel):
    name: str | None = None
    phone: str | None = None
    notes: str | None = None


def _clean_phone(raw: str) -> str:
    phone = normalize_phone(raw)
    if not phone:
        raise ApiError("validation", "phone: must contain digits", 422)
    return phone


def _ensure_unique(session: Session, tenant_id: str, phone: str, exclude_id: str | None = None):
    existing = session.scalars(
        select(Client).where(Client.tenant_id == tenant_id, Client.phone == phone)
    ).first()
    if existing is not None and existing.id != exclude_id:
        raise ApiError("invalid_state", "client with this phone already exists", 409)


@router.get("")
def list_clients(tenant_id: str, phone: str | None = None, q: str | None = None,
                 session: Session = Depends(get_session)):
    get_tenant_or_404(session, tenant_id)
    stmt = select(Client).where(Client.tenant_id == tenant_id).order_by(Client.name, Client.id)
    if phone is not None:
        stmt = stmt.where(Client.phone == _clean_phone(phone))
    rows = list(session.scalars(stmt))
    if q:
        needle = q.strip().casefold()
        digits = normalize_phone(q)
        rows = [
            c for c in rows
            if needle in c.name.casefold() or (digits and digits in c.phone)
        ]
    return [client_out(c, session) for c in rows]


@router.post("", status_code=201)
def create_client(tenant_id: str, body: ClientIn, session: Session = Depends(get_session)):
    get_tenant_or_404(session, tenant_id)
    phone = _clean_phone(body.phone)
    _ensure_unique(session, tenant_id, phone)
    c = Client(id=new_id("c"), tenant_id=tenant_id, name=body.name, phone=phone, notes=body.notes)
    session.add(c)
    session.commit()
    return client_out(c, session, with_bookings=True)


@router.get("/{client_id}")
def get_client(tenant_id: str, client_id: str, session: Session = Depends(get_session)):
    return client_out(get_or_404(session, Client, client_id, tenant_id), session, with_bookings=True)


@router.patch("/{client_id}")
def patch_client(tenant_id: str, client_id: str, body: ClientPatch,
                 session: Session = Depends(get_session)):
    c = get_or_404(session, Client, client_id, tenant_id)
    data = body.model_dump(exclude_unset=True)
    if data.get("phone") is not None:
        phone = _clean_phone(data["phone"])
        _ensure_unique(session, tenant_id, phone, exclude_id=c.id)
        c.phone = phone
    if data.get("name") is not None:
        c.name = data["name"]
    if data.get("notes") is not None:
        c.notes = data["notes"]
    session.commit()
    return client_out(c, session, with_bookings=True)


@router.delete("/{client_id}", status_code=204)
def delete_client(tenant_id: str, client_id: str, session: Session = Depends(get_session)):
    c = get_or_404(session, Client, client_id, tenant_id)
    if has_future_scheduled(session, client_id=c.id):
        raise ApiError("invalid_state", "client has upcoming scheduled bookings", 409)
    session.delete(c)
    session.commit()
    return Response(status_code=204)
