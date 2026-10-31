from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from booking.models import (
    Booking, ChatMessage, Client, Conversation, GoodwillException,
    OutgoingMessage, Service, Staff, StaffSchedule, Tenant, Ticket, add_event,
)
from booking.schemas import (
    Policy, booking_out, chat_message_out, client_out, conversation_out,
    message_out, service_out, staff_out, tenant_out, ticket_out,
)
from tests.conftest import NOW

KYIV = ZoneInfo("Europe/Kyiv")
POLICY = {
    "cancellation_window_hours": 24, "late_change_forfeits_prepayment": True,
    "no_show_fee": 500, "prepayment_required": False,
    "agent_permissions": {
        "reschedule": "auto", "cancel": "approval", "refund": "auto_under_limit",
        "refund_auto_limit": 300, "goodwill_exception": "approval",
        "goodwill_per_client_per_180d": 1, "goodwill_requires_zero_no_shows": True,
        "waive_no_show_fee": "forbidden",
    },
}


def _setup(session):
    t = Tenant(id="t-test", name="T", kind="salon", timezone="Europe/Kyiv",
               description="d", address="a", phone="1", policy=Policy(**POLICY).model_dump())
    sv = Service(id="s-test", tenant_id="t-test", name="Cut", duration_min=60, price=700)
    st = Staff(id="st-test", tenant_id="t-test", name="Olena", services=[sv])
    c = Client(id="c-test", tenant_id="t-test", name="Anna", phone="380671234567", notes="")
    session.add_all([t, sv, st, c, StaffSchedule(staff_id="st-test", weekday=0,
                     start_time=datetime(2000, 1, 1, 9).time(), end_time=datetime(2000, 1, 1, 18).time())])
    session.flush()
    b1 = Booking(id="b-test-1", tenant_id="t-test", client_id="c-test", staff_id="st-test",
                 service_id="s-test", start=datetime(2026, 11, 3, 10, tzinfo=KYIV),
                 end=datetime(2026, 11, 3, 11, tzinfo=KYIV), status="completed")
    b2 = Booking(id="b-test-2", tenant_id="t-test", client_id="c-test", staff_id="st-test",
                 service_id="s-test", start=datetime(2026, 11, 5, 10, tzinfo=KYIV),
                 end=datetime(2026, 11, 5, 11, tzinfo=KYIV), status="no_show",
                 no_show_fee_amount=500, no_show_fee_status="charged")
    session.add_all([b1, b2])
    session.flush()
    session.add(GoodwillException(id="g-test", client_id="c-test", booking_id="b-test-1",
                                  date=date(2026, 10, 1), reason="late"))
    add_event(session, b1, "created", "agent", "hi")
    session.commit()
    return t, c, b1, b2


def test_serializers(session):
    t, c, b1, b2 = _setup(session)
    out = client_out(c, session, with_bookings=True)
    assert out["visits_count"] == 1 and out["no_show_count"] == 1
    assert out["goodwill_exceptions"] == [{"date": "2026-10-01", "booking_id": "b-test-1", "reason": "late"}]
    assert [b["id"] for b in out["bookings"]] == ["b-test-2", "b-test-1"]
    assert "bookings" not in client_out(c, session, with_bookings=False)

    bo = booking_out(b1, expand=True)
    for k in ("prepayment", "no_show_fee", "history", "client", "staff", "service"):
        assert k in bo
    assert bo["start"].endswith("+02:00")
    assert bo["client"]["visits_count"] == 1 and bo["client"]["no_show_count"] == 1
    assert bo["client"]["tenant_id"] == "t-test" and len(bo["client"]["goodwill_exceptions"]) == 1
    assert "notes" in bo["client"]
    assert bo["prepayment"] == {"amount": 0, "status": "none"}
    assert bo["history"][0]["event"] == "created" and bo["history"][0]["by"] == "agent"
    assert "client" not in booking_out(b1, expand=False)
    assert booking_out(b2, expand=False)["no_show_fee"] == {"amount": 500, "status": "charged"}

    assert tenant_out(t)["policy"]["agent_permissions"]["refund"] == "auto_under_limit"
    assert staff_out(b1.staff)["service_ids"] == ["s-test"]
    assert service_out(b1.service)["price"] == 700


def test_messages_tickets_chat(session):
    t, c, *_ = _setup(session)
    m = OutgoingMessage(id="m-test", tenant_id="t-test", client_id="c-test", channel="sms",
                        text="x", ts=NOW)
    tk = Ticket(id="tk-test", tenant_id="t-test", client_id="c-test", summary="s",
                priority="high", status="open", ts=NOW)
    cv = Conversation(id="cv-test", tenant_id="t-test", client_id=None, status="open", created_at=NOW)
    session.add_all([m, tk, cv])
    session.flush()
    cm = ChatMessage(id="cm-test", conversation_id="cv-test", role="client", text="hey", ts=NOW)
    session.add(cm)
    session.commit()
    assert message_out(m)["ts"].endswith("+02:00")
    assert ticket_out(tk)["priority"] == "high"
    assert conversation_out(cv)["client_id"] is None
    assert chat_message_out(cm)["role"] == "client"


def test_policy_validation():
    with pytest.raises(ValidationError):
        Policy(**{**POLICY, "agent_permissions": {**POLICY["agent_permissions"], "refund": "bogus"}})
