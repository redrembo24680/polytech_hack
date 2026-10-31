from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from booking import clock
from booking.db import get_session
from booking.ids import new_id
from booking.models import Client, OutgoingMessage, Ticket
from booking.routers.deps import get_or_404, get_tenant_or_404
from booking.schemas import Channel, Priority, TicketStatus, message_out, ticket_out

router = APIRouter(prefix="/api/tenants/{tenant_id}")


class MessageIn(BaseModel):
    client_id: str
    channel: Channel = "chat"
    text: str


class TicketIn(BaseModel):
    client_id: str
    summary: str
    priority: Priority = "normal"


class TicketPatch(BaseModel):
    status: TicketStatus


@router.post("/messages", status_code=201)
def post_message(tenant_id: str, body: MessageIn, session: Session = Depends(get_session)):
    get_or_404(session, Client, body.client_id, tenant_id)
    m = OutgoingMessage(id=new_id("msg"), tenant_id=tenant_id, client_id=body.client_id,
                        channel=body.channel, text=body.text, ts=clock.now())
    session.add(m)
    session.commit()
    return message_out(m)


@router.get("/messages")
def list_messages(tenant_id: str, client_id: str | None = None,
                  session: Session = Depends(get_session)):
    get_tenant_or_404(session, tenant_id)
    q = select(OutgoingMessage).where(OutgoingMessage.tenant_id == tenant_id)
    if client_id is not None:
        q = q.where(OutgoingMessage.client_id == client_id)
    return [message_out(m) for m in session.scalars(q.order_by(OutgoingMessage.ts, OutgoingMessage.id))]


@router.post("/tickets", status_code=201)
def post_ticket(tenant_id: str, body: TicketIn, session: Session = Depends(get_session)):
    get_or_404(session, Client, body.client_id, tenant_id)
    t = Ticket(id=new_id("t"), tenant_id=tenant_id, client_id=body.client_id,
               summary=body.summary, priority=body.priority, status="open", ts=clock.now())
    session.add(t)
    session.commit()
    return ticket_out(t)


@router.get("/tickets")
def list_tickets(tenant_id: str, status: TicketStatus | None = None,
                 session: Session = Depends(get_session)):
    get_tenant_or_404(session, tenant_id)
    q = select(Ticket).where(Ticket.tenant_id == tenant_id)
    if status is not None:
        q = q.where(Ticket.status == status)
    return [ticket_out(t) for t in session.scalars(q.order_by(Ticket.ts, Ticket.id))]


@router.patch("/tickets/{ticket_id}")
def patch_ticket(tenant_id: str, ticket_id: str, body: TicketPatch,
                 session: Session = Depends(get_session)):
    t = get_or_404(session, Ticket, ticket_id, tenant_id)
    t.status = body.status
    session.commit()
    return ticket_out(t)
