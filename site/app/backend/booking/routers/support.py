from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from booking import clock
from booking.db import get_session
from booking.errors import ApiError
from booking.ids import new_id
from booking.models import ChatMessage, Client, Conversation
from booking.phone import normalize_phone
from booking.routers.deps import get_or_404, get_tenant_or_404
from booking.schemas import chat_message_out, conversation_out, iso
from booking.services import chat
from booking.timeparse import parse_when

router = APIRouter(prefix="/api/tenants/{tenant_id}/support/conversations")


class ConversationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    client_phone: str | None = None
    client_name: str | None = None


class TextIn(BaseModel):
    text: str


class ReplyIn(BaseModel):
    text: str
    role: Literal["agent", "human"]


class ConversationPatch(BaseModel):
    status: Literal["open", "closed"] | None = None
    client_id: str | None = None


def _require_open(conv: Conversation) -> None:
    if conv.status != "open":
        raise ApiError("invalid_state", "conversation is closed", 409)


@router.post("", status_code=201)
def create_conversation(tenant_id: str, body: ConversationIn,
                        session: Session = Depends(get_session)):
    get_tenant_or_404(session, tenant_id)
    client_id = None
    phone = normalize_phone(body.client_phone) if body.client_phone else ""
    if phone:
        client_id = session.scalar(select(Client.id).where(
            Client.tenant_id == tenant_id, Client.phone == phone))
    conv = Conversation(id=new_id("conv"), tenant_id=tenant_id, client_id=client_id,
                        status="open", created_at=clock.now(),
                        visitor_name=(body.client_name or "").strip() or None,
                        visitor_phone=phone or None)
    session.add(conv)
    session.commit()
    return conversation_out(conv)


@router.get("")
def list_conversations(tenant_id: str, status: Literal["open", "closed"] | None = None,
                       session: Session = Depends(get_session)):
    tenant = get_tenant_or_404(session, tenant_id)
    q = select(Conversation).where(Conversation.tenant_id == tenant_id)
    if status is not None:
        q = q.where(Conversation.status == status)
    out = []
    for c in session.scalars(q):
        last = session.scalars(select(ChatMessage).where(ChatMessage.conversation_id == c.id)
                               .order_by(ChatMessage.ts.desc(), ChatMessage.id.desc())
                               .limit(1)).first()
        name = session.get(Client, c.client_id).name if c.client_id else c.visitor_name
        d = conversation_out(c)
        d["client_name"] = name
        d["last_message"] = (
            {"text": last.text, "role": last.role, "ts": iso(last.ts, tenant.timezone)}
            if last else None)
        out.append((last.ts if last else c.created_at, d))
    out.sort(key=lambda p: p[0], reverse=True)
    return [d for _, d in out]


@router.get("/{conversation_id}")
def get_conversation(tenant_id: str, conversation_id: str,
                     session: Session = Depends(get_session)):
    return conversation_out(get_or_404(session, Conversation, conversation_id, tenant_id))


@router.get("/{conversation_id}/messages")
def list_messages(tenant_id: str, conversation_id: str, after: str | None = None,
                  session: Session = Depends(get_session)):
    conv = get_or_404(session, Conversation, conversation_id, tenant_id)
    q = select(ChatMessage).where(ChatMessage.conversation_id == conv.id)
    if after is not None:
        q = q.where(ChatMessage.ts > parse_when(after, conv.tenant.timezone, "after"))
    return [chat_message_out(m) for m in session.scalars(q.order_by(ChatMessage.ts, ChatMessage.id))]


@router.post("/{conversation_id}/messages", status_code=201)
def post_client_message(tenant_id: str, conversation_id: str, body: TextIn,
                        session: Session = Depends(get_session)):
    conv = get_or_404(session, Conversation, conversation_id, tenant_id)
    _require_open(conv)
    created = [chat.add_message(session, conv, "client", body.text)]
    session.commit()
    payload = chat.build_agent_payload(conv, chat.history(session, conv))
    session.commit()  # end the read transaction: no connection held during the webhook
    reply = chat.forward_to_agent(payload)
    if reply is not None:
        created.append(chat.add_message(session, conv, "agent", reply))
        session.commit()
    return [chat_message_out(m) for m in created]


@router.post("/{conversation_id}/reply", status_code=201)
def reply(tenant_id: str, conversation_id: str, body: ReplyIn,
          session: Session = Depends(get_session)):
    conv = get_or_404(session, Conversation, conversation_id, tenant_id)
    _require_open(conv)
    m = chat.add_message(session, conv, body.role, body.text)
    session.commit()
    return chat_message_out(m)


@router.patch("/{conversation_id}")
def patch_conversation(tenant_id: str, conversation_id: str, body: ConversationPatch,
                       session: Session = Depends(get_session)):
    conv = get_or_404(session, Conversation, conversation_id, tenant_id)
    if body.status is not None:
        conv.status = body.status
    if body.client_id is not None:
        get_or_404(session, Client, body.client_id, tenant_id)
        conv.client_id = body.client_id
    session.commit()
    return conversation_out(conv)
