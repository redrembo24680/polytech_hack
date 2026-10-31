from collections.abc import Callable
import threading
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
    "triage",
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
        self._lock = threading.Lock()

    def emit(self, session_id: str, tenant_id: str, type: EventType, payload: dict) -> Event:
        with self._lock:
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
        with self._lock:
            snapshot = list(self._events)
        return [e for e in snapshot if e.session_id == session_id and e.id > after_id]

    def for_tenant(self, tenant_id: str) -> list[Event]:
        with self._lock:
            snapshot = list(self._events)
        return [e for e in snapshot if e.tenant_id == tenant_id]


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
        self._lock = threading.Lock()

    def _snapshot(self) -> list[Approval]:
        with self._lock:
            return list(self._items.values())

    def create(self, session_id: str, tenant_id: str, tool: str, args: dict, reason: str) -> Approval:
        with self._lock:
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
        with self._lock:
            return self._items[approval_id]

    def pending(self, tenant_id: str) -> list[Approval]:
        return [a for a in self._snapshot() if a.tenant_id == tenant_id and a.status == "pending"]

    def for_tenant(self, tenant_id: str) -> list[Approval]:
        return [a for a in self._snapshot() if a.tenant_id == tenant_id]

    def decide(self, approval_id: str, approve: bool, by: str, note: str | None) -> Approval:
        with self._lock:
            approval = self._items[approval_id]
            if approval.status != "pending":
                raise ValueError("already_decided")
            approval.status = "approved" if approve else "rejected"
            approval.decided_by = by
            approval.note = note
            approval.decided_at = self._now()
            return approval


def _saved_uah(payload: dict) -> int:
    result = payload.get("result")
    nested = result.get("saved_uah", 0) if isinstance(result, dict) else 0
    return payload.get("saved_uah", 0) + nested


def metrics(log: EventLog, approvals: ApprovalStore, tenant_id: str) -> dict:
    events = log.for_tenant(tenant_id)
    calls = [e for e in events if e.type == "tool_call"]
    mine = approvals.for_tenant(tenant_id)
    intents: dict[str, int] = {}
    emotions: dict[str, int] = {}
    for e in events:
        if e.type == "triage":
            key = str(e.payload.get("intent", "other"))
            intents[key] = intents.get(key, 0) + 1
            emo = str(e.payload.get("emotion", "calm"))
            emotions[emo] = emotions.get(emo, 0) + 1
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
        "intents": intents,
        "emotions": emotions,
        "money_saved_uah": sum(_saved_uah(e.payload) for e in events if e.type == "tool_result"),
    }
