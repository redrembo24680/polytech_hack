from sqlalchemy.orm import Session

from booking.errors import ApiError
from booking.models import Tenant


def not_found() -> ApiError:
    return ApiError("not_found", "not found", 404)


def get_tenant_or_404(session: Session, tenant_id: str) -> Tenant:
    t = session.get(Tenant, tenant_id)
    if t is None:
        raise not_found()
    return t


def get_or_404(session: Session, model, entity_id: str, tenant_id: str):
    """Fetch entity by id, 404 if missing or owned by another tenant."""
    get_tenant_or_404(session, tenant_id)
    obj = session.get(model, entity_id)
    if obj is None or obj.tenant_id != tenant_id:
        raise not_found()
    return obj
