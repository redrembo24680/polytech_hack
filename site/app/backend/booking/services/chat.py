from datetime import timedelta

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from booking import clock
from booking.config import settings
from booking.ids import new_id
from booking.models import ChatMessage, Conversation
from booking.schemas import iso

STUB_NO_AGENT = "Агент підтримки ще не підключений"
STUB_UNAVAILABLE = "Агент тимчасово недоступний, адміністратор відповість найближчим часом"


def add_message(session: Session, conv: Conversation, role: str, text: str) -> ChatMessage:
    """Append a message; ts is strictly increasing within the conversation."""
    ts = clock.now()
    last = session.scalar(
        select(func.max(ChatMessage.ts)).where(ChatMessage.conversation_id == conv.id))
    if last is not None and ts <= last:
        ts = last + timedelta(milliseconds=1)
    m = ChatMessage(id=new_id("cm"), conversation_id=conv.id, role=role, text=text, ts=ts)
    session.add(m)
    session.flush()
    return m


def history(session: Session, conv: Conversation) -> list[ChatMessage]:
    return list(session.scalars(select(ChatMessage).where(
        ChatMessage.conversation_id == conv.id).order_by(ChatMessage.ts, ChatMessage.id)))


def build_agent_payload(conversation: Conversation, messages: list[ChatMessage]) -> dict:
    tz = conversation.tenant.timezone
    return {
        "tenant_id": conversation.tenant_id,
        "conversation_id": conversation.id,
        "client_id": conversation.client_id,
        "visitor_name": conversation.visitor_name,
        "visitor_phone": conversation.visitor_phone,
        "messages": [{"role": m.role, "text": m.text, "ts": iso(m.ts, tz)} for m in messages],
    }


def forward_to_agent(payload: dict) -> str | None:
    """Send the conversation payload to the agent (no DB access: callers end their
    transaction first). Returns reply text, None for 'no reply', or a stub text when
    the agent is absent/unavailable."""
    agent_url = settings.agent_url  # read at call time
    if not agent_url:
        return STUB_NO_AGENT
    try:
        resp = httpx.post(f"{agent_url.rstrip('/')}/chat", json=payload,
                          timeout=settings.agent_timeout)
        resp.raise_for_status()
        data = resp.json()
        reply = data.get("reply")
    except Exception:
        return STUB_UNAVAILABLE
    if not isinstance(reply, str) or not reply.strip():
        return None
    return reply
