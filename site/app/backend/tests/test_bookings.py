from booking.models import Booking
from tests.conftest import TestSession

B = "/api/tenants/lumen/bookings"
NEW = {"name": "Нова", "phone": "+380 50 111 22 33"}


FREE = "2026-11-04T14:00:00+02:00"  # free for Maria in the seed (verified via /slots)


def body(**kw):
    d = {"client": NEW, "service_id": "lumen-styling", "staff_id": "maria", "start": FREE}
    d.update(kw)
    return d


def test_create_with_new_client(client):
    r = client.post(B, json=body())
    assert r.status_code == 201, r.text
    j = r.json()
    assert j["status"] == "scheduled" and j["staff_id"] == "maria"
    price = client.get("/api/tenants/lumen/services/lumen-styling").json()["price"]
    assert j["prepayment"] == {"amount": price, "status": "held"}
    assert j["history"][0]["event"] == "created" and j["history"][0]["by"] == "human:admin"
    assert j["start"] == FREE
    found = client.get("/api/tenants/lumen/clients", params={"phone": "0501112233"}).json()
    assert [c["id"] for c in found] == [j["client_id"]]
    # same phone again reuses the client
    r2 = client.post(B, json=body(start="2026-11-04T16:00:00+02:00", client={"name": "x", "phone": "050 111 22 33"}))
    assert r2.status_code == 201 and r2.json()["client_id"] == j["client_id"]


def test_existing_client_id(client):
    r = client.post(B, json={"client_id": "olena", "service_id": "lumen-styling",
                             "staff_id": "maria", "start": FREE, "by": "agent"})
    assert r.status_code == 201 and r.json()["client_id"] == "olena"
    assert r.json()["history"][0]["by"] == "agent"


def test_no_prepayment_policy(client):
    pol = client.get("/api/tenants/lumen").json()["policy"]
    assert client.put("/api/tenants/lumen/policy",
                      json={**pol, "prepayment_required": False}).status_code == 200
    r = client.post(B, json=body())
    assert r.json()["prepayment"] == {"amount": 0, "status": "none"}


def test_exact_overlap_409(client):
    r = client.post(B, json=body(start="2026-11-03T10:00:00+02:00"))
    assert r.status_code == 409 and r.json()["error"] == "slot_taken"


def test_partial_overlap_409(client):
    for start in ("2026-11-03T10:30:00+02:00", "2026-11-03T09:30:00+02:00"):
        r = client.post(B, json=body(start=start))
        assert r.status_code == 409 and r.json()["error"] == "slot_taken", start


def test_adjacent_ok(client):
    assert client.post(B, json=body(start="2026-11-03T11:00:00+02:00")).status_code == 201


def test_cancelled_booking_frees_slot(client):
    with TestSession() as s:
        s.get(Booking, "b-olena-1").status = "cancelled"
        s.commit()
    r = client.post(B, json=body(start="2026-11-03T10:00:00+02:00"))
    assert r.status_code == 201, r.text


def test_naive_start_422(client):
    r = client.post(B, json=body(start="2026-11-03T10:00:00"))
    assert r.status_code == 422 and r.json()["error"] == "validation"


def test_utc_offset_compared_correctly(client):
    r = client.post(B, json=body(start="2026-11-03T08:00:00Z"))
    assert r.status_code == 409 and r.json()["error"] == "slot_taken"
    assert client.post(B, json=body(start="2026-11-04T12:00:00Z")).status_code == 201  # 14:00 Kyiv


def test_past_and_outside_schedule_409(client):
    for start in ("2026-11-02T07:00:00+02:00", "2026-11-04T08:00:00+02:00", "2026-11-04T18:30:00+02:00"):
        r = client.post(B, json=body(start=start))
        assert r.status_code == 409 and r.json()["error"] == "slot_taken", start


def test_staff_without_service_422(client):
    r = client.post(B, json=body(service_id="lumen-manicure"))  # maria doesn't do manicure
    assert r.status_code == 422 and r.json()["error"] == "validation"


def test_unknown_refs_404(client):
    for kw in ({"service_id": "nope"}, {"staff_id": "nope"}, {"client": None, "client_id": "nope"},
               {"service_id": "denta-consult"}):
        assert client.post(B, json=body(**kw)).status_code == 404, kw


def test_client_xor_422(client):
    assert client.post(B, json=body(client=None)).status_code == 422
    assert client.post(B, json=body(client_id="olena")).status_code == 422


def test_patch_no_show(client):
    r = client.patch(f"{B}/b-olena-1", json={"status": "no_show"})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["status"] == "no_show"
    fee = client.get("/api/tenants/lumen").json()["policy"]["no_show_fee"]
    assert j["no_show_fee"] == {"amount": fee, "status": "charged"}
    assert j["history"][-1]["event"] == "no_show" and j["history"][-1]["by"] == "human:admin"
    assert client.patch(f"{B}/b-olena-1", json={"status": "completed"}).status_code == 409


def test_patch_completed_and_notes(client):
    r = client.patch(f"{B}/b-olena-1", json={"status": "completed", "notes": "ok", "by": "human:Ann"})
    j = r.json()
    assert j["status"] == "completed" and j["notes"] == "ok"
    assert j["history"][-1]["event"] == "completed" and j["history"][-1]["by"] == "human:Ann"


def test_patch_bad_status_422(client):
    assert client.patch(f"{B}/b-olena-1", json={"status": "cancelled"}).status_code == 422


def test_list_week(client):
    r = client.get(B, params={"from": "2026-11-02", "to": "2026-11-09"})
    assert r.status_code == 200
    item = next(b for b in r.json() if b["id"] == "b-olena-1")
    assert item["client_name"] .startswith("Олена") and item["staff_name"] == "Марія"
    assert item["service_name"] and "client" not in item
    starts = [b["start"] for b in r.json()]
    assert starts == sorted(starts)


def test_list_filters(client):
    r = client.get(B, params={"staff_id": "sofia", "status": "scheduled"}).json()
    assert r and all(b["staff_id"] == "sofia" and b["status"] == "scheduled" for b in r)
    assert client.get(B, params={"from": "2026-11-03T10:00:00"}).status_code == 422


def test_get_expand_and_tenant_scope(client):
    j = client.get(f"{B}/b-olena-1").json()
    assert j["client"]["id"] == "olena" and j["staff"]["id"] == "maria" and j["service"]["id"]
    assert client.get("/api/tenants/dentaplus/bookings/b-olena-1").status_code == 404


def test_delete(client):
    assert client.delete(f"{B}/b-olena-1").status_code == 204
    assert client.get(f"{B}/b-olena-1").status_code == 404
    assert client.delete(f"{B}/b-olena-1").status_code == 404
