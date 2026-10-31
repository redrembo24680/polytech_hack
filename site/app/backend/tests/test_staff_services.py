SCHED = [{"weekday": 0, "start": "09:00", "end": "17:00"}, {"weekday": 2, "start": "10:00", "end": "14:30"}]


def test_create_staff_with_services_and_schedule(client):
    r = client.post("/api/tenants/lumen/staff",
                    json={"name": "Нова", "service_ids": ["lumen-brows", "lumen-manicure"]})
    assert r.status_code == 201
    s = r.json()
    assert sorted(s["service_ids"]) == ["lumen-brows", "lumen-manicure"]
    assert s["schedule"] == []
    r = client.put(f"/api/tenants/lumen/staff/{s['id']}/schedule", json=SCHED)
    assert r.status_code == 200
    got = client.get(f"/api/tenants/lumen/staff/{s['id']}").json()
    assert got["schedule"] == SCHED
    assert any(x["id"] == s["id"] for x in client.get("/api/tenants/lumen/staff").json())


def test_staff_unknown_service_422(client):
    r = client.post("/api/tenants/lumen/staff", json={"name": "X", "service_ids": ["denta-consult"]})
    assert r.status_code == 422 and r.json()["error"] == "validation"


def test_schedule_start_after_end_422(client):
    r = client.put("/api/tenants/lumen/staff/maria/schedule",
                   json=[{"weekday": 1, "start": "18:00", "end": "10:00"}])
    assert r.status_code == 422 and r.json()["error"] == "validation"
    r = client.put("/api/tenants/lumen/staff/maria/schedule",
                   json=[{"weekday": 9, "start": "10:00", "end": "11:00"}])
    assert r.status_code == 422


def test_patch_staff(client):
    r = client.patch("/api/tenants/lumen/staff/sofia", json={"name": "Софія П", "service_ids": ["lumen-brows"]})
    assert r.status_code == 200
    assert r.json()["name"] == "Софія П" and r.json()["service_ids"] == ["lumen-brows"]


def test_delete_staff_with_future_booking_409(client):
    r = client.delete("/api/tenants/lumen/staff/maria")
    assert r.status_code == 409 and r.json()["error"] == "invalid_state"


def test_delete_new_staff_204(client):
    sid = client.post("/api/tenants/lumen/staff", json={"name": "Тимч"}).json()["id"]
    r = client.delete(f"/api/tenants/lumen/staff/{sid}")
    assert r.status_code == 204 and r.content == b""
    assert client.get(f"/api/tenants/lumen/staff/{sid}").status_code == 404


def test_staff_other_tenant_404(client):
    r = client.get("/api/tenants/dentaplus/staff/maria")
    assert r.status_code == 404 and r.json()["error"] == "not_found"


def test_service_crud(client):
    r = client.post("/api/tenants/lumen/services", json={"name": "Масаж", "duration_min": 30, "price": 0})
    assert r.status_code == 201
    sid = r.json()["id"]
    r = client.patch(f"/api/tenants/lumen/services/{sid}", json={"price": 250})
    assert r.status_code == 200 and r.json()["price"] == 250 and r.json()["duration_min"] == 30
    assert client.get(f"/api/tenants/lumen/services/{sid}").status_code == 200
    assert any(x["id"] == sid for x in client.get("/api/tenants/lumen/services").json())
    assert client.delete(f"/api/tenants/lumen/services/{sid}").status_code == 204
    assert client.get(f"/api/tenants/lumen/services/{sid}").status_code == 404


def test_service_validation(client):
    r = client.post("/api/tenants/lumen/services", json={"name": "X", "duration_min": 0, "price": 10})
    assert r.status_code == 422 and r.json()["error"] == "validation"
    r = client.post("/api/tenants/lumen/services", json={"name": "X", "duration_min": 10, "price": -1})
    assert r.status_code == 422
    r = client.patch("/api/tenants/lumen/services/lumen-brows", json={"duration_min": -5})
    assert r.status_code == 422


def test_delete_service_with_future_booking_409(client, session):
    from booking.models import Booking
    sv = session.get(Booking, "b-olena-1").service_id
    r = client.delete(f"/api/tenants/lumen/services/{sv}")
    assert r.status_code == 409 and r.json()["error"] == "invalid_state"


def test_service_other_tenant_404(client):
    assert client.get("/api/tenants/dentaplus/services/lumen-brows").status_code == 404
