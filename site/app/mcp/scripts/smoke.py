"""Live smoke test: reschedule b-olena-1 through the running MCP server (http://localhost:8002/mcp)."""
import asyncio
import json
from datetime import datetime, timedelta, timezone

from fastmcp import Client

URL = "http://localhost:8002/mcp"
T = "lumen"


def unwrap(res):
    text = res.content[0].text
    try:
        return json.loads(text)
    except ValueError:
        return text


async def main() -> None:
    async with Client(URL) as c:
        booking = unwrap(await c.call_tool("get_booking", {"tenant_id": T, "booking_id": "b-olena-1"}))
        print("before:", booking["start"], booking["status"])
        kyiv = timezone(timedelta(hours=2))
        tomorrow = (datetime.now(kyiv) + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        slots = unwrap(await c.call_tool("find_slots", {
            "tenant_id": T, "service_id": booking["service_id"],
            "date_from": tomorrow.isoformat(), "date_to": (tomorrow + timedelta(days=7)).isoformat()}))
        assert isinstance(slots, list) and slots, f"no slots: {slots}"
        # first slot whose start differs from the current one (so the change is visible)
        first = next((s for s in slots if s["start"] != booking["start"]), slots[0])
        print("first slot:", first)
        res = unwrap(await c.call_tool("reschedule_booking", {
            "tenant_id": T, "booking_id": "b-olena-1", "start": first["start"],
            "staff_id": first["staff_id"], "reason": "smoke", "forfeit_prepayment": False}))
        assert isinstance(res, dict), res
        after = unwrap(await c.call_tool("get_booking", {"tenant_id": T, "booking_id": "b-olena-1"}))
        agent_events = [e for e in after["history"] if e["by"] == "agent"]
        print("after start:", after["start"])
        print("last agent event:", agent_events[-1])
        assert after["start"] == first["start"] and agent_events


asyncio.run(main())
