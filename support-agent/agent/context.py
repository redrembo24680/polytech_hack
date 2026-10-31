from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime

from agent.datasource import DataSource
from agent.events import ApprovalStore, EventLog


@dataclass
class SessionCtx:
    session_id: str
    tenant_id: str
    client_id: str | None
    now: datetime
    ds: DataSource
    events: EventLog
    approvals: ApprovalStore
    goodwill_applied: set[str] = field(default_factory=set)


current: ContextVar[SessionCtx] = ContextVar("current_session_ctx")


@contextmanager
def use(ctx: SessionCtx):
    token = current.set(ctx)
    try:
        yield ctx
    finally:
        current.reset(token)


def get_ctx() -> SessionCtx:
    try:
        return current.get()
    except LookupError:
        raise RuntimeError("no active session context") from None
