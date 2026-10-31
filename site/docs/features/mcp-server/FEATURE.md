# mcp-server

MCP-сервер (Python, FastMCP 4.1.4) у `app/mcp/booking_mcp/`. Обгортає HTTP API бронювань (`booking-api`) у 12 інструментів для AI-агента підтримки.

Транспорти: streamable HTTP (контейнер `mcp`, `http://localhost:8002/mcp`) і stdio (локальний запуск).
Конфігурація: `APP_API_URL` (у Docker `http://backend:8001`), `MCP_TRANSPORT=http|stdio` (за замовчуванням `http`), `MCP_PORT` (8002).

## Як підключитися тіммейту

**HTTP (стек уже піднятий: `cd site && docker compose up -d`)**

- URL: `http://localhost:8002/mcp`
- Claude Code: `claude mcp add --transport http booking http://localhost:8002/mcp`
- Claude Desktop / будь-який клієнт з `mcpServers` (через `mcp-remote`):

```json
{
  "mcpServers": {
    "booking": { "command": "npx", "args": ["-y", "mcp-remote", "http://localhost:8002/mcp"] }
  }
}
```

- Python (FastMCP): `async with fastmcp.Client("http://localhost:8002/mcp") as c: await c.call_tool("get_tenant", {"tenant_id": "lumen"})`

**stdio (без контейнера mcp; бекенд має працювати на :8001)**

```
cd site/app/mcp && APP_API_URL=http://localhost:8001 MCP_TRANSPORT=stdio uv run python -m booking_mcp
```

Конфіг для Claude Desktop / Claude Code (`.mcp.json`):

```json
{
  "mcpServers": {
    "booking": {
      "command": "uv",
      "args": ["run", "--directory", "/ABS/PATH/site/app/mcp", "python", "-m", "booking_mcp"],
      "env": { "APP_API_URL": "http://localhost:8001", "MCP_TRANSPORT": "stdio" }
    }
  }
}
```

## Інструменти

Усі приймають `tenant_id` (`lumen`, `dentaplus`). Дії приймають `by` (за замовчуванням `agent`).
Час — ISO 8601 з офсетом (`2026-11-03T10:00:00+02:00`).

| Інструмент | Параметри | Ендпоінт API |
|---|---|---|
| `get_tenant` | tenant_id | GET /tenants/{t} |
| `find_client_by_phone` | tenant_id, phone | GET /tenants/{t}/clients?phone= |
| `get_client` | tenant_id, client_id | GET /tenants/{t}/clients/{c} |
| `get_booking` | tenant_id, booking_id | GET /tenants/{t}/bookings/{b} |
| `find_slots` | tenant_id, service_id, date_from, date_to, staff_id? | GET /tenants/{t}/slots?service_id&from&to |
| `reschedule_booking` | tenant_id, booking_id, start, reason, forfeit_prepayment, staff_id?, by | POST .../reschedule |
| `cancel_booking` | tenant_id, booking_id, reason, forfeit_prepayment, by | POST .../cancel |
| `refund_booking` | tenant_id, booking_id, amount (грн), reason, by | POST .../refund |
| `waive_no_show` | tenant_id, booking_id, reason, by | POST .../waive-no-show |
| `add_goodwill` | tenant_id, client_id, booking_id, reason, by | POST /clients/{c}/goodwill |
| `send_message` | tenant_id, client_id, text, channel=chat | POST /tenants/{t}/messages |
| `create_ticket` | tenant_id, client_id, summary, priority=normal | POST /tenants/{t}/tickets |

Успіх повертає JSON відповіді API. Помилка API повертається текстом `"{error}: {message}"` (напр. `slot_taken: slot is not available`), мережева — `api_unavailable: ...`. Інструмент не кидає виняток.
