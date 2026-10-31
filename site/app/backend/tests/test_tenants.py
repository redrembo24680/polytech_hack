def test_list_has_seeded(client):
    ids = {t["id"] for t in client.get("/api/tenants").json()}
    assert {"lumen", "dentaplus"} <= ids


def test_get_tenant_policy(client):
    r = client.get("/api/tenants/lumen")
    assert r.status_code == 200
    p = r.json()["policy"]
    assert p["agent_permissions"]["refund"] == "auto_under_limit"
    assert p["agent_permissions"]["refund_auto_limit"] == 500


def test_get_unknown_404(client):
    r = client.get("/api/tenants/nope")
    assert r.status_code == 404 and r.json()["error"] == "not_found"


def test_put_policy_invalid_422(client):
    p = client.get("/api/tenants/lumen").json()["policy"]
    p["agent_permissions"]["refund"] = "maybe"
    r = client.put("/api/tenants/lumen/policy", json=p)
    assert r.status_code == 422 and r.json()["error"] == "validation"


def test_put_policy_valid(client):
    p = client.get("/api/tenants/lumen").json()["policy"]
    p["no_show_fee"] = 123
    p["agent_permissions"]["refund_auto_limit"] = 42
    r = client.put("/api/tenants/lumen/policy", json=p)
    assert r.status_code == 200
    got = client.get("/api/tenants/lumen").json()["policy"]
    assert got["no_show_fee"] == 123
    assert got["agent_permissions"]["refund_auto_limit"] == 42


def test_create_and_get(client):
    r = client.post("/api/tenants", json={"name": "Nova Studio", "kind": "salon"})
    assert r.status_code == 201
    t = r.json()
    assert t["id"] == "nova-studio"
    assert t["policy"] == client.get("/api/tenants/lumen").json()["policy"]
    assert client.get("/api/tenants/nova-studio").status_code == 200
    r2 = client.post("/api/tenants", json={"name": "Nova Studio", "kind": "salon"})
    assert r2.status_code == 201 and r2.json()["id"].startswith("t-")


def test_create_non_ascii_name_gets_generated_id(client):
    r = client.post("/api/tenants", json={"name": "Салон", "kind": "salon"})
    assert r.status_code == 201 and r.json()["id"].startswith("t-")


def test_create_bad_kind_422(client):
    r = client.post("/api/tenants", json={"name": "X", "kind": "bank"})
    assert r.status_code == 422


def test_patch(client):
    r = client.patch("/api/tenants/lumen", json={"address": "New 1", "bogus": 1})
    assert r.status_code == 200 and r.json()["address"] == "New 1"
    assert r.json()["name"] == client.get("/api/tenants/lumen").json()["name"]


def test_delete(client):
    assert client.delete("/api/tenants/dentaplus").status_code == 204
    r = client.get("/api/tenants/dentaplus")
    assert r.status_code == 404 and r.json()["error"] == "not_found"
    assert client.get("/api/tenants/lumen").status_code == 200
