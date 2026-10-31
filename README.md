# PolytechHack

Хакатон PolyTech Code Fest (трек "AI Customer Support Automation"). Моноріпо з кількох частин.

## Структура
- `support-agent/` — AI support-агент (FastAPI + Gemma 4). Опис і запуск: [support-agent/README.md](support-agent/README.md).
- `app/` — платформа бронювань тіммейта (ще не додана). Дизайн: [docs/superpowers/specs/2026-10-31-booking-app-design.md](docs/superpowers/specs/2026-10-31-booking-app-design.md).
- `docs/` — спеки, план, `WORKLOG.md`, feature docs.

## Швидкий старт агента
```bash
cd support-agent && uv sync && uv run uvicorn agent.main:app --port 8000
```
Тести: `cd support-agent && uv run pytest -q`.
