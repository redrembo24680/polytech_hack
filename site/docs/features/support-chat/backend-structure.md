# Структура бекенду

- `booking/routers/support.py` — ендпоінти розмов (див. `entry-points.json`).
- `booking/services/chat.py` — `add_message` (строго зростаючий `ts`), `history`, `forward_to_agent` (виклик `POST {AGENT_URL}/chat`, таймаут 60 с).
- `booking/config.py` — `agent_url` з `AGENT_URL`, читається під час виклику.
- `scripts/echo_agent.py` — тестовий агент-ехо (FastAPI, порт 9000), поза compose.
