"""Agent-spec section 8 acceptance scenario, run against the seeded data."""


def test_agent_acceptance(client):
    T = "/api/tenants/lumen"
    # 1. client with their booking
    r = client.get(f"{T}/clients/olena")
    assert r.status_code == 200
    assert "b-olena-1" in [b["id"] for b in r.json()["bookings"]]
    # 2. at least 3 slots
    slots = client.get(f"{T}/slots", params={"service_id": "lumen-styling",
                                             "from": "2026-11-03", "to": "2026-11-10"}).json()
    assert len(slots) >= 3
    first = slots[0]
    # 3. reschedule olena's booking onto the first slot
    r = client.post(f"{T}/bookings/b-olena-1/reschedule",
                    json={"start": first["start"], "staff_id": first["staff_id"],
                          "reason": "client request", "by": "agent", "forfeit_prepayment": False})
    assert r.status_code == 200, r.text
    assert r.json()["start"] == first["start"]
    # 4. Max onto the same slot (same staff) -> genuine conflict
    r = client.post(f"{T}/bookings/b-max-1/reschedule",
                    json={"start": first["start"], "staff_id": first["staff_id"],
                          "reason": "client request", "by": "agent", "forfeit_prepayment": False})
    assert r.status_code == 409 and r.json()["error"] == "slot_taken"
