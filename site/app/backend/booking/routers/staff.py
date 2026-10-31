from datetime import time

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from booking.db import get_session
from booking.errors import ApiError
from booking.ids import new_id
from booking.models import Service, Staff, StaffSchedule
from booking.routers.deps import get_or_404, get_tenant_or_404
from booking.schemas import staff_out
from booking.services.bookings import has_future_scheduled

router = APIRouter(prefix="/api/tenants/{tenant_id}/staff")


class StaffIn(BaseModel):
    name: str
    service_ids: list[str] = []


class StaffPatch(BaseModel):
    name: str | None = None
    service_ids: list[str] | None = None


class ScheduleDay(BaseModel):
    weekday: int
    start: time
    end: time

    @model_validator(mode="after")
    def _check(self):
        if not 0 <= self.weekday <= 6:
            raise ValueError("weekday must be 0-6")
        if self.start >= self.end:
            raise ValueError("start must be before end")
        return self


def _services(session: Session, tenant_id: str, ids: list[str]) -> list[Service]:
    found = {}
    for sid in dict.fromkeys(ids):
        sv = session.get(Service, sid)
        if sv is None or sv.tenant_id != tenant_id:
            raise ApiError("validation", f"unknown service_id: {sid}", 422)
        found[sid] = sv
    return list(found.values())


@router.get("")
def list_staff(tenant_id: str, session: Session = Depends(get_session)):
    get_tenant_or_404(session, tenant_id)
    rows = session.scalars(select(Staff).where(Staff.tenant_id == tenant_id).order_by(Staff.id))
    return [staff_out(s) for s in rows]


@router.post("", status_code=201)
def create_staff(tenant_id: str, body: StaffIn, session: Session = Depends(get_session)):
    get_tenant_or_404(session, tenant_id)
    s = Staff(id=new_id("st"), tenant_id=tenant_id, name=body.name,
              services=_services(session, tenant_id, body.service_ids))
    session.add(s)
    session.commit()
    return staff_out(s)


@router.get("/{staff_id}")
def get_staff(tenant_id: str, staff_id: str, session: Session = Depends(get_session)):
    return staff_out(get_or_404(session, Staff, staff_id, tenant_id))


@router.patch("/{staff_id}")
def patch_staff(tenant_id: str, staff_id: str, body: StaffPatch,
                session: Session = Depends(get_session)):
    s = get_or_404(session, Staff, staff_id, tenant_id)
    if body.name is not None:
        s.name = body.name
    if body.service_ids is not None:
        s.services = _services(session, tenant_id, body.service_ids)
    session.commit()
    return staff_out(s)


@router.delete("/{staff_id}", status_code=204)
def delete_staff(tenant_id: str, staff_id: str, session: Session = Depends(get_session)):
    s = get_or_404(session, Staff, staff_id, tenant_id)
    if has_future_scheduled(session, staff_id=s.id):
        raise ApiError("invalid_state", "staff has upcoming scheduled bookings", 409)
    session.delete(s)
    session.commit()
    return Response(status_code=204)


@router.put("/{staff_id}/schedule")
def put_schedule(tenant_id: str, staff_id: str, body: list[ScheduleDay],
                 session: Session = Depends(get_session)):
    s = get_or_404(session, Staff, staff_id, tenant_id)
    if len({d.weekday for d in body}) != len(body):
        raise ApiError("validation", "duplicate weekday in schedule", 422)
    s.schedule = [
        StaffSchedule(staff_id=s.id, weekday=d.weekday, start_time=d.start, end_time=d.end)
        for d in body
    ]
    session.commit()
    session.refresh(s)
    return staff_out(s)
