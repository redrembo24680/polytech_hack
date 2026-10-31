# PolytechHack — Bookly

Хакатон PolyTech Code Fest (трек "AI Customer Support Automation"): AI-підтримка для бізнесів за записом (салони, клініки), яка не лише відповідає, а виконує дії за правилами бізнесу.

## Структура
- `site/` — платформа бронювань Bookly: FastAPI + PostgreSQL, MCP-сервер, сайт на Next.js (сторінка бізнесу, запис, чат підтримки, адмінка, віджет), запис демо-відео. Запуск і підключення агента: [site/README.md](site/README.md).
- `support-agent/` — AI-агент підтримки (оркестратор Claude Sonnet, Gemma 4, permission engine, copilot, телефонія Vapi). Запуск: [support-agent/README.md](support-agent/README.md).
- `presentation/` — презентація для журі (10 слайдів), відео під слайди і спіч на 5 хв.
- `docs/` — спеки й план агента, `WORKLOG.md`, feature docs агента, демо-відео.

## Швидкий старт
```bash
cd site && docker compose up -d --build            # платформа: сайт :3000, API :8001, MCP :8002
cd support-agent && uv sync && \
  APP_API_URL=http://localhost:8001 uv run uvicorn agent.main:app --host 0.0.0.0 --port 8000
```
Щоб чат сайту йшов в агента: у `site/.env` задати `AGENT_URL=http://host.docker.internal:8000` і `docker compose up -d backend`.
