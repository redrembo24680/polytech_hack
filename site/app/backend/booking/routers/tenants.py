import re

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from booking.db import get_session
from booking.ids import new_id
from booking.models import Tenant
from booking.routers.deps import get_tenant_or_404
from booking.seed import LUMEN_POLICY
from booking.schemas import Policy, TenantKind, tenant_out

router = APIRouter(prefix="/api/tenants")


class TenantIn(BaseModel):
    name: str
    kind: TenantKind
    timezone: str = "Europe/Kyiv"
    description: str = ""
    address: str = ""
    phone: str = ""
    instagram: str | None = None
    policy: Policy | None = None


class TenantPatch(BaseModel):
    name: str | None = None
    kind: TenantKind | None = None
    timezone: str | None = None
    description: str | None = None
    address: str | None = None
    phone: str | None = None
    instagram: str | None = None


def _slug(name: str) -> str | None:
    if not name.isascii():
        return None
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or None


@router.get("")
def list_tenants(session: Session = Depends(get_session)):
    return [tenant_out(t) for t in session.scalars(select(Tenant).order_by(Tenant.id))]


@router.post("", status_code=201)
def create_tenant(body: TenantIn, session: Session = Depends(get_session)):
    tid = _slug(body.name)
    if tid is None or session.get(Tenant, tid) is not None:
        tid = new_id("t")
    policy = body.policy or Policy.model_validate(LUMEN_POLICY)
    t = Tenant(
        id=tid, name=body.name, kind=body.kind, timezone=body.timezone,
        description=body.description, address=body.address, phone=body.phone,
        instagram=body.instagram, policy=policy.model_dump(),
    )
    session.add(t)
    session.commit()
    return tenant_out(t)


@router.get("/{tenant_id}")
def get_tenant(tenant_id: str, session: Session = Depends(get_session)):
    return tenant_out(get_tenant_or_404(session, tenant_id))


@router.patch("/{tenant_id}")
def patch_tenant(tenant_id: str, body: TenantPatch, session: Session = Depends(get_session)):
    t = get_tenant_or_404(session, tenant_id)
    for k, v in body.model_dump(exclude_unset=True).items():
        if v is None and k != "instagram":
            continue
        setattr(t, k, v)
    session.commit()
    return tenant_out(t)


@router.delete("/{tenant_id}", status_code=204)
def delete_tenant(tenant_id: str, session: Session = Depends(get_session)):
    session.delete(get_tenant_or_404(session, tenant_id))
    session.commit()
    return Response(status_code=204)


@router.put("/{tenant_id}/policy")
def put_policy(tenant_id: str, body: Policy, session: Session = Depends(get_session)):
    t = get_tenant_or_404(session, tenant_id)
    t.policy = body.model_dump()  # whole new dict: JSONB has no mutation tracking
    session.commit()
    return tenant_out(t)
