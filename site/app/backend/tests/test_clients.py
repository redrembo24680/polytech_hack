def test_phone_lookup_formats(client):
    created = client.post("/api/tenants/lumen/clients",
                          json={"name": "Тест", "phone": "+380 67 123 45 67"})
    assert created.status_code == 201 and created.json()["phone"] == "380671234567"
    for fmt in ["0671234567", "+380 67 123-45-67", "380671234567", "(067) 123 45 67"]:
        r = client.get("/api/tenants/lumen/clients", params={"phone": fmt})
        assert r.status_code == 200
        assert [c["id"] for c in r.json()] == [created.json()["id"]], fmt


def test_phone_lookup_no_match_and_tenant_scope(client):
    assert client.get("/api/tenants/dentaplus/clients", params={"phone": "380671234501"}).json() == []


def test_duplicate_phone_409(client):
    client.post("/api/tenants/lumen/clients", json={"name": "A", "phone": "+380 67 123 45 67"})
    r = client.post("/api/tenants/lumen/clients", json={"name": "B", "phone": "0671234567"})
    assert r.status_code == 409 and r.json()["error"] == "invalid_state"
    # same phone in another tenant is fine
    assert client.post("/api/tenants/dentaplus/clients",
                       json={"name": "B", "phone": "0671234567"}).status_code == 201


def test_empty_phone_422(client):
    r = client.post("/api/tenants/lumen/clients", json={"name": "A", "phone": "abc"})
    assert r.status_code == 422 and r.json()["error"] == "validation"


def test_profile_has_bookings_newest_first(client):
    r = client.get("/api/tenants/lumen/clients/olena")
    assert r.status_code == 200
    bs = r.json()["bookings"]
    assert len(bs) >= 2
    starts = [b["start"] for b in bs]
    assert starts == sorted(starts, reverse=True)
    assert bs[0]["id"] == "b-olena-1" or bs[0]["start"] == max(starts)


def test_other_tenant_404(client):
    r = client.get("/api/tenants/dentaplus/clients/olena")
    assert r.status_code == 404 and r.json()["error"] == "not_found"


def test_search_q(client):
    r = client.get("/api/tenants/lumen/clients", params={"q": "оле"})
    assert "olena" in [c["id"] for c in r.json()]
    r = client.get("/api/tenants/lumen/clients", params={"q": "ОЛЕ"})
    assert "olena" in [c["id"] for c in r.json()]
    r = client.get("/api/tenants/lumen/clients", params={"q": "1234501"})
    assert [c["id"] for c in r.json()] == ["olena"]
    r = client.get("/api/tenants/lumen/clients", params={"q": "zzzz"})
    assert r.json() == []


def test_patch_client(client):
    r = client.patch("/api/tenants/lumen/clients/max", json={"notes": "VIP", "phone": "050 123 45 99"})
    assert r.status_code == 200 and r.json()["notes"] == "VIP" and r.json()["phone"] == "380501234599"
    r = client.patch("/api/tenants/lumen/clients/max", json={"phone": "380671234501"})
    assert r.status_code == 409
    r = client.patch("/api/tenants/lumen/clients/max", json={"phone": "--"})
    assert r.status_code == 422
    # patching own phone unchanged is fine
    assert client.patch("/api/tenants/lumen/clients/max", json={"phone": "380501234599"}).status_code == 200


def test_delete_client(client):
    r = client.post("/api/tenants/lumen/clients", json={"name": "Del", "phone": "0991112233"})
    cid = r.json()["id"]
    assert client.delete(f"/api/tenants/lumen/clients/{cid}").status_code == 204
    assert client.get(f"/api/tenants/lumen/clients/{cid}").status_code == 404


def test_delete_client_with_future_booking_409(client):
    r = client.delete("/api/tenants/lumen/clients/olena")
    assert r.status_code == 409 and r.json()["error"] == "invalid_state"
