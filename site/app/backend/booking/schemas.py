from datetime import datetime
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import object_session

from booking.models import Booking, Client

BookingStatus = Literal["scheduled", "completed", "cancelled", "no_show"]
PrepaymentStatus = Literal["held", "refunded", "forfeited", "none"]
NoShowFeeStatus = Literal["charged", "waived", "none"]
Channel = Literal["chat", "sms"]
Priority = Literal["low", "normal", "high", "urgent"]
TicketStatus = Literal["open", "closed"]
TenantKind = Literal["salon", "clinic"]
ChatRole = Literal["client", "agent", "human"]
ConversationStatus = Literal["open", "closed"]
Auto = Literal["auto", "approval"]
Gate = Literal["auto", "approval", "forbidden"]


class AgentPermissions(BaseModel):
    reschedule: Auto
    cancel: Auto
    refund: Literal["auto_under_limit", "approval", "forbidden"]
    refund_auto_limit: int
    goodwill_exception: Gate
    goodwill_per_client_per_180d: int
    goodwill_requires_zero_no_shows: bool
    waive_no_show_fee: Gate


class Policy(BaseModel):
    cancellation_window_hours: int
    late_change_forfeits_prepayment: bool
    no_show_fee: int
    prepayment_required: bool
    agent_permissions: AgentPermissions


def iso(dt: datetime, tz: str = "Europe/Kyiv") -> str:
    return dt.astimezone(ZoneInfo(tz)).isoformat()


def tenant_out(t) -> dict:
    return {
        "id": t.id, "name": t.name, "kind": t.kind, "timezone": t.timezone,
        "description": t.description, "address": t.address, "phone": t.phone,
        "instagram": t.instagram,
        "policy": Policy.model_validate(t.policy).model_dump(),
    }


def staff_out(s) -> dict:
    return {
        "id": s.id, "tenant_id": s.tenant_id, "name": s.name,
        "service_ids": [sv.id for sv in s.services],
        "schedule": [
            {"weekday": r.weekday, "start": r.start_time.strftime("%H:%M"),
             "end": r.end_time.strftime("%H:%M")}
            for r in s.schedule
        ],
    }


def service_out(s) -> dict:
    return {
        "id": s.id, "tenant_id": s.tenant_id, "name": s.name,
        "duration_min": s.duration_min, "price": s.price,
    }


def client_out(c, session, with_bookings: bool = False) -> dict:
    bookings = session.scalars(
        select(Booking).where(Booking.client_id == c.id).order_by(Booking.start.desc())
    ).all()
    out = {
        "id": c.id, "tenant_id": c.tenant_id, "name": c.name, "phone": c.phone,
        "visits_count": sum(b.status == "completed" for b in bookings),
        "no_show_count": sum(b.status == "no_show" for b in bookings),
        "goodwill_exceptions": [
            {"date": g.date.isoformat(), "booking_id": g.booking_id, "reason": g.reason}
            for g in c.goodwill_exceptions
        ],
        "notes": c.notes,
    }
    if with_bookings:
        out["bookings"] = [booking_out(b, expand=False) for b in bookings]
    return out


def booking_out(b, expand: bool = False) -> dict:
    tz = b.tenant.timezone
    out = {
        "id": b.id, "tenant_id": b.tenant_id, "client_id": b.client_id,
        "staff_id": b.staff_id, "service_id": b.service_id,
        "start": iso(b.start, tz), "end": iso(b.end, tz), "status": b.status,
        "prepayment": {"amount": b.prepayment_amount, "status": b.prepayment_status},
        "no_show_fee": {"amount": b.no_show_fee_amount, "status": b.no_show_fee_status},
        "history": [
            {"ts": iso(e.ts, tz), "event": e.event, "by": e.by, "note": e.note}
            for e in sorted(b.events, key=lambda e: e.ts)
        ],
        "notes": b.notes,
    }
    if expand:
        out["client"] = client_out(b.client, object_session(b), with_bookings=False)
        out["staff"] = staff_out(b.staff)
        out["service"] = service_out(b.service)
    return out


def message_out(m) -> dict:
    return {
        "id": m.id, "tenant_id": m.tenant_id, "client_id": m.client_id,
        "channel": m.channel, "text": m.text, "ts": iso(m.ts, m.tenant.timezone),
    }


def ticket_out(t) -> dict:
    return {
        "id": t.id, "tenant_id": t.tenant_id, "client_id": t.client_id,
        "summary": t.summary, "priority": t.priority, "status": t.status,
        "ts": iso(t.ts, t.tenant.timezone),
    }


def conversation_out(c) -> dict:
    return {
        "id": c.id, "tenant_id": c.tenant_id, "client_id": c.client_id,
        "status": c.status, "created_at": iso(c.created_at, c.tenant.timezone),
    }


def chat_message_out(m) -> dict:
    return {
        "id": m.id, "conversation_id": m.conversation_id, "role": m.role,
        "text": m.text, "ts": iso(m.ts, m.conversation.tenant.timezone),
    }
