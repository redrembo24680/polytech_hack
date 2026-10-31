from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class AgentPermissions(BaseModel):
    reschedule: Literal["auto", "approval"]
    cancel: Literal["auto", "approval"]
    refund: Literal["auto_under_limit", "approval", "forbidden"]
    refund_auto_limit: int = 0
    goodwill_exception: Literal["auto", "approval", "forbidden"]
    goodwill_per_client_per_180d: int = 0
    goodwill_requires_zero_no_shows: bool = False
    waive_no_show_fee: Literal["auto", "approval", "forbidden"]


class Policy(BaseModel):
    rules_text: str
    cancellation_window_hours: int
    late_change_forfeits_prepayment: bool
    no_show_fee: int
    prepayment_required: bool
    agent_permissions: AgentPermissions


class Tenant(BaseModel):
    id: str
    name: str
    kind: Literal["salon", "clinic"]
    timezone: str
    policy: Policy


class GoodwillException(BaseModel):
    date: datetime
    booking_id: str
    reason: str


class Client(BaseModel):
    id: str
    tenant_id: str
    name: str
    phone: str
    visits_count: int
    no_show_count: int
    goodwill_exceptions: list[GoodwillException] = Field(default_factory=list)
    notes: str = ""


class Staff(BaseModel):
    id: str
    tenant_id: str
    name: str
    service_ids: list[str]


class Service(BaseModel):
    id: str
    tenant_id: str
    name: str
    duration_min: int
    price: int


class Prepayment(BaseModel):
    amount: int
    status: Literal["held", "refunded", "forfeited", "none"]


class HistoryEntry(BaseModel):
    ts: datetime
    event: str
    by: str
    note: str


class Booking(BaseModel):
    id: str
    tenant_id: str
    client_id: str
    staff_id: str
    service_id: str
    start: datetime
    end: datetime
    status: Literal["scheduled", "completed", "cancelled", "no_show"]
    prepayment: Prepayment
    history: list[HistoryEntry] = Field(default_factory=list)


class Slot(BaseModel):
    staff_id: str
    staff_name: str
    start: datetime
    end: datetime


class OutgoingMessage(BaseModel):
    id: str
    tenant_id: str
    client_id: str
    channel: Literal["chat", "sms"]
    text: str
    ts: datetime


class Ticket(BaseModel):
    id: str
    tenant_id: str
    client_id: str
    summary: str
    priority: Literal["low", "normal", "high", "urgent"]
    status: Literal["open", "closed"]
    ts: datetime
