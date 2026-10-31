import json
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx
import pytest

from agent.datasource import DataError, HttpDataSource, make_datasource, MemoryDataSource
from tests.conftest import NOW

KYIV = ZoneInfo("Europe/Kyiv")
POLICY = {"cancellation_window_hours": 24, "late_change_forfeits_prepayment": True, "no_show_fee": 300,
          "prepayment_required": True,
          "agent_permissions": {"reschedule": "auto", "cancel": "auto", "refund": "auto_under_limit",
                                "refund_auto_limit": 500, "goodwill_exception": "auto",
                                "goodwill_per_client_per_180d": 1, "goodwill_requires_zero_no_shows": True,
                                "waive_no_show_fee": "approval"}}
TENANT = {"id": "lumen", "name": "Lumen", "kind": "salon", "timezone": "Europe/Kyiv", "description": "d",
          "address": "a", "phone": "p", "instagram": "i", "policy": POLICY}
BOOKING = {"id": "b1", "tenant_id": "lumen", "client_id": "olena", "staff_id": "maria", "service_id": "s",
           "start": "2026-11-01T10:00:00+02:00", "end": "2026-11-01T11:00:00+02:00", "status": "scheduled",
           "prepayment": {"amount": 200, "status": "held"}, "no_show_fee": {"amount": 0, "status": "none"},
           "history": [{"ts": "2026-10-31T10:00:00+02:00", "event": "rescheduled", "by": "agent", "note": "n"}],
           "notes": ""}
CLIENT = {"id": "olena", "tenant_id": "lumen", "name": "Олена", "phone": "380671234501", "visits_count": 3,
          "no_show_count": 0, "notes": "", "goodwill_exceptions": [
              {"date": "2026-09-01", "booking_id": "b0", "reason": "r"}], "bookings": [BOOKING]}


def ds_with(handler):
    seen = []

    def wrapped(req: httpx.Request):
        seen.append(req)
        return handler(req)

    return HttpDataSource("http://api", transport=httpx.MockTransport(wrapped)), seen


def ok(data, status=200):
    return lambda req: httpx.Response(status, json=data)


def test_get_tenant_maps_policy_and_rules_override():
    ds, seen = ds_with(ok(TENANT))
    t = ds.get_tenant("lumen")
    assert seen[0].url.path == "/api/tenants/lumen"
    assert t.policy.cancellation_window_hours == 24 and t.policy.agent_permissions.refund_auto_limit == 500
    assert "24 години" in t.policy.rules_text
    other, _ = ds_with(ok({**TENANT, "id": "zzz"}))
    assert other.get_tenant("zzz").policy.rules_text == ""
    withtext, _ = ds_with(ok({**TENANT, "policy": {**POLICY, "rules_text": "свій"}}))
    assert withtext.get_tenant("lumen").policy.rules_text == "свій"


def test_get_client_parses_goodwill_date():
    ds, _ = ds_with(ok(CLIENT))
    c = ds.get_client("lumen", "olena")
    assert c.goodwill_exceptions[0].date == datetime(2026, 9, 1, tzinfo=KYIV)
    assert c.goodwill_exceptions[0].date.utcoffset() is not None


def test_list_client_bookings_uses_client_bookings():
    ds, seen = ds_with(ok(CLIENT))
    bs = ds.list_client_bookings("lumen", "olena")
    assert seen[0].url.path == "/api/tenants/lumen/clients/olena" and [b.id for b in bs] == ["b1"]
    assert bs[0].history[0].event == "rescheduled"


def test_find_client_by_phone_and_get_booking():
    ds, seen = ds_with(ok([CLIENT]))
    assert ds.find_client_by_phone("lumen", "+380671234501")[0].id == "olena"
    assert seen[0].url.params["phone"] == "+380671234501"
    ds2, seen2 = ds_with(ok({**BOOKING, "client": CLIENT}))
    assert ds2.get_booking("lumen", "b1").prepayment.amount == 200
    assert seen2[0].url.path.endswith("/bookings/b1")


def test_find_slots_query_params():
    slot = {"staff_id": "maria", "staff_name": "Марія", "start": "2026-11-03T13:00:00+02:00",
            "end": "2026-11-03T14:00:00+02:00"}
    ds, seen = ds_with(ok([slot]))
    out = ds.find_slots("lumen", "lumen-styling", NOW, NOW.replace(day=5), "maria")
    p = seen[0].url.params
    assert p["service_id"] == "lumen-styling" and p["staff_id"] == "maria"
    assert p["from"] == NOW.isoformat() and "to" in p
    assert out[0].staff_name == "Марія"
    ds.find_slots("lumen", "x", NOW, NOW)
    assert "staff_id" not in seen[1].url.params


def test_reschedule_body_and_slot_taken():
    ds, seen = ds_with(ok(BOOKING))
    start = datetime(2026, 11, 3, 13, 0, tzinfo=KYIV)
    ds.reschedule("lumen", "b1", start, "sofia", "хвороба", "agent", True)
    req = seen[0]
    assert req.method == "POST" and req.url.path == "/api/tenants/lumen/bookings/b1/reschedule"
    assert json.loads(req.content) == {"start": start.isoformat(), "staff_id": "sofia", "reason": "хвороба",
                                       "by": "agent", "forfeit_prepayment": True}
    bad, _ = ds_with(ok({"error": "slot_taken", "message": "зайнято"}, 409))
    with pytest.raises(DataError) as e:
        bad.reschedule("lumen", "b1", start, None, "r", "agent", False)
    assert (e.value.code, e.value.message) == ("slot_taken", "зайнято")


def test_refund_validation_error():
    ds, _ = ds_with(ok({"error": "validation", "message": "сума"}, 422))
    with pytest.raises(DataError) as e:
        ds.refund("lumen", "b1", 9999, "r", "agent")
    assert e.value.code == "validation"


def test_other_actions_paths():
    ds, seen = ds_with(lambda req: httpx.Response(200, json=CLIENT if "goodwill" in req.url.path else BOOKING))
    ds.cancel("lumen", "b1", "r", "agent", False)
    ds.waive_no_show("lumen", "b1", "r", "agent")
    ds.add_goodwill("lumen", "olena", "b1", "r", "agent")
    assert [r.url.path.rsplit("/", 1)[-1] for r in seen] == ["cancel", "waive-no-show", "goodwill"]
    assert json.loads(seen[2].content) == {"booking_id": "b1", "reason": "r", "by": "agent"}


def test_connection_error_is_api_unavailable():
    def boom(req):
        raise httpx.ConnectError("refused")

    ds, _ = ds_with(boom)
    with pytest.raises(DataError) as e:
        ds.get_tenant("lumen")
    assert e.value.code == "api_unavailable" and e.value.message == "Платформа бронювань недоступна."


def test_list_tenants():
    ds, seen = ds_with(ok([TENANT, {**TENANT, "id": "dentaplus", "name": "Denta", "kind": "clinic"}]))
    assert [t.id for t in ds.list_tenants()] == ["lumen", "dentaplus"]
    assert seen[0].url.path == "/api/tenants"
    assert "48 годин" in ds.list_tenants()[1].policy.rules_text


def test_make_datasource(monkeypatch):
    monkeypatch.delenv("APP_API_URL", raising=False)
    assert isinstance(make_datasource(lambda: NOW), MemoryDataSource)
    monkeypatch.setenv("APP_API_URL", "http://x:1")
    assert isinstance(make_datasource(lambda: NOW), HttpDataSource)
