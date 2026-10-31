from datetime import datetime
from zoneinfo import ZoneInfo

from tests.conftest import NOW

URL = "/api/tenants/lumen/slots"
KYIV = ZoneInfo("Europe/Kyiv")


def slots(client, **p):
    p.setdefault("service_id", "lumen-styling")
    p.setdefault("from", "2026-11-03")
    p.setdefault("to", "2026-11-10")
    r = client.get(URL, params=p)
    assert r.status_code == 200, r.text
    return r.json()


def test_enough_slots_for_demo_service(client):
    # b-olena-1 is lumen-styling (Maria, 2026-11-03 10:00 in the frozen-clock world)
    assert len(slots(client, service_id="lumen-styling")) >= 3


def test_booked_slot_absent_and_sorted(client):
    s = slots(client)
    assert not [x for x in s if x["staff_id"] == "maria" and x["start"].startswith("2026-11-03T10:00")]
    keys = [(x["start"], x["staff_name"]) for x in s]
    assert keys == sorted(keys)
    assert all(x["start"].endswith("+02:00") for x in s)


def test_none_before_now(client):
    s = slots(client, **{"from": "2026-11-02", "to": "2026-11-03"})
    assert s
    assert all(datetime.fromisoformat(x["start"]) >= NOW for x in s)
    s2 = slots(client, **{"from": "2026-11-01", "to": "2026-11-02"})
    assert s2 == []


def test_long_service_not_at_1800(client):
    r = client.post("/api/tenants/lumen/services",
                    json={"name": "Long", "duration_min": 90, "price": 100})
    sid = r.json()["id"]
    from booking.models import StaffService
    from tests.conftest import TestSession
    with TestSession() as s:
        s.add(StaffService(staff_id="maria", service_id=sid)); s.commit()
    got = slots(client, service_id=sid, staff_id="maria")
    assert got
    for x in got:
        end = datetime.fromisoformat(x["end"])
        assert end.hour * 60 + end.minute <= 19 * 60
    assert not [x for x in got if x["start"][11:16] == "18:00"]


def test_staff_filter(client):
    s = slots(client, staff_id="maria")
    assert s and all(x["staff_id"] == "maria" for x in s)


def test_only_staff_providing_service(client):
    s = slots(client, service_id="lumen-manicure")
    assert s and {x["staff_id"] for x in s} == {"sofia", "katya"}


def test_day_without_schedule_has_no_slots(client):
    # 2026-11-08 is Sunday (weekday 6); drop Sunday for everyone providing styling
    for sid in ("maria", "sofia"):
        st = client.get(f"/api/tenants/lumen/staff/{sid}").json()
        sched = [d for d in st["schedule"] if d["weekday"] != 6]
        assert client.put(f"/api/tenants/lumen/staff/{sid}/schedule", json=sched).status_code == 200
    assert slots(client, **{"from": "2026-11-08", "to": "2026-11-09"}) == []


def test_unknown_service_404(client):
    r = client.get(URL, params={"service_id": "nope", "from": "2026-11-03", "to": "2026-11-10"})
    assert r.status_code == 404 and r.json()["error"] == "not_found"


def test_foreign_service_404(client):
    r = client.get(URL, params={"service_id": "denta-consult", "from": "2026-11-03", "to": "2026-11-10"})
    assert r.status_code == 404


def test_naive_datetime_422(client):
    r = client.get(URL, params={"service_id": "lumen-styling", "from": "2026-11-03T10:00:00",
                                "to": "2026-11-10"})
    assert r.status_code == 422 and r.json()["error"] == "validation"


def test_datetime_with_offset_accepted(client):
    s = slots(client, **{"from": "2026-11-03T08:00:00Z", "to": "2026-11-03T12:00:00+02:00"})
    assert s and all("2026-11-03T10:00" <= x["start"] < "2026-11-03T12:00" for x in s)
