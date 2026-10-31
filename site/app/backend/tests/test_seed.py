from collections import defaultdict
from datetime import timedelta

from datetime import datetime
from zoneinfo import ZoneInfo

from booking.models import Booking, Client, Service, Staff, StaffSchedule, StaffService, Tenant
from booking.phone import normalize_phone
from booking.schemas import booking_out, client_out
from booking.seed import reset
from tests.conftest import NOW


def test_seed_demo_core(session):
    o = client_out(session.get(Client, "olena"), session, with_bookings=True)
    assert (o["visits_count"], o["no_show_count"]) == (12, 0)
    b = next(b for b in o["bookings"] if b["id"] == "b-olena-1")
    assert b["start"] == "2026-11-03T10:00:00+02:00"
    assert b["prepayment"] == {"amount": 500, "status": "held"}
    assert b["staff_id"] == "maria"
    assert session.get(Service, b["service_id"]).name == "Стрижка + укладка"


def test_seed_demo_clients_counters(session):
    def counts(cid):
        o = client_out(session.get(Client, cid), session)
        return o["visits_count"], o["no_show_count"]
    assert counts("max") == (2, 2)
    assert counts("ira") == (5, 0)
    assert counts("petro") == (3, 0)
    assert counts("anna")[1] == 1


def test_seed_demo_bookings(session):
    exp = {"b-max-1": ("2026-11-03T11:00:00+02:00", 400), "b-ira-1": ("2026-11-05T15:00:00+02:00", 500),
           "b-petro-1": ("2026-11-03T09:00:00+02:00", 800)}
    for bid, (start, amt) in exp.items():
        b = booking_out(session.get(Booking, bid))
        assert b["start"] == start and b["status"] == "scheduled"
        assert b["prepayment"] == {"amount": amt, "status": "held"}
    assert session.get(Booking, "b-max-1").staff_id != "maria"


def test_seed_anna_no_show_fee(session):
    b = booking_out(session.get(Booking, "b-anna-1"), expand=False)
    assert b["status"] == "no_show" and b["no_show_fee"] == {"amount": 500, "status": "charged"}
    assert b["start"].startswith("2026-11-01")


def test_seed_ira_goodwill(session):
    ira = client_out(session.get(Client, "ira"), session, with_bookings=False)
    assert len(ira["goodwill_exceptions"]) == 1
    assert ira["goodwill_exceptions"][0]["date"].startswith("2026-10-03")


def test_seed_policies(session):
    l = session.get(Tenant, "lumen").policy
    d = session.get(Tenant, "dentaplus").policy
    assert (l["cancellation_window_hours"], l["no_show_fee"]) == (24, 300)
    assert l["agent_permissions"]["refund"] == "auto_under_limit"
    assert (d["cancellation_window_hours"], d["no_show_fee"]) == (48, 500)
    assert d["agent_permissions"]["waive_no_show_fee"] == "forbidden"


def test_seed_shape(session):
    for tid in ("lumen", "dentaplus"):
        staff = session.query(Staff).filter_by(tenant_id=tid).all()
        assert len(staff) == 3
        assert 4 <= session.query(Service).filter_by(tenant_id=tid).count() <= 6
        assert session.query(Client).filter_by(tenant_id=tid).count() >= 20
    assert session.get(Staff, "maria").tenant_id == "lumen"
    # every booking uses a service its staff provides
    pairs = {(r.staff_id, r.service_id) for r in session.query(StaffService)}
    for b in session.query(Booking):
        assert (b.staff_id, b.service_id) in pairs
    for c in session.query(Client):
        assert c.phone == normalize_phone(c.phone) and c.phone.startswith("380")


def test_seed_no_overlaps_and_low_occupancy(session):
    by_staff = defaultdict(list)
    for b in session.query(Booking).filter(Booking.status != "cancelled"):
        by_staff[b.staff_id].append(b)
    for bs in by_staff.values():
        bs.sort(key=lambda b: b.start)
        for a, b in zip(bs, bs[1:]):
            assert a.end <= b.start
    horizon = NOW + timedelta(days=7)
    for stid, bs in by_staff.items():
        mins = sum((b.end - b.start).total_seconds() / 60 for b in bs if NOW < b.start <= horizon)
        assert mins <= 0.5 * 7 * 9 * 60
    # Maria's 11:00 tomorrow is free
    assert not any(b.start == NOW.replace(day=3, hour=11) for b in by_staff["maria"])


def test_reset_endpoint_restores_state(client, session):
    session.get(Booking, "b-olena-1").status = "cancelled"
    session.commit()
    assert client.post("/api/admin/reset").json() == {"status": "ok"}
    session.expire_all()
    assert session.get(Booking, "b-olena-1").status == "scheduled"


def test_seed_is_deterministic(session):
    reset(session, NOW)
    ids1 = sorted(b.id for b in session.query(Booking))
    snap1 = sorted((b.id, b.start, b.staff_id, b.client_id) for b in session.query(Booking))
    reset(session, NOW)
    ids2 = sorted(b.id for b in session.query(Booking))
    snap2 = sorted((b.id, b.start, b.staff_id, b.client_id) for b in session.query(Booking))
    assert ids1 == ids2 and snap1 == snap2


def test_reset_on_weekend_clock(session):
    for now in (datetime(2026, 10, 31, 8, tzinfo=ZoneInfo("Europe/Kyiv")),
                datetime(2026, 11, 1, 8, tzinfo=ZoneInfo("Europe/Kyiv"))):
        reset(session, now)
        b = session.get(Booking, "b-olena-1")
        sched = {r.weekday: r for r in session.query(StaffSchedule).filter_by(staff_id="maria")}
        ks, ke = b.start.astimezone(ZoneInfo("Europe/Kyiv")), b.end.astimezone(ZoneInfo("Europe/Kyiv"))
        assert ks.hour == 10 and ks.date() == (now + timedelta(days=1)).date()
        row = sched[ks.weekday()]
        assert row.start_time <= ks.time() and ke.time() <= row.end_time
        assert len(sched) == 7
