# AI-підтримка для бізнесів із записами (PolyTech Code Fest)

Платформа для салонів, клінік та інших бізнесів, що працюють за записом: клієнти пишуть у чат підтримки, а AI-агент
переносить/скасовує записи, повертає передоплату, прощає штрафи — за політикою бізнесу. **Наша частина** — продукт
(публічна сторінка, бронювання, чат, адмінка), HTTP API та MCP-сервер, через який агент працює з даними.
Сам агент підтримки будує тіммейт. Мультитенантність: у демо два бізнеси — Lumen Beauty (салон) і DentaPlus (клініка).

## Архітектура

```
browser ──► web :3000 (Next.js) ──► backend :8001 (FastAPI) ──► db :5433 (Postgres)
                                        ▲      │
                       mcp :8002 (FastMCP)     └──► AGENT_URL/chat  (вебхук до агента)
                                        ▲
                                     AI-агент (тіммейт)
```

Агент отримує повідомлення клієнта вебхуком `POST {AGENT_URL}/chat` і діє через MCP-інструменти (або напряму через API).

## Швидкий старт

```
cd site && docker compose up -d --build
```

Перший запуск займає кілька хвилин; демо-дані створюються автоматично. Перевірка: `curl localhost:8001/api/health` -> `{"status":"ok"}`.

| Що | URL |
|---|---|
| Лендінг | http://localhost:3000/ |
| Сторінка бізнесу | http://localhost:3000/b/lumen |
| Запис онлайн | http://localhost:3000/b/lumen/book |
| Чат підтримки | http://localhost:3000/b/lumen/support |
| Адмінка | http://localhost:3000/admin/lumen |
| Демо-сайт із віджетом | http://localhost:3000/demo-salon-site.html |
| API (Swagger) | http://localhost:8001/docs (префікс `/api`) |
| MCP (streamable HTTP) | http://localhost:8002/mcp |

Те саме для DentaPlus: `/b/dentaplus`, `/admin/dentaplus`.

## Демо-дані

Бізнеси: `lumen` (Lumen Beauty, салон), `dentaplus` (DentaPlus, клініка). Усі id — читабельні рядки.

| Клієнт | Тенант | Телефон | Що демонструє (за специфікацією агента) |
|---|---|---|---|
| `olena` | lumen | 380671234501 | Постійна клієнтка (12 візитів, без неявок) -> goodwill можна видати автоматично; запис `b-olena-1` завтра 10:00 |
| `max` | lumen | 380501234502 | 2 неявки -> goodwill не належить; `b-max-1` |
| `ira` | lumen | 380931234503 | Уже використала разовий goodwill (`gw-ira-1`) -> вдруге не можна; `b-ira-1` |
| `petro` | dentaplus | 380671234504 | Сувора політика клініки -> дії потребують погодження адміністратора; `b-petro-1` |
| `anna` | dentaplus | 380991234505 | Неявка зі штрафом (`b-anna-1`); у клініці прощення штрафу за неявку заборонене |

Політики бізнесів лежать у `tenant.policy` (`GET /api/tenants/{id}`). Додатково згенеровано по 20 фонових клієнтів на бізнес.

### Скинути демо

Кнопка «Скинути демо» в адмінці або `curl -XPOST localhost:8001/api/admin/reset` — повертає дані до початкового стану
(час записів рахується від «сьогодні»).

## Підключення агента

**MCP** (12 інструментів: пошук клієнта, слоти, перенесення, скасування, повернення, goodwill, повідомлення, тікети …)

- HTTP: `http://localhost:8002/mcp`; Claude Code: `claude mcp add --transport http booking http://localhost:8002/mcp`
- stdio: `cd site/app/mcp && APP_API_URL=http://localhost:8001 MCP_TRANSPORT=stdio uv run python -m booking_mcp`
- Python: `async with fastmcp.Client("http://localhost:8002/mcp") as c: await c.call_tool("get_tenant", {"tenant_id": "lumen"})`
- Повний список інструментів і конфіги для Claude Desktop: [docs/features/mcp-server](docs/features/mcp-server/FEATURE.md)

**Чат-вебхук.** Задайте `AGENT_URL` (файл `site/.env` або змінна середовища; напр. `AGENT_URL=http://host.docker.internal:9000`)
і перезапустіть: `docker compose up -d backend`. Бекенд викликає `POST {AGENT_URL}/chat` (таймаут 60 с):

```json
{
  "tenant_id": "lumen",
  "conversation_id": "conv-1a2b3c",
  "client_id": "olena",
  "messages": [
    {"role": "client", "text": "Хочу скасувати запис на завтра", "ts": "2026-10-31T14:32:53.854535+02:00"},
    {"role": "agent", "text": "Підкажіть, будь ласка, час запису", "ts": "2026-10-31T14:33:02.100000+02:00"},
    {"role": "client", "text": "О 15:00", "ts": "2026-10-31T14:33:20.000000+02:00"}
  ]
}
```

Відповідь: `{"reply": "Запис скасовано, передоплату повернуто."}`. `client_id` може бути `null` (невідомий телефон);
`messages` — вся історія, `role` ∈ `client|agent|human`. Порожній/відсутній `reply` — повідомлення не створюється
(агент може відповісти пізніше через `POST /api/tenants/{t}/support/conversations/{id}/reply`).
Без `AGENT_URL` клієнт бачить заглушку «Агент підтримки ще не підключений». Тестовий агент-ехо:
`cd site/app/backend && uv run uvicorn scripts.echo_agent:app --port 9000`.
Деталі: [docs/features/support-chat](docs/features/support-chat/integration-points.md).

## Тести

```
cd site/app/backend && uv run pytest -q      # потрібна БД на localhost:5433 (docker compose up -d db), БД booking_test
cd site/app/mcp && uv run pytest -q
cd site && docker compose exec web npx vitest run
cd site && docker compose exec web npx tsc --noEmit && docker compose exec web npm run lint
cd site/app/mcp && uv run python scripts/smoke.py   # живий прогін агента; після нього зробіть reset
```

## Порти та підводні камені

- Postgres на хості — **5433** (локальний Homebrew Postgres займає 5432); у контейнерах — 5432.
- Час — ISO 8601 **з офсетом** (`2026-11-03T10:00:00+02:00`); без офсету API відповідає 422 `validation`. Таймзона тенантів — `Europe/Kyiv`.
- Помилки API: `{"error": code, "message": text}` (`not_found` 404, `invalid_state` 409, `slot_taken` 409, `validation` 422); MCP повертає їх текстом `code: message`.
- Застосунок **не перевіряє** політику та `agent_permissions` — лише цілісність даних; рішення приймає агент.
- Телефони нормалізуються до цифр (`0671234567` = `+380 67 123 45 67`). Гроші — цілі гривні.
- Схема створюється на старті (`create_all`), сід — лише якщо БД порожня. Повний скид: `docker compose down -v`.
- Якщо web не бачить залежностей: `docker compose up -d --build -V`.

## Документація фіч

[booking-api](docs/features/booking-api/FEATURE.md) · [mcp-server](docs/features/mcp-server/FEATURE.md) ·
[support-chat](docs/features/support-chat/FEATURE.md) · [business-page](docs/features/business-page/FEATURE.md) ·
[admin-panel](docs/features/admin-panel/FEATURE.md) · [support-widget](docs/features/support-widget/FEATURE.md)
