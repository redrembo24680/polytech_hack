# Структура бекенду

- `booking/routers/support.py` — ендпоінти розмов (див. `entry-points.json`).
- `booking/services/chat.py` — `add_message` (строго зростаючий `ts`), `history`, `forward_to_agent` (виклик `POST {AGENT_URL}/chat`, таймаут `AGENT_TIMEOUT`, за замовчуванням 60 с).
- `booking/config.py` — `agent_url` з `AGENT_URL` та `agent_timeout` з `AGENT_TIMEOUT`, читаються під час виклику.
- `scripts/echo_agent.py` — тестовий агент-ехо (FastAPI, порт 9000), поза compose.
