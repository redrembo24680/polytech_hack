from collections.abc import Callable
from datetime import datetime
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field

EventType = Literal[
    "user_message",
    "assistant_message",
    "thinking",
    "tool_call",
    "tool_result",
    "card",
    "approval_created",
    "approval_decided",
    "error",
]

WRITE_TOOLS = frozenset(
    {
        "reschedule_booking",
        "cancel_booking",
        "refund_prepayment",
        "apply_goodwill_exception",
        "waive_no_show_fee",
    }
)


def _kyiv_now() -> datetime:
    return datetime.now(ZoneInfo("Europe/Kyiv"))


class Event(BaseModel):
    id: int
    ts: datetime
    session_id: str
    tenant_id: str
    type: EventType
    payload: dict = Field(default_factory=dict)


class EventLog:
    def __init__(self, now_fn: Callable[[], datetime] = _kyiv_now):
        self._now = now_fn
        self._events: list[Event] = []

    def emit(self, session_id: str, tenant_id: str, type: EventType, payload: dict) -> Event:
        event = Event(
            id=len(self._events) + 1,
            ts=self._now(),
            session_id=session_id,
            tenant_id=tenant_id,
            type=type,
            payload=payload,
        )
        self._events.append(event)
        return event

    def since(self, session_id: str, after_id: int = 0) -> list[Event]:
        return [e for e in self._events if e.session_id == session_id and e.id > after_id]

    def for_tenant(self, tenant_id: str) -> list[Event]:
        return [e for e in self._events if e.tenant_id == tenant_id]


class Approval(BaseModel):
    id: str
    session_id: str
    tenant_id: str
    tool: str
    args: dict
    reason: str
    status: Literal["pending", "approved", "rejected"] = "pending"
    decided_by: str | None = None
    note: str | None = None
    created_at: datetime
    decided_at: datetime | None = None


class ApprovalStore:
    def __init__(self, now_fn: Callable[[], datetime] = _kyiv_now):
        self._now = now_fn
        self._items: dict[str, Approval] = {}
        self._counter = 0

    def create(self, session_id: str, tenant_id: str, tool: str, args: dict, reason: str) -> Approval:
        self._counter += 1
        approval = Approval(
            id=f"ap-{self._counter}",
            session_id=session_id,
            tenant_id=tenant_id,
            tool=tool,
            args=args,
            reason=reason,
            created_at=self._now(),
        )
        self._items[approval.id] = approval
        return approval

    def get(self, approval_id: str) -> Approval:
        return self._items[approval_id]

    def pending(self, tenant_id: str) -> list[Approval]:
        return [a for a in self._items.values() if a.tenant_id == tenant_id and a.status == "pending"]

    def for_tenant(self, tenant_id: str) -> list[Approval]:
        return [a for a in self._items.values() if a.tenant_id == tenant_id]

    def decide(self, approval_id: str, approve: bool, by: str, note: str | None) -> Approval:
        approval = self.get(approval_id)
        if approval.status != "pending":
            raise ValueError("already_decided")
        approval.status = "approved" if approve else "rejected"
        approval.decided_by = by
        approval.note = note
        approval.decided_at = self._now()
        return approval


def metrics(log: EventLog, approvals: ApprovalStore, tenant_id: str) -> dict:
    events = log.for_tenant(tenant_id)
    calls = [e for e in events if e.type == "tool_call"]
    mine = approvals.for_tenant(tenant_id)
    return {
        "sessions": len({e.session_id for e in events}),
        "messages": sum(e.type == "user_message" for e in events),
        "tool_calls": len(calls),
        "auto_actions": sum(
            e.payload.get("decision") == "allow" and e.payload.get("name") in WRITE_TOOLS for e in calls
        ),
        "approvals_pending": sum(a.status == "pending" for a in mine),
        "approvals_approved": sum(a.status == "approved" for a in mine),
        "approvals_rejected": sum(a.status == "rejected" for a in mine),
        "escalations": sum(e.payload.get("name") == "escalate_to_human" for e in calls),
        "money_saved_uah": sum(e.payload.get("saved_uah", 0) for e in events if e.type == "tool_result"),
    }
