# Точки інтеграції

- **Вхід:** MCP-клієнти (AI-агент підтримки) через streamable HTTP `http://localhost:8002/mcp` або stdio.
- **Вихід:** HTTP до `booking-api` за `APP_API_URL` (`http://backend:8001` у Docker, `http://localhost:8001` локально).
- **Docker Compose:** сервіс `mcp` залежить від `backend`; порт 8002.
- **Контракт `by`:** дії за замовчуванням шлють `by="agent"`, тож у `history` бронювання видно, що дію зробив агент.
- **Версія:** FastMCP 4.1.4; транспорт `"http"` (= streamable-http), `"stdio"`.
