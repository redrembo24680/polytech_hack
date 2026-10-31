from datetime import timedelta

import pytest

from agent.datasource import DataError
from tests.conftest import NOW


def test_get_tenant_policy(ds):
    t = ds.get_tenant("lumen")
    assert t.policy.agent_permissions.refund == "auto_under_limit"
    assert t.policy.agent_permissions.refund_auto_limit == 500
    assert "24 годин" in t.policy.rules_text


def test_get_client_with_bookings(ds):
    c = ds.get_client("lumen", "olena")
    assert (c.visits_count, c.no_show_count) == (12, 0)
    assert ds.list_client_bookings("lumen", "olena")[0].id == "b-olena-1"


def test_booking_start_is_tomorrow_10(ds):
    b = ds.get_booking("lumen", "b-olena-1")
    assert b.start == NOW.replace(hour=10, minute=0) + timedelta(days=1)
    assert b.prepayment.amount == 500 and b.prepayment.status == "held"


def test_unknown_booking_raises_not_found(ds):
    with pytest.raises(DataError) as e:
        ds.get_booking("lumen", "nope")
    assert e.value.code == "not_found"


def test_find_slots_excludes_taken(ds):
    slots = ds.find_slots("lumen", "svc-cut", NOW + timedelta(days=1), NOW + timedelta(days=2), staff_id="st-maria")
    starts = [s.start for s in slots]
    assert NOW.replace(hour=10, minute=0) + timedelta(days=1) not in starts  # зайнято Оленою
    assert NOW.replace(hour=11, minute=0) + timedelta(days=1) in starts
    assert len(slots) >= 3


def test_reschedule_moves_and_keeps_prepayment(ds):
    new = NOW.replace(hour=14, minute=0) + timedelta(days=2)
    b = ds.reschedule("lumen", "b-olena-1", new, "st-maria", "хвороба", "agent", forfeit_prepayment=False)
    assert b.start == new and b.prepayment.status == "held" and b.history[-1].event == "rescheduled"


def test_reschedule_to_taken_slot_raises(ds):
    taken = ds.get_booking("lumen", "b-max-1").start
    with pytest.raises(DataError) as e:
        ds.reschedule("lumen", "b-olena-1", taken, "st-olha", "x", "agent", False)
    assert e.value.code == "slot_taken"


def test_reschedule_cancelled_is_invalid_state(ds):
    ds.cancel("lumen", "b-olena-1", "x", "agent", forfeit_prepayment=False)
    with pytest.raises(DataError) as e:
        ds.reschedule("lumen", "b-olena-1", NOW + timedelta(days=3), None, "x", "agent", False)
    assert e.value.code == "invalid_state"


def test_cancel_forfeits(ds):
    b = ds.cancel("lumen", "b-max-1", "late", "agent", forfeit_prepayment=True)
    assert b.status == "cancelled" and b.prepayment.status == "forfeited"


def test_refund_over_amount_is_validation(ds):
    with pytest.raises(DataError) as e:
        ds.refund("lumen", "b-olena-1", 900, "x", "agent")
    assert e.value.code == "validation"


def test_refund_marks_refunded(ds):
    assert ds.refund("lumen", "b-olena-1", 500, "x", "agent").prepayment.status == "refunded"


def test_refund_twice_is_invalid_state(ds):
    ds.refund("lumen", "b-olena-1", 500, "x", "agent")
    with pytest.raises(DataError) as e:
        ds.refund("lumen", "b-olena-1", 1, "x", "agent")
    assert e.value.code == "invalid_state"


def test_waive_no_show_only_for_no_show(ds):
    assert ds.waive_no_show("denta", "b-anna-1", "x", "human:Оля").history[-1].event == "no_show_fee_waived"
    with pytest.raises(DataError):
        ds.waive_no_show("lumen", "b-olena-1", "x", "agent")


def test_goodwill_message_ticket(ds):
    c = ds.add_goodwill("lumen", "olena", "b-olena-1", "хвороба дитини", "agent")
    assert c.goodwill_exceptions[-1].booking_id == "b-olena-1"
    assert ds.send_message("lumen", "olena", "chat", "привіт").text == "привіт"
    assert ds.create_ticket("lumen", "olena", "складний кейс", "high").status == "open"


def test_ira_has_used_exception_30_days_ago(ds):
    ex = ds.get_client("lumen", "ira").goodwill_exceptions
    assert len(ex) == 1 and (NOW - ex[0].date).days == 30
