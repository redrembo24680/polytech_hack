def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json() == {"status": "ok"}


def test_unknown_route_error_shape(client):
    r = client.get("/api/tenants/nope")
    assert r.status_code == 404
    assert r.json()["error"] == "not_found"
