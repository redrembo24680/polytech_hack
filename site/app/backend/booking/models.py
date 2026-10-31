from datetime import date, datetime, time

from sqlalchemy import (
    Date, DateTime, ForeignKey, Integer, String, Text, Time, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from booking import clock
from booking.db import Base
from booking.ids import new_id

CASCADE = {"ondelete": "CASCADE"}
TS = DateTime(timezone=True)


class Tenant(Base):
    __tablename__ = "tenants"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    kind: Mapped[str] = mapped_column(String)
    timezone: Mapped[str] = mapped_column(String, default="Europe/Kyiv")
    description: Mapped[str] = mapped_column(Text, default="")
    address: Mapped[str] = mapped_column(String, default="")
    phone: Mapped[str] = mapped_column(String, default="")
    instagram: Mapped[str | None] = mapped_column(String, nullable=True)
    policy: Mapped[dict] = mapped_column(JSONB, default=dict)


class Service(Base):
    __tablename__ = "services"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", **CASCADE), index=True)
    name: Mapped[str] = mapped_column(String)
    duration_min: Mapped[int] = mapped_column(Integer)
    price: Mapped[int] = mapped_column(Integer)
    tenant: Mapped[Tenant] = relationship()


class StaffService(Base):
    __tablename__ = "staff_services"
    staff_id: Mapped[str] = mapped_column(ForeignKey("staff.id", **CASCADE), primary_key=True)
    service_id: Mapped[str] = mapped_column(ForeignKey("services.id", **CASCADE), primary_key=True)


class Staff(Base):
    __tablename__ = "staff"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", **CASCADE), index=True)
    name: Mapped[str] = mapped_column(String)
    tenant: Mapped[Tenant] = relationship()
    services: Mapped[list[Service]] = relationship(secondary="staff_services", order_by="Service.id")
    schedule: Mapped[list["StaffSchedule"]] = relationship(
        cascade="all, delete-orphan", passive_deletes=True, order_by="StaffSchedule.weekday"
    )


class StaffSchedule(Base):
    __tablename__ = "staff_schedule"
    staff_id: Mapped[str] = mapped_column(ForeignKey("staff.id", **CASCADE), primary_key=True)
    weekday: Mapped[int] = mapped_column(Integer, primary_key=True)  # 0=Mon..6=Sun
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)


class Client(Base):
    __tablename__ = "clients"
    __table_args__ = (UniqueConstraint("tenant_id", "phone", name="uq_client_tenant_phone"),)
    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", **CASCADE), index=True)
    name: Mapped[str] = mapped_column(String)
    phone: Mapped[str] = mapped_column(String)
    notes: Mapped[str] = mapped_column(Text, default="")
    tenant: Mapped[Tenant] = relationship()
    goodwill_exceptions: Mapped[list["GoodwillException"]] = relationship(
        cascade="all, delete-orphan", passive_deletes=True, order_by="GoodwillException.date"
    )


class Booking(Base):
    __tablename__ = "bookings"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", **CASCADE), index=True)
    client_id: Mapped[str] = mapped_column(ForeignKey("clients.id", **CASCADE), index=True)
    staff_id: Mapped[str] = mapped_column(ForeignKey("staff.id", **CASCADE), index=True)
    service_id: Mapped[str] = mapped_column(ForeignKey("services.id", **CASCADE), index=True)
    start: Mapped[datetime] = mapped_column(TS)
    end: Mapped[datetime] = mapped_column(TS)
    status: Mapped[str] = mapped_column(String, default="scheduled")
    prepayment_amount: Mapped[int] = mapped_column(Integer, default=0)
    prepayment_status: Mapped[str] = mapped_column(String, default="none")
    no_show_fee_amount: Mapped[int] = mapped_column(Integer, default=0)
    no_show_fee_status: Mapped[str] = mapped_column(String, default="none")
    notes: Mapped[str] = mapped_column(Text, default="")
    tenant: Mapped[Tenant] = relationship()
    client: Mapped[Client] = relationship()
    staff: Mapped[Staff] = relationship()
    service: Mapped[Service] = relationship()
    events: Mapped[list["BookingEvent"]] = relationship(
        cascade="all, delete-orphan", passive_deletes=True, order_by="BookingEvent.ts, BookingEvent.id"
    )


class GoodwillException(Base):
    __tablename__ = "goodwill_exceptions"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    client_id: Mapped[str] = mapped_column(ForeignKey("clients.id", **CASCADE), index=True)
    booking_id: Mapped[str] = mapped_column(ForeignKey("bookings.id", **CASCADE))
    date: Mapped[date] = mapped_column(Date)
    reason: Mapped[str] = mapped_column(Text, default="")


class BookingEvent(Base):
    __tablename__ = "booking_events"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    booking_id: Mapped[str] = mapped_column(ForeignKey("bookings.id", **CASCADE), index=True)
    ts: Mapped[datetime] = mapped_column(TS)
    event: Mapped[str] = mapped_column(String)
    by: Mapped[str] = mapped_column(String)
    note: Mapped[str] = mapped_column(Text, default="")


class OutgoingMessage(Base):
    __tablename__ = "outgoing_messages"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", **CASCADE), index=True)
    client_id: Mapped[str] = mapped_column(ForeignKey("clients.id", **CASCADE), index=True)
    channel: Mapped[str] = mapped_column(String)
    text: Mapped[str] = mapped_column(Text)
    ts: Mapped[datetime] = mapped_column(TS)
    tenant: Mapped[Tenant] = relationship()


class Ticket(Base):
    __tablename__ = "tickets"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", **CASCADE), index=True)
    client_id: Mapped[str] = mapped_column(ForeignKey("clients.id", **CASCADE), index=True)
    summary: Mapped[str] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(String, default="normal")
    status: Mapped[str] = mapped_column(String, default="open")
    ts: Mapped[datetime] = mapped_column(TS)
    tenant: Mapped[Tenant] = relationship()


class Conversation(Base):
    __tablename__ = "conversations"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", **CASCADE), index=True)
    client_id: Mapped[str | None] = mapped_column(
        ForeignKey("clients.id", **CASCADE), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String, default="open")
    created_at: Mapped[datetime] = mapped_column(TS)
    tenant: Mapped[Tenant] = relationship()


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", **CASCADE), index=True
    )
    role: Mapped[str] = mapped_column(String)  # client|agent|human
    text: Mapped[str] = mapped_column(Text)
    ts: Mapped[datetime] = mapped_column(TS)
    conversation: Mapped[Conversation] = relationship()


def add_event(session, booking: Booking, event: str, by: str, note: str = "") -> BookingEvent:
    ev = BookingEvent(
        id=new_id("ev"), booking_id=booking.id, ts=clock.now(), event=event, by=by, note=note
    )
    session.add(ev)
    session.flush()
    session.expire(booking, ["events"])
    return ev
