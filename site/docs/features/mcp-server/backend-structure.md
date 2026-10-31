# Структура

```
app/mcp/
  pyproject.toml, uv.lock     окремий uv-проєкт (fastmcp, httpx; dev: pytest, pytest-asyncio)
  Dockerfile                  python:3.14-slim + uv, CMD python -m booking_mcp
  booking_mcp/
    server.py     build_server(api_url, http=None) -> FastMCP; 12 інструментів; хелпер call()
    __main__.py   MCP_TRANSPORT=http|stdio, host 0.0.0.0, port 8002, path /mcp
  tests/test_server.py        in-memory fastmcp.Client + httpx.MockTransport
  scripts/smoke.py            перевірка проти живого стеку
```

`build_server` створює один спільний `httpx.AsyncClient(base_url=api_url)`, якщо клієнта не передано (тести передають `MockTransport`). Параметри `date_from`/`date_to` у `find_slots` відображаються на query `from`/`to`. Docker-сервіс `mcp` у `docker-compose.yml`: порт 8002, `APP_API_URL=http://backend:8001`, `depends_on: backend`.
