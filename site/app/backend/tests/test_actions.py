B = "/api/tenants/lumen/bookings"
NEW_START = "2026-11-04T14:00:00+02:00"  # free for Maria (see test_bookings)


def act(client, bid, action, tenant="lumen", **body):
    return client.post(f"/api/tenants/{tenant}/bookings/{bid}/{action}", json=body)


def test_reschedule(client):
    r = act(client, "b-olena-1", "reschedule", start=NEW_START, reason="client asked",
            by="agent", forfeit_prepayment=False)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["start"] == NEW_START and j["end"] == "2026-11-04T15:00:00+02:00"
    assert j["prepayment"]["status"] == "held" and j["staff_id"] == "maria"
    ev = j["history"][-1]
    assert ev["event"] == "rescheduled" and ev["by"] == "agent"
    assert "client asked" in ev["note"] and "2026-11-03T10:00:00+02:00" in ev["note"] and "→" in ev["note"]
    assert "client" in j and "staff" in j


def test_reschedule_forfeit(client):
    r = act(client, "b-olena-1", "reschedule", start=NEW_START, reason="late", by="agent",
            forfeit_prepayment=True)
    assert r.json()["prepayment"] == {"amount": 500, "status": "forfeited"}


def test_reschedule_other_staff_must_provide_service(client):
    r = act(client, "b-olena-1", "reschedule", start=NEW_START, staff_id="katya",
            reason="x", by="agent", forfeit_prepayment=False)
    assert r.status_code == 422 and r.json()["error"] == "validation"


def test_reschedule_naive_422_and_slot_taken(client):
    r = act(client, "b-olena-1", "reschedule", start="2026-11-04T14:00:00", reason="x",
            by="agent", forfeit_prepayment=False)
    assert r.status_code == 422
    r = act(client, "b-olena-1", "reschedule", start="2026-11-05T15:00:00+02:00", reason="x",
            by="agent", forfeit_prepayment=False)  # Ira's slot, Maria
    assert r.status_code == 409 and r.json()["error"] == "slot_taken"


def test_cancel_and_state_guards(client):
    r = act(client, "b-olena-1", "cancel", reason="ill", by="agent", forfeit_prepayment=False)
    assert r.status_code == 200
    j = r.json()
    assert j["status"] == "cancelled" and j["prepayment"]["status"] == "held"
    assert j["history"][-1]["event"] == "cancelled" and "ill" in j["history"][-1]["note"]
    r = act(client, "b-olena-1", "reschedule", start=NEW_START, reason="x", by="agent",
            forfeit_prepayment=False)
    assert r.status_code == 409 and r.json()["error"] == "invalid_state"
    r = act(client, "b-olena-1", "cancel", reason="x", by="agent", forfeit_prepayment=False)
    assert r.status_code == 409


def test_cancel_forfeit(client):
    r = act(client, "b-max-1", "cancel", reason="late", by="agent", forfeit_prepayment=True)
    assert r.json()["prepayment"]["status"] == "forfeited"


def test_refund(client):
    r = act(client, "b-olena-1", "refund", amount=300, reason="goodwill", by="agent")
    assert r.status_code == 200, r.text
    assert r.json()["prepayment"]["status"] == "refunded"
    assert r.json()["history"][-1]["event"] == "refunded"
    r = act(client, "b-olena-1", "refund", amount=100, reason="again", by="agent")
    assert r.status_code == 409 and r.json()["error"] == "invalid_state"


def test_refund_too_much_or_nonpositive(client):
    for amt in (600, 0, -5):
        r = act(client, "b-olena-1", "refund", amount=amt, reason="x", by="agent")
        assert r.status_code == 422 and r.json()["error"] == "validation", amt
    assert client.get(f"{B}/b-olena-1").json()["prepayment"]["status"] == "held"


def test_waive_no_show(client):
    r = act(client, "b-anna-1", "waive-no-show", tenant="dentaplus", reason="ok", by="human:ann")
    assert r.status_code == 200, r.text
    assert r.json()["no_show_fee"] == {"amount": 500, "status": "waived"}
    assert r.json()["history"][-1]["event"] == "no_show_waived"
    r = act(client, "b-anna-1", "waive-no-show", tenant="dentaplus", reason="again", by="agent")
    assert r.status_code == 409


def test_waive_scheduled_409(client):
    r = act(client, "b-olena-1", "waive-no-show", reason="x", by="agent")
    assert r.status_code == 409 and r.json()["error"] == "invalid_state"


def test_other_tenant_404(client):
    r = act(client, "b-olena-1", "cancel", tenant="dentaplus", reason="x", by="agent",
            forfeit_prepayment=False)
    assert r.status_code == 404 and r.json()["error"] == "not_found"


def test_goodwill(client):
    r = client.post("/api/tenants/lumen/clients/olena/goodwill",
                    json={"booking_id": "b-olena-1", "reason": "loyal", "by": "agent"})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["goodwill_exceptions"][-1]["booking_id"] == "b-olena-1"
    assert j["goodwill_exceptions"][-1]["reason"] == "loyal" and "bookings" not in j
    assert client.get(f"{B}/b-olena-1").json()["history"][-1]["event"] == "goodwill"


def test_goodwill_foreign_booking_404(client):
    r = client.post("/api/tenants/lumen/clients/olena/goodwill",
                    json={"booking_id": "b-max-1", "reason": "x", "by": "agent"})
    assert r.status_code == 404
    r = client.post("/api/tenants/lumen/clients/olena/goodwill",
                    json={"booking_id": "b-petro-1", "reason": "x", "by": "agent"})
    assert r.status_code == 404


def test_messages(client):
    r = client.post("/api/tenants/lumen/messages",
                    json={"client_id": "olena", "text": "Привіт"})
    assert r.status_code == 201, r.text
    assert r.json()["channel"] == "chat" and r.json()["client_id"] == "olena"
    client.post("/api/tenants/lumen/messages",
                json={"client_id": "max", "channel": "sms", "text": "hi"})
    lst = client.get("/api/tenants/lumen/messages", params={"client_id": "olena"}).json()
    assert [m["text"] for m in lst] == ["Привіт"]
    assert len(client.get("/api/tenants/lumen/messages").json()) == 2
    bad = client.post("/api/tenants/lumen/messages",
                      json={"client_id": "petro", "text": "x"})
    assert bad.status_code == 404
    assert client.post("/api/tenants/lumen/messages",
                       json={"client_id": "olena", "channel": "fax", "text": "x"}).status_code == 422


def test_tickets(client):
    r = client.post("/api/tenants/lumen/tickets", json={"client_id": "olena", "summary": "Скарга"})
    assert r.status_code == 201, r.text
    t = r.json()
    assert t["status"] == "open" and t["priority"] == "normal"
    assert client.post("/api/tenants/lumen/tickets",
                       json={"client_id": "petro", "summary": "x"}).status_code == 404
    assert [x["id"] for x in client.get("/api/tenants/lumen/tickets", params={"status": "open"}).json()] == [t["id"]]
    p = client.patch(f"/api/tenants/lumen/tickets/{t['id']}", json={"status": "closed"})
    assert p.status_code == 200 and p.json()["status"] == "closed"
    assert client.get("/api/tenants/lumen/tickets", params={"status": "open"}).json() == []
    assert client.patch(f"/api/tenants/dentaplus/tickets/{t['id']}",
                        json={"status": "closed"}).status_code == 404
