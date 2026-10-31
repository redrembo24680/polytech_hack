"""MCP server exposing the booking platform HTTP API as tools for a support agent."""
from typing import Annotated, Any, Literal

import httpx
from fastmcp import FastMCP
from pydantic import Field

TIME_NOTE = "All datetimes must be ISO 8601 with a UTC offset (e.g. 2026-11-03T10:00:00+02:00); naive times are rejected."
POLICY_NOTE = (
    "The API only checks data integrity, NOT business policy or agent permissions: "
    "checking the tenant's policy and agent_permissions before calling is the agent's responsibility."
)

INSTRUCTIONS = (
    "Tools over the booking platform API. Always pass tenant_id (e.g. 'lumen', 'dentaplus'). "
    "Errors come back as text 'error_code: message' (slot_taken, invalid_state, not_found, validation, "
    "api_unavailable) instead of raising. " + POLICY_NOTE
)


def build_server(api_url: str, http: httpx.AsyncClient | None = None) -> FastMCP:
    base = api_url.rstrip("/")
    client = http if http is not None else httpx.AsyncClient(base_url=base, timeout=15.0)
    mcp = FastMCP("booking-support", instructions=INSTRUCTIONS)

    async def call(method: str, path: str, *, params: dict | None = None, json: dict | None = None) -> Any:
        try:
            resp = await client.request(method, base + path, params=params, json=json)
        except httpx.HTTPError as exc:
            return f"api_unavailable: {exc!r}"
        try:
            data = resp.json()
        except ValueError:
            data = None
        if resp.status_code >= 400:
            if isinstance(data, dict) and "error" in data:
                return f"{data['error']}: {data.get('message', '')}"
            if resp.status_code >= 500:
                return f"api_unavailable: HTTP {resp.status_code}"
            return f"http_{resp.status_code}: {resp.text[:200]}"
        return data

    @mcp.tool
    async def get_tenant(tenant_id: str) -> Any:
        """Load a business (tenant): name, timezone and its policy (cancellation window, no-show fee,
        prepayment, late-change fee, agent_permissions). Call this first in every conversation to learn
        the rules you must apply. Read-only. The API only checks data integrity, NOT business policy or agent permissions: checking the tenant's policy and agent_permissions before calling is the agent's responsibility.
        """
        return await call("GET", f"/api/tenants/{tenant_id}")

    @mcp.tool
    async def find_client_by_phone(tenant_id: str, phone: str) -> Any:
        """Find a client of the tenant by phone number; any format works (+380 67 123 45 67, 0671234567).
        Call it to identify who is writing. Returns a list (empty if nobody matches) with visits_count,
        no_show_count and goodwill_exceptions. Read-only. The API only checks data integrity, NOT business policy or agent permissions: checking the tenant's policy and agent_permissions before calling is the agent's responsibility.
        """
        return await call("GET", f"/api/tenants/{tenant_id}/clients", params={"phone": phone})

    @mcp.tool
    async def get_client(tenant_id: str, client_id: str) -> Any:
        """Get one client's card (contacts, visit and no-show counters, goodwill exceptions already granted,
        notes). Call before deciding on a goodwill exception or fee waiver. Read-only. The API only checks data integrity, NOT business policy or agent permissions: checking the tenant's policy and agent_permissions before calling is the agent's responsibility.
        """
        return await call("GET", f"/api/tenants/{tenant_id}/clients/{client_id}")

    @mcp.tool
    async def get_booking(tenant_id: str, booking_id: str) -> Any:
        """Get a booking with client, staff, service, prepayment and no-show fee state, and full history
        of events (who did what, when). Call to check status/time before any change and to verify the
        result after. Read-only. All datetimes must be ISO 8601 with a UTC offset (e.g. 2026-11-03T10:00:00+02:00); naive times are rejected.
        The API only checks data integrity, NOT business policy or agent permissions: checking the tenant's policy and agent_permissions before calling is the agent's responsibility.
        """
        return await call("GET", f"/api/tenants/{tenant_id}/bookings/{booking_id}")

    @mcp.tool
    async def find_slots(
        tenant_id: str,
        service_id: str,
        date_from: Annotated[str, Field(description="Window start, ISO 8601 with offset or YYYY-MM-DD")],
        date_to: Annotated[str, Field(description="Window end; limits slot START times, not their end")],
        staff_id: str | None = None,
    ) -> Any:
        """List free slots for a service in a time window (optionally for one staff member). Call it before
        rescheduling or when the client asks for available times. Returns [{staff_id, staff_name, start, end}].
        Read-only. All datetimes must be ISO 8601 with a UTC offset (e.g. 2026-11-03T10:00:00+02:00); naive times are rejected.
        The API only checks data integrity, NOT business policy or agent permissions: checking the tenant's policy and agent_permissions before calling is the agent's responsibility.
        """
        params = {"service_id": service_id, "from": date_from, "to": date_to}
        if staff_id:
            params["staff_id"] = staff_id
        return await call("GET", f"/api/tenants/{tenant_id}/slots", params=params)

    @mcp.tool
    async def reschedule_booking(
        tenant_id: str,
        booking_id: str,
        start: Annotated[str, Field(description="New start, ISO 8601 with offset")],
        reason: str,
        forfeit_prepayment: bool,
        staff_id: str | None = None,
        by: str = "agent",
    ) -> Any:
        """Move a scheduled booking to a new start (same service; optionally another staff member).
        Changes the booking time/staff, appends a history event and, if forfeit_prepayment is true,
        marks a held prepayment as forfeited (late-change fee). Fails with slot_taken if the slot is busy,
        invalid_state if the booking is not scheduled. Check with find_slots first. All datetimes must be ISO 8601 with a UTC offset (e.g. 2026-11-03T10:00:00+02:00); naive times are rejected.
        The API only checks data integrity, NOT business policy or agent permissions: checking the tenant's policy and agent_permissions before calling is the agent's responsibility.
        """
        body: dict[str, Any] = {"start": start, "reason": reason,
                                "forfeit_prepayment": forfeit_prepayment, "by": by}
        if staff_id:
            body["staff_id"] = staff_id
        return await call("POST", f"/api/tenants/{tenant_id}/bookings/{booking_id}/reschedule", json=body)

    @mcp.tool
    async def cancel_booking(
        tenant_id: str, booking_id: str, reason: str, forfeit_prepayment: bool, by: str = "agent",
    ) -> Any:
        """Cancel a scheduled booking. Sets status to cancelled (the slot becomes free), appends a history
        event and, if forfeit_prepayment is true, marks a held prepayment as forfeited; otherwise the
        prepayment stays held (use refund_booking to return it). invalid_state if not scheduled. The API only checks data integrity, NOT business policy or agent permissions: checking the tenant's policy and agent_permissions before calling is the agent's responsibility.
        """
        body = {"reason": reason, "forfeit_prepayment": forfeit_prepayment, "by": by}
        return await call("POST", f"/api/tenants/{tenant_id}/bookings/{booking_id}/cancel", json=body)

    @mcp.tool
    async def refund_booking(
        tenant_id: str, booking_id: str, amount: Annotated[int, Field(description="Whole UAH")],
        reason: str, by: str = "agent",
    ) -> Any:
        """Refund (part of) a held prepayment: moves its status to refunded and records the event.
        Amount is whole UAH and must not exceed the prepayment (422 validation otherwise); a second
        refund gives invalid_state. Call when policy entitles the client to money back. The API only checks data integrity, NOT business policy or agent permissions: checking the tenant's policy and agent_permissions before calling is the agent's responsibility.
        """
        body = {"amount": amount, "reason": reason, "by": by}
        return await call("POST", f"/api/tenants/{tenant_id}/bookings/{booking_id}/refund", json=body)

    @mcp.tool
    async def waive_no_show(tenant_id: str, booking_id: str, reason: str, by: str = "agent") -> Any:
        """Waive the no-show fee of a booking in status no_show: clears the fee and records the event.
        invalid_state if the booking is not a no-show. Call when the client has a valid excuse and policy
        allows waiving. The API only checks data integrity, NOT business policy or agent permissions: checking the tenant's policy and agent_permissions before calling is the agent's responsibility.
        """
        body = {"reason": reason, "by": by}
        return await call("POST", f"/api/tenants/{tenant_id}/bookings/{booking_id}/waive-no-show", json=body)

    @mcp.tool
    async def add_goodwill(
        tenant_id: str, client_id: str, booking_id: str, reason: str, by: str = "agent",
    ) -> Any:
        """Record a goodwill exception (a one-off courtesy) for a client, tied to a booking. Adds an entry to
        the client's goodwill_exceptions, which later counts against the tenant's goodwill limit. Call right
        after you grant an exception to a rule. The API only checks data integrity, NOT business policy or agent permissions: checking the tenant's policy and agent_permissions before calling is the agent's responsibility.
        """
        body = {"booking_id": booking_id, "reason": reason, "by": by}
        return await call("POST", f"/api/tenants/{tenant_id}/clients/{client_id}/goodwill", json=body)

    @mcp.tool
    async def send_message(
        tenant_id: str, client_id: str, text: str, channel: Literal["chat", "sms", "email"] = "chat",
    ) -> Any:
        """Send an outgoing message to the client (stored in the message log; default channel chat).
        Call to confirm an action you took or to notify the client. Does not change bookings. The API only checks data integrity, NOT business policy or agent permissions: checking the tenant's policy and agent_permissions before calling is the agent's responsibility.
        """
        body = {"client_id": client_id, "channel": channel, "text": text}
        return await call("POST", f"/api/tenants/{tenant_id}/messages", json=body)

    @mcp.tool
    async def create_ticket(
        tenant_id: str, client_id: str, summary: str,
        priority: Literal["low", "normal", "high"] = "normal",
    ) -> Any:
        """Escalate to a human: create a support ticket for the client with a short summary. Call when the
        request is outside your permissions or policy forbids it. Creates a new open ticket; changes no
        bookings. The API only checks data integrity, NOT business policy or agent permissions: checking the tenant's policy and agent_permissions before calling is the agent's responsibility.
        """
        body = {"client_id": client_id, "summary": summary, "priority": priority}
        return await call("POST", f"/api/tenants/{tenant_id}/tickets", json=body)

    return mcp
