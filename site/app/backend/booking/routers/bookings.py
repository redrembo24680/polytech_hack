from fastapi import APIRouter

router = APIRouter(prefix="/api/tenants/{tenant_id}/bookings")
