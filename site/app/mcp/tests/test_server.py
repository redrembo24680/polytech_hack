import json

import httpx
from fastmcp import Client

from booking_mcp.server import build_server

TOOLS = {
    "get_tenant", "find_client_by_phone", "get_client", "get_booking", "find_slots",
    "reschedule_booking", "cancel_booking", "refund_booking", "waive_no_show",
    "add_goodwill", "send_message", "create_ticket",
}


def make(handler):
    calls = []

    def wrapped(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return handler(request)

    http = httpx.AsyncClient(transport=httpx.MockTransport(wrapped), base_url="http://api")
    return build_server("http://api", http=http), calls


def text_of(result) -> str:
    return result.content[0].text


async def test_lists_all_tools():
    server, _ = make(lambda r: httpx.Response(200, json={}))
    async with Client(server) as c:
        names = {t.name for t in await c.list_tools()}
    assert names == TOOLS
    async with Client(server) as c:
        for t in await c.list_tools():
            assert t.description and "permission" in t.description.lower()


async def test_find_slots_maps_query():
    slots = [{"staff_id": "maria", "start": "2026-11-02T10:00:00+02:00"}]
    server, calls = make(lambda r: httpx.Response(200, json=slots))
    async with Client(server) as c:
        res = await c.call_tool("find_slots", {
            "tenant_id": "lumen", "service_id": "lumen-styling",
            "date_from": "2026-11-02T00:00:00+02:00", "date_to": "2026-11-09T00:00:00+02:00"})
    req = calls[0]
    assert req.method == "GET" and req.url.path == "/api/tenants/lumen/slots"
    assert req.url.params["service_id"] == "lumen-styling"
    assert req.url.params["from"] == "2026-11-02T00:00:00+02:00"
    assert req.url.params["to"] == "2026-11-09T00:00:00+02:00"
    assert "staff_id" not in req.url.params
    assert json.loads(text_of(res)) == slots


async def test_reschedule_posts_by_agent():
    server, calls = make(lambda r: httpx.Response(200, json={"id": "b-olena-1"}))
    async with Client(server) as c:
        res = await c.call_tool("reschedule_booking", {
            "tenant_id": "lumen", "booking_id": "b-olena-1",
            "start": "2026-11-02T10:00:00+02:00", "reason": "client asked",
            "forfeit_prepayment": False})
    req = calls[0]
    assert req.method == "POST"
    assert req.url.path == "/api/tenants/lumen/bookings/b-olena-1/reschedule"
    body = json.loads(req.content)
    assert body["by"] == "agent" and body["reason"] == "client asked"
    assert body["forfeit_prepayment"] is False and "staff_id" not in body
    assert res.data == {"id": "b-olena-1"}


async def test_api_error_returned_as_text():
    server, _ = make(lambda r: httpx.Response(
        409, json={"error": "slot_taken", "message": "slot is not available"}))
    async with Client(server) as c:
        res = await c.call_tool("reschedule_booking", {
            "tenant_id": "lumen", "booking_id": "b-olena-1",
            "start": "2026-11-02T10:00:00+02:00", "reason": "x", "forfeit_prepayment": False})
    assert not res.is_error
    assert text_of(res).startswith("slot_taken:")


async def test_network_error_returned_as_text():
    def boom(request):
        raise httpx.ConnectError("refused")

    server, _ = make(boom)
    async with Client(server) as c:
        res = await c.call_tool("get_tenant", {"tenant_id": "lumen"})
    assert not res.is_error
    assert text_of(res).startswith("api_unavailable:")


async def test_other_endpoints():
    server, calls = make(lambda r: httpx.Response(200, json={"ok": True}))
    async with Client(server) as c:
        await c.call_tool("find_client_by_phone", {"tenant_id": "lumen", "phone": "0671234567"})
        await c.call_tool("cancel_booking", {"tenant_id": "lumen", "booking_id": "b1",
                                              "reason": "r", "forfeit_prepayment": True})
        await c.call_tool("refund_booking", {"tenant_id": "lumen", "booking_id": "b1",
                                              "amount": 300, "reason": "r"})
        await c.call_tool("waive_no_show", {"tenant_id": "lumen", "booking_id": "b1", "reason": "r"})
        await c.call_tool("add_goodwill", {"tenant_id": "lumen", "client_id": "olena",
                                            "booking_id": "b1", "reason": "r"})
        await c.call_tool("send_message", {"tenant_id": "lumen", "client_id": "olena", "text": "hi"})
        await c.call_tool("create_ticket", {"tenant_id": "lumen", "client_id": "olena", "summary": "s"})
    seen = [(r.method, r.url.path) for r in calls]
    assert seen == [
        ("GET", "/api/tenants/lumen/clients"),
        ("POST", "/api/tenants/lumen/bookings/b1/cancel"),
        ("POST", "/api/tenants/lumen/bookings/b1/refund"),
        ("POST", "/api/tenants/lumen/bookings/b1/waive-no-show"),
        ("POST", "/api/tenants/lumen/clients/olena/goodwill"),
        ("POST", "/api/tenants/lumen/messages"),
        ("POST", "/api/tenants/lumen/tickets"),
    ]
    assert calls[0].url.params["phone"] == "0671234567"
    assert json.loads(calls[2].content) == {"amount": 300, "reason": "r", "by": "agent"}
    assert json.loads(calls[5].content) == {"client_id": "olena", "channel": "chat", "text": "hi"}
    assert json.loads(calls[6].content)["priority"] == "normal"
