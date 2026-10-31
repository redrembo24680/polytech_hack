from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from booking.db import get_session
from booking.errors import ApiError
from booking.ids import new_id
from booking.models import Service
from booking.routers.deps import get_or_404, get_tenant_or_404
from booking.schemas import service_out
from booking.services.bookings import has_future_scheduled

router = APIRouter(prefix="/api/tenants/{tenant_id}/services")


class ServiceIn(BaseModel):
    name: str
    duration_min: int = Field(gt=0)
    price: int = Field(ge=0)


class ServicePatch(BaseModel):
    name: str | None = None
    duration_min: int | None = Field(default=None, gt=0)
    price: int | None = Field(default=None, ge=0)


@router.get("")
def list_services(tenant_id: str, session: Session = Depends(get_session)):
    get_tenant_or_404(session, tenant_id)
    rows = session.scalars(select(Service).where(Service.tenant_id == tenant_id).order_by(Service.id))
    return [service_out(s) for s in rows]


@router.post("", status_code=201)
def create_service(tenant_id: str, body: ServiceIn, session: Session = Depends(get_session)):
    get_tenant_or_404(session, tenant_id)
    s = Service(id=new_id("sv"), tenant_id=tenant_id, **body.model_dump())
    session.add(s)
    session.commit()
    return service_out(s)


@router.get("/{service_id}")
def get_service(tenant_id: str, service_id: str, session: Session = Depends(get_session)):
    return service_out(get_or_404(session, Service, service_id, tenant_id))


@router.patch("/{service_id}")
def patch_service(tenant_id: str, service_id: str, body: ServicePatch,
                  session: Session = Depends(get_session)):
    s = get_or_404(session, Service, service_id, tenant_id)
    for k, v in body.model_dump(exclude_unset=True).items():
        if v is not None:
            setattr(s, k, v)
    session.commit()
    return service_out(s)


@router.delete("/{service_id}", status_code=204)
def delete_service(tenant_id: str, service_id: str, session: Session = Depends(get_session)):
    s = get_or_404(session, Service, service_id, tenant_id)
    if has_future_scheduled(session, service_id=s.id):
        raise ApiError("invalid_state", "service has upcoming scheduled bookings", 409)
    session.delete(s)
    session.commit()
    return Response(status_code=204)
