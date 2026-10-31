from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from booking import clock
from booking.db import get_session
from booking.errors import ApiError
from booking.models import Service, Staff
from booking.routers.deps import get_or_404, get_tenant_or_404
from booking.schemas import iso
from booking.services.slots import find_free_slots
from booking.timeparse import parse_when

router = APIRouter(prefix="/api/tenants/{tenant_id}")


@router.get("/slots")
def get_slots(tenant_id: str, service_id: str, from_: str = Query(alias="from"),
              to: str = Query(), staff_id: str | None = None,
              session: Session = Depends(get_session)):
    tenant = get_tenant_or_404(session, tenant_id)
    service = get_or_404(session, Service, service_id, tenant_id)
    if staff_id is not None:
        get_or_404(session, Staff, staff_id, tenant_id)
    start = parse_when(from_, tenant.timezone, "from")
    end = parse_when(to, tenant.timezone, "to")
    if end <= start:
        raise ApiError("validation", "to: must be after from", 422)
    slots = find_free_slots(session, tenant, service, start, end, staff_id, clock.now())
    return [{"staff_id": s["staff_id"], "staff_name": s["staff_name"],
             "start": iso(s["start"], tenant.timezone), "end": iso(s["end"], tenant.timezone)}
            for s in slots]
