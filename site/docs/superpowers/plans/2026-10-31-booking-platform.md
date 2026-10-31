# Booking Platform + MCP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Мульти-тенант платформа бронювань (API + адмінка з CRUD + сторінка бізнесу + чат підтримки) і MCP-сервер, через які агент тіммейта виконує дії підтримки; усе в Docker з мок-даними в Postgres.

**Architecture:** FastAPI-бекенд — єдине джерело правди над PostgreSQL. MCP-сервер (FastMCP) — тонкий HTTP-клієнт до цього API. Next.js-сайт ходить в API з браузера (SWR з опитуванням). Docker Compose піднімає `db`, `backend`, `mcp`, `web`.

**Tech Stack:** Python 3.14, uv, FastAPI, SQLAlchemy 2 + psycopg 3, pydantic 2, httpx, pytest; FastMCP; Next.js (App Router) + React + TypeScript + Tailwind + SWR; PostgreSQL 16; Docker Compose.

**Spec:** `site/docs/superpowers/specs/2026-10-31-booking-platform-design.md` (+ спека агента тіммейта, розділи 3–5 і 8 — контракт API і сід).

## Global Constraints

- **Уся наша частина живе в `site/` у корені репо.** Усі шляхи в цьому плані (`docker-compose.yml`, `app/…`, `docs/…`) — відносно `site/`; команди запускаються з `site/` (напр. `cd site && docker compose up`).
- Порти: db 5433 на хості (5432 в контейнері; локальний Homebrew Postgres займає 5432), backend 8001, mcp 8002, web 3000. MCP шлях: `/mcp`.
- Env: `DATABASE_URL`, `AGENT_URL` (опц.), `APP_API_URL` (MCP; у Docker `http://backend:8001`), `NEXT_PUBLIC_API_URL` (`http://localhost:8001`).
- Усі id — рядки. Сід: людські slug (`lumen`, `dentaplus`, `olena`, `b-olena-1` …); нові — `f"{prefix}-{secrets.token_hex(3)}"`.
- Час — ISO 8601 з офсетом; таймзона тенантів `Europe/Kyiv`. Datetime без офсету на вході → 422 `validation`.
- Гроші — цілі гривні.
- Помилки: `{"error": code, "message": text}`; коди і статуси: `not_found` 404, `invalid_state` 409, `slot_taken` 409, `validation` 422.
- Поле `by`: `"agent"` або `"human:<ім'я>"`; адмінка шле `"human:admin"`.
- Апка НЕ перевіряє `agent_permissions` — лише цілісність даних.
- Телефони нормалізуються до цифр (`+380 67 123-45-67` → `380671234567`; `0671234567` → `380671234567`) для збереження, пошуку й унікальності в тенанті.
- Форма запитів/відповідей ендпоінтів зі спеки агента не змінюється.
- Схема — `Base.metadata.create_all` на старті, без міграцій. Сід на старті лише якщо таблиця `tenants` порожня.
- Документація фічі: `docs/features/<фіча>/` × 10 файлів: FEATURE.md, business-context.md, end-to-end-flow.md, entry-points.json, per-app-responsibility.md, backend-structure.md, frontend-structure.md, data-model.md, integration-points.md, known-gotchas.md (українською; файл, що не стосується фічі, містить одне речення «Не стосується: …»).
- Коміти закінчуються рядком `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Робота в гілці `feature/booking-platform`.

## Review Focus

1. **Datetime без офсету або з чужим офсетом** (`2026-11-03T10:00:00`, `…Z`) — без офсету 422, з будь-яким офсетом коректно порівнюється з бронюваннями в Києві. Тест у Task 8.
2. **Часткове перетинання слотів** (нове 10:30–11:30 при існуючому 10:00–11:00 того ж майстра) — 409 `slot_taken`, а перетин з `cancelled` бронюванням — дозволено. Тест у Task 8.
3. **Недопустимі переходи стану** — reschedule/cancel не-`scheduled`, повторний refund, waive не-`no_show` → 409 `invalid_state`; refund більше передоплати → 422. Тести в Task 9.
4. **Різні формати телефону** — пошук `?phone=0671234567` знаходить клієнта, збереженого як `+380 67 123 45 67`; дубль у тенанті → 409 `invalid_state`. Тест у Task 6.
5. **Чужий тенант у шляху** — `/api/tenants/dentaplus/bookings/b-olena-1` → 404 `not_found` (і для клієнтів, майстрів, послуг, дій). Тест у Task 9.

---

## File Structure

```
docker-compose.yml                      усі сервіси
.env.example
app/backend/
  Dockerfile  pyproject.toml
  docker/init-test-db.sql               створює БД booking_test
  booking/
    main.py         create_app(), CORS, error handlers, startup (create_all + seed if empty)
    config.py       Settings (pydantic-settings)
    db.py           Base, engine, SessionLocal, get_session
    clock.py        now() -> aware datetime (Europe/Kyiv); тести підміняють
    errors.py       ApiError, обробники
    ids.py          new_id(prefix)
    phone.py        normalize_phone(raw) -> str
    models.py       усі таблиці
    schemas.py      pydantic In/Out + серіалізатори
    seed.py         seed(session, now), reset(session, now)
    services/slots.py  services/bookings.py  services/chat.py
    routers/tenants.py staff.py services.py clients.py bookings.py actions.py
            slots.py messages_tickets.py support.py admin.py
  tests/conftest.py + test_*.py
app/mcp/
  Dockerfile  pyproject.toml
  booking_mcp/server.py  __main__.py
  tests/test_server.py
app/web/                                 create-next-app + Dockerfile
  lib/api.ts  lib/types.ts  lib/policy-text.ts
  app/page.tsx
  app/b/[tenant]/page.tsx  book/page.tsx  support/page.tsx
  app/admin/[tenant]/layout.tsx  page.tsx (бронювання)  clients/  staff/  services/  settings/  support/
  components/…
  public/widget.js  public/demo-salon-site.html     (stretch)
docs/features/<booking-api|mcp-server|support-chat|business-page|admin-panel|support-widget>/
```

---

### Task 1: Каркас репо, Docker з Postgres, FastAPI health, тестова база

**Files:**
- Create: `docker-compose.yml` (поки лише `db`), `.env.example`, `.gitignore`, `app/backend/pyproject.toml`, `app/backend/docker/init-test-db.sql`, `app/backend/booking/{__init__,main,config,db,clock,errors,ids,phone}.py`, `app/backend/tests/{conftest,test_health,test_phone}.py`

**Interfaces:**
- Produces: `create_app() -> FastAPI`; `get_session()` (FastAPI dependency, yields `Session`); `Base`; `clock.now() -> datetime`; `ApiError(code: str, message: str, status: int)`; `new_id(prefix: str) -> str`; `normalize_phone(raw: str) -> str`; pytest fixtures `client: TestClient`, `session: Session`, константа `NOW = datetime(2026, 11, 2, 8, 0, tzinfo=ZoneInfo("Europe/Kyiv"))` (понеділок) з підміною `booking.clock.now`.

- [ ] **Step 1:** `git checkout -b feature/booking-platform`. Створити `docker-compose.yml` з сервісом `db` (`postgres:16`, user/password/db `booking`, порт 5432, volume `pgdata`, healthcheck `pg_isready`, монтує `init-test-db.sql` у `/docker-entrypoint-initdb.d/`). `docker compose up -d db`. Expected: `docker compose ps` — db healthy.
- [ ] **Step 2:** `cd app/backend && uv init --package --name booking` (або вручну pyproject), `uv add fastapi uvicorn[standard] sqlalchemy psycopg[binary] pydantic-settings httpx tzdata`, `uv add --dev pytest`.
- [ ] **Step 3: Failing tests**

```python
def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json() == {"status": "ok"}

def test_unknown_route_error_shape(client):
    r = client.get("/api/tenants/nope")
    assert r.status_code == 404
    assert r.json()["error"] == "not_found"

@pytest.mark.parametrize("raw,expected", [
    ("+380 67 123-45-67", "380671234567"),
    ("0671234567", "380671234567"),
    ("380671234567", "380671234567"),
])
def test_normalize_phone(raw, expected):
    assert normalize_phone(raw) == expected
```
(`test_unknown_route_error_shape` поки може перевіряти лише 404 від неіснуючого роуту з нашою формою — обробник 404 FastAPI теж віддає `{"error":"not_found",...}`.)

- [ ] **Step 4:** `uv run pytest` → FAIL.
- [ ] **Step 5:** Реалізувати модулі. `conftest.py`: engine на `TEST_DATABASE_URL` (default `postgresql+psycopg://booking:booking@localhost:5432/booking_test`), `drop_all/create_all` раз на сесію, перед кожним тестом `TRUNCATE … CASCADE` усіх таблиць; `client` підміняє `get_session` і `clock.now`. Обробники: `ApiError` → її статус і форма; `RequestValidationError` → 422 `validation` з першою помилкою в `message`; `StarletteHTTPException` 404 → `not_found`.
- [ ] **Step 6:** `uv run pytest` → PASS.
- [ ] **Step 7:** Commit `chore: scaffold backend, postgres in docker, error format`.

---

### Task 2: Моделі даних і серіалізатори

**Files:**
- Create: `app/backend/booking/models.py`, `app/backend/booking/schemas.py`, `app/backend/tests/test_models.py`

**Interfaces:**
- Consumes: `Base`, `new_id`.
- Produces: моделі `Tenant, Staff, StaffService, StaffSchedule, Service, Client, GoodwillException, Booking, BookingEvent, OutgoingMessage, Ticket, Conversation, ChatMessage` (поля — спек 5.2; `Tenant.policy: JSONB`; `Booking.start/end: TIMESTAMPTZ`; `prepayment_amount, prepayment_status, no_show_fee_amount, no_show_fee_status`).
  Серіалізатори: `tenant_out(t) -> dict`, `client_out(c, session, with_bookings: bool) -> dict` (рахує `visits_count`=completed, `no_show_count`=no_show; `goodwill_exceptions: [{date, booking_id, reason}]`), `booking_out(b, expand: bool) -> dict` (`prepayment: {amount, status}`, `no_show_fee: {amount, status}`, `history: [{ts, event, by, note}]` за часом; при `expand` — вкладені `client`, `staff`, `service`), `staff_out`, `service_out`, `message_out`, `ticket_out`, `conversation_out`, `chat_message_out`. Datetime у відповідях — ISO з офсетом Києва.
  Pydantic-модель `Policy` (усі поля зі спеки агента, з `agent_permissions: AgentPermissions`), літерали статусів.
  Хелпер `add_event(session, booking, event: str, by: str, note: str = "")`.

- [ ] **Step 1: Failing test** — створити тенанта, клієнта, 2 бронювання (completed і no_show), подію; перевірити `client_out` → `visits_count == 1`, `no_show_count == 1`; `booking_out(b, expand=True)` має ключі `prepayment`, `no_show_fee`, `history`, `client`, `staff`, `service`, а `start` закінчується на `+02:00`.
- [ ] **Step 2:** `uv run pytest tests/test_models.py` → FAIL.
- [ ] **Step 3:** Реалізувати.
- [ ] **Step 4:** PASS.
- [ ] **Step 5:** Commit `feat(backend): data model and serializers`.

---

### Task 3: Сід мок-даних, reset, старт застосунку

**Files:**
- Create: `app/backend/booking/seed.py`, `app/backend/booking/routers/admin.py`, `app/backend/tests/test_seed.py`
- Modify: `app/backend/booking/main.py` (startup: `create_all`, `seed` якщо порожньо; підключити роутер)

**Interfaces:**
- Produces: `seed(session, now: datetime) -> None`, `reset(session, now) -> None` (видаляє все, сіє заново); `POST /api/admin/reset` → `{"status": "ok"}`.
- Значення демо-ядра — рівно спека агента розділ 5 + спек 5.5:
  - `lumen` «Lumen Beauty», salon; policy: window 24, forfeits true, no_show_fee 300, prepayment true; reschedule auto, cancel auto, refund auto_under_limit, refund_auto_limit 500, goodwill auto, goodwill_per_client_per_180d 1, goodwill_requires_zero_no_shows true, waive_no_show_fee approval.
  - `dentaplus` «DentaPlus», clinic; window 48, forfeits true, no_show_fee 500, prepayment true; reschedule auto, cancel approval, refund approval, refund_auto_limit 0, goodwill approval, per_180d 1, requires_zero_no_shows true, waive forbidden.
  - lumen: майстер `maria` «Марія»; `olena` 12 completed / 0 no_show, `b-olena-1` завтра 10:00 «Стрижка + укладка» у Марії, передоплата 500 held; `max` 2 completed / 2 no_show, `b-max-1` завтра 11:00, 400 held; `ira` 5 completed / 0 no_show, goodwill 30 днів тому, `b-ira-1` через 3 дні 15:00, 500 held.
  - dentaplus: `petro` 3 completed / 0 no_show, `b-petro-1` завтра 09:00 «Консультація», 800 held; `anna` — `b-anna-1` вчора, `no_show`, штраф 500 charged.
    (09:00 поза графіком 10–19: для DentaPlus графік 09:00–18:00.)
  - Опис, адреса, телефон тенантів — правдоподібні вигадані.
- Фон: по 3 майстри (включно з `maria` у lumen), 4–6 послуг, ~25 клієнтів, бронювання за 30 днів назад і 7 вперед; `random.Random(42)`; графік пн–сб. Майбутні фонові бронювання займають ≤50% слотів і не чіпають слоти демо-бронювань. Лічильники демо-клієнтів формуються лише їхніми власними минулими бронюваннями.

- [ ] **Step 1: Failing tests**

Тести читають через `session` + серіалізатори Task 2 (HTTP-роутів ще немає); conftest сіє з `NOW`.

```python
def test_seed_demo_core(session):
    o = client_out(session.get(Client, "olena"), session, with_bookings=True)
    assert (o["visits_count"], o["no_show_count"]) == (12, 0)
    b = next(b for b in o["bookings"] if b["id"] == "b-olena-1")
    assert b["start"] == "2026-11-03T10:00:00+02:00"
    assert b["prepayment"] == {"amount": 500, "status": "held"}

def test_seed_anna_no_show_fee(session):
    b = booking_out(session.get(Booking, "b-anna-1"), expand=False)
    assert b["status"] == "no_show" and b["no_show_fee"] == {"amount": 500, "status": "charged"}

def test_seed_ira_goodwill(session):
    ira = client_out(session.get(Client, "ira"), session, with_bookings=False)
    assert len(ira["goodwill_exceptions"]) == 1
    assert ira["goodwill_exceptions"][0]["date"].startswith("2026-10-03")

def test_reset_endpoint_restores_state(client, session):
    session.get(Booking, "b-olena-1").status = "cancelled"; session.commit()
    assert client.post("/api/admin/reset").status_code == 200
    session.expire_all()
    assert session.get(Booking, "b-olena-1").status == "scheduled"

def test_seed_is_deterministic(session):
    reset(session, NOW); ids1 = sorted(b.id for b in session.query(Booking))
    reset(session, NOW); ids2 = sorted(b.id for b in session.query(Booking))
    assert ids1 == ids2
```
Фонові id — детерміновані (`f"b-{tenant}-{n}"`), не `new_id`.

- [ ] **Step 2:** FAIL. **Step 3:** Реалізувати. **Step 4:** PASS.
- [ ] **Step 5:** Commit `feat(backend): deterministic demo seed and reset`.

---

### Task 4: Тенанти і політика (CRUD)

**Files:**
- Create: `app/backend/booking/routers/tenants.py`, `app/backend/tests/test_tenants.py`

**Interfaces:**
- Produces: `GET /api/tenants`, `POST /api/tenants` (`{name, kind, timezone?, description?, address?, phone?, instagram?, policy?}`; id = slug з name або `new_id("t")`; policy за замовчуванням — як у lumen), `GET /api/tenants/{t}` (Tenant із policy — контракт агента), `PATCH /api/tenants/{t}`, `DELETE /api/tenants/{t}` (каскадом), `PUT /api/tenants/{t}/policy` (повна Policy, валідація літералів → 422).
  Хелпер для інших роутерів: `get_tenant_or_404(session, tenant_id) -> Tenant`.

- [ ] **Step 1: Failing tests:** список містить `lumen` і `dentaplus`; `GET /api/tenants/lumen` → `policy.agent_permissions.refund == "auto_under_limit"`, `refund_auto_limit == 500`; PUT policy з `refund: "maybe"` → 422 `validation`; PUT валідна → GET повертає нову; POST → 201 і GET працює; DELETE → наступний GET 404 `not_found`.
- [ ] **Step 2:** FAIL. **Step 3:** Реалізувати. **Step 4:** PASS.
- [ ] **Step 5:** Commit `feat(backend): tenants and policy CRUD`.

---

### Task 5: Майстри, графік, послуги (CRUD)

**Files:**
- Create: `app/backend/booking/routers/staff.py`, `app/backend/booking/routers/services.py`, `app/backend/tests/test_staff_services.py`

**Interfaces:**
- Produces: `GET/POST /api/tenants/{t}/staff`, `GET/PATCH/DELETE …/staff/{id}`, `PUT …/staff/{id}/schedule` (тіло `[{weekday: 0-6, start: "HH:MM", end: "HH:MM"}]`, `start < end`, інакше 422); `staff_out` містить `service_ids` і `schedule`. `GET/POST /api/tenants/{t}/services`, `GET/PATCH/DELETE …/services/{id}` (`duration_min > 0`, `price >= 0`).
  Хелпер `has_future_scheduled(session, **filter) -> bool` (у `services/bookings.py`).

- [ ] **Step 1: Failing tests:** створити майстра з `service_ids`, PUT графіка, GET повертає їх; графік `start >= end` → 422; DELETE `maria` (має `b-olena-1`) → 409 `invalid_state`; DELETE нового майстра без бронювань → 204; DELETE послуги з майбутнім бронюванням → 409; послуга з `duration_min: 0` → 422; `GET /api/tenants/dentaplus/staff/maria` → 404.
- [ ] **Step 2:** FAIL. **Step 3:** Реалізувати. **Step 4:** PASS.
- [ ] **Step 5:** Commit `feat(backend): staff, schedules, services CRUD`.

---

### Task 6: Клієнти (CRUD, пошук, профіль)

**Files:**
- Create: `app/backend/booking/routers/clients.py`, `app/backend/tests/test_clients.py`

**Interfaces:**
- Produces: `GET /api/tenants/{t}/clients?phone=&q=` → `[Client]` (phone — точний збіг після нормалізації; q — підрядок імені/телефону, без регістру); `GET …/clients/{id}` → Client + `bookings` (нові зверху) — контракт агента; `POST` (`{name, phone, notes?}`; дубль телефону → 409 `invalid_state`); `PATCH`; `DELETE` (з майбутніми scheduled → 409).

- [ ] **Step 1: Failing tests:** `?phone=` у різних форматах знаходить того самого клієнта (Review Focus 4); дубль → 409; `GET …/clients/olena` має `bookings[0]` з найпізнішим `start`; `GET /api/tenants/dentaplus/clients/olena` → 404; `?q=оле` знаходить Олену.
- [ ] **Step 2:** FAIL. **Step 3:** Реалізувати. **Step 4:** PASS.
- [ ] **Step 5:** Commit `feat(backend): clients CRUD and lookup`.

---

### Task 7: Пошук вільних слотів

**Files:**
- Create: `app/backend/booking/services/slots.py`, `app/backend/booking/routers/slots.py`, `app/backend/tests/test_slots.py`

**Interfaces:**
- Produces: `find_free_slots(session, tenant, service, start: datetime, end: datetime, staff_id: str | None, now: datetime) -> list[Slot]` де `Slot = {staff_id, staff_name, start, end}`; `is_slot_free(session, staff, start, end, exclude_booking_id: str | None) -> bool` (у графіку майстра, не в минулому, без перетину з `scheduled`). `GET /api/tenants/{t}/slots?service_id=&from=&to=&staff_id=` — контракт агента; сортування за `start`, потім `staff_name`. Лише майстри, що надають послугу.
- Алгоритм: для кожного дня в [from, to) у таймзоні тенанта, для кожного рядка графіка: старти кроком 60 хв від `start` поки `start + duration <= end`.

- [ ] **Step 1: Failing tests:** lumen, послуга `b-olena-1`, from = 2026-11-03, to = +7 днів → ≥3 слоти; слоту Марії 2026-11-03T10:00 немає; жодного слоту раніше `NOW`; неділі немає; послуга 90 хв не дає старту 18:00 при кінці 19:00; `staff_id=maria` → усі слоти Марії; невідома послуга → 404.
- [ ] **Step 2:** FAIL. **Step 3:** Реалізувати. **Step 4:** PASS.
- [ ] **Step 5:** Commit `feat(backend): free slot search`.

---

### Task 8: Бронювання (список, створення, редагування, видалення)

**Files:**
- Create: `app/backend/booking/routers/bookings.py`, `app/backend/tests/test_bookings.py`
- Modify: `app/backend/booking/services/bookings.py`

**Interfaces:**
- Consumes: `is_slot_free`, `add_event`, `normalize_phone`.
- Produces: `GET /api/tenants/{t}/bookings?from=&to=&staff_id=&status=` (без `expand`, але з `client_name`, `staff_name`, `service_name` для таблиці); `GET …/bookings/{id}` (expand — контракт агента); `POST …/bookings` `{client_id? | client: {name, phone}, service_id, staff_id, start, by?}` → 201; `PATCH …/bookings/{id}` `{status?: "completed"|"no_show", notes?, by?}`; `DELETE …/bookings/{id}` → 204.
  `create_booking(...)`, `mark_status(...)` у `services/bookings.py`.
- Правила (спек 5.3): клієнт знаходиться за нормалізованим телефоном або створюється; передоплата = ціна послуги `held`, якщо `prepayment_required`, інакше `{amount: 0, status: "none"}`; `end = start + duration`; майстер не надає послугу → 422; слот зайнятий/поза графіком/у минулому → 409 `slot_taken`; `no_show` → `no_show_fee = {policy.no_show_fee, "charged"}`; PATCH не-`scheduled` → 409; подія в history: `created`, `completed`, `no_show`.

- [ ] **Step 1: Failing tests:** створення новим клієнтом → клієнт з'явився, передоплата = ціна; створення на 2026-11-03T10:00 у Марії → 409 `slot_taken`; **10:30 при 10:00–11:00 → 409** (Review Focus 2); після cancel `b-olena-1` слот 10:00 вільний; `start` без офсету → 422 (Review Focus 1); `start` `2026-11-03T08:00:00Z` (=10:00 Київ) у Марії → 409; PATCH `no_show` → fee charged + подія; список за тиждень містить `b-olena-1` з `client_name == "Олена"`.
- [ ] **Step 2:** FAIL. **Step 3:** Реалізувати. **Step 4:** PASS.
- [ ] **Step 5:** Commit `feat(backend): bookings CRUD with integrity rules`.

---

### Task 9: Дії підтримки (контракт агента), повідомлення, тікети + документація booking-api

**Files:**
- Create: `app/backend/booking/routers/actions.py`, `app/backend/booking/routers/messages_tickets.py`, `app/backend/tests/test_actions.py`, `app/backend/tests/test_acceptance.py`, `docs/features/booking-api/*` (10 файлів)

**Interfaces:**
- Produces (форма — спека агента розділ 4):
  - `POST …/bookings/{id}/reschedule` `{start, staff_id?, reason, by, forfeit_prepayment}` — тільки `scheduled`; `is_slot_free(..., exclude_booking_id=id)`; forfeit → `prepayment.status = "forfeited"`; подія `rescheduled` з нотаткою «старий → новий час».
  - `POST …/cancel` `{reason, by, forfeit_prepayment}` — тільки `scheduled`; `forfeited` або лишається `held`.
  - `POST …/refund` `{amount, reason, by}` — `prepayment.status == "held"` (інакше 409); `0 < amount <= prepayment.amount` (інакше 422); → `refunded`.
  - `POST …/waive-no-show` `{reason, by}` — тільки `status == "no_show"` і fee `charged`; → `waived`.
  - `POST …/clients/{id}/goodwill` `{booking_id, reason, by}` — бронювання цього клієнта; → оновлений Client.
  - `POST …/messages` `{client_id, channel: "chat"|"sms", text}` → OutgoingMessage (201); `GET …/messages?client_id=`.
  - `POST …/tickets` `{client_id, summary, priority}` → Ticket `open` (201); `GET …/tickets?status=`; `PATCH …/tickets/{id}` `{status}`.
  Кожна дія з бронюванням пише подію з `by` і `reason`.

- [ ] **Step 1: Failing tests** — по одному успішному кейсу на кожну дію + Review Focus 3 (reschedule скасованого → 409 `invalid_state`; refund двічі → 409; refund 600 з 500 → 422; waive для `scheduled` → 409) + Review Focus 5 (`/api/tenants/dentaplus/bookings/b-olena-1/cancel` → 404; goodwill з чужим booking_id → 404).
- [ ] **Step 2: Acceptance test** — розділ 8 спеки агента дослівно в `test_acceptance.py`: (1) GET olena з b-olena-1; (2) slots ≥3; (3) reschedule `b-olena-1` на перший слот → 200, новий `start`; (4) reschedule `b-max-1` на той самий слот → 409 `slot_taken`.
- [ ] **Step 3:** FAIL. **Step 4:** Реалізувати. **Step 5:** `uv run pytest` — усі PASS.
- [ ] **Step 6:** Написати `docs/features/booking-api/` (10 файлів): ендпоінти, правила цілісності, що апка не перевіряє політику, gotchas (таймзони, нормалізація телефону, reset).
- [ ] **Step 7:** Commit `feat(backend): support actions, messages, tickets per agent contract`.

---

### Task 10: Чат підтримки і підключення агента

**Files:**
- Create: `app/backend/booking/services/chat.py`, `app/backend/booking/routers/support.py`, `app/backend/tests/test_support_chat.py`
- Modify: `app/backend/booking/routers/messages_tickets.py` (chat-повідомлення → у розмову)

**Interfaces:**
- Produces (спек 5.4): `POST /api/tenants/{t}/support/conversations` `{client_phone?, client_name?}` → Conversation (якщо телефон знайдено — `client_id` заповнено); `GET …/support/conversations?status=` (з останнім повідомленням і `client_name`); `GET …/support/conversations/{id}/messages?after=<iso>`; `POST …/support/conversations/{id}/messages` `{text}` → зберігає `role=client`, потім `forward_to_agent`; `POST …/support/conversations/{id}/reply` `{text, role: "agent"|"human"}`; `PATCH …/support/conversations/{id}` `{status, client_id?}`.
  `forward_to_agent(conversation, messages) -> str | None` у `services/chat.py`: якщо `settings.agent_url` — `httpx.post(f"{agent_url}/chat", json={tenant_id, conversation_id, client_id, messages:[{role,text,ts}]}, timeout=60)`; відповідь `{reply}` → `role=agent`; помилка/таймаут → `role=agent` текст «Агент тимчасово недоступний, адміністратор відповість найближчим часом»; без `agent_url` → «Агент підтримки ще не підключений».
  `POST …/messages` з `channel=chat` додає `role=agent` повідомлення в останню `open` розмову клієнта (якщо є).

- [ ] **Step 1: Failing tests:** без AGENT_URL → після повідомлення клієнта в розмові 2 повідомлення, друге — заглушка; з AGENT_URL і замоканим `httpx.post` (monkeypatch) → відповідь агента збережена, payload містить `tenant_id` і всю історію; таймаут → текст недоступності; `POST /messages channel=chat` для olena з відкритою розмовою → з'являється в розмові; `?after=` віддає лише новіші.
- [ ] **Step 2:** FAIL. **Step 3:** Реалізувати. **Step 4:** PASS.
- [ ] **Step 5:** Commit `feat(backend): support chat with agent webhook`.

---

### Task 11: Бекенд у Docker

**Files:**
- Create: `app/backend/Dockerfile`, `app/backend/.dockerignore`
- Modify: `docker-compose.yml`, `.env.example`

**Interfaces:**
- Produces: сервіс `backend` (порт 8001, `DATABASE_URL=postgresql+psycopg://booking:booking@db:5432/booking`, `AGENT_URL` з `.env`, `depends_on: db: condition: service_healthy`, bind mount `./app/backend/booking` + `uvicorn --reload`).

- [ ] **Step 1:** Dockerfile на `python:3.14-slim` + uv (`COPY --from=ghcr.io/astral-sh/uv`), `uv sync --frozen --no-dev`, CMD `uv run uvicorn booking.main:create_app --factory --host 0.0.0.0 --port 8001`.
- [ ] **Step 2:** `docker compose up -d --build backend`.
- [ ] **Step 3: Verify:** `curl -s localhost:8001/api/tenants/lumen/clients/olena` → JSON Олени з `b-olena-1`. `docker compose restart backend` → дані не задублювались (`curl -s localhost:8001/api/tenants | jq length` → 2).
- [ ] **Step 4:** Commit `chore: run backend in docker`.

---

### Task 12: MCP-сервер + документація mcp-server

**Files:**
- Create: `app/mcp/pyproject.toml`, `app/mcp/booking_mcp/{__init__,server,__main__}.py`, `app/mcp/tests/test_server.py`, `app/mcp/Dockerfile`, `docs/features/mcp-server/*`
- Modify: `docker-compose.yml`

**Interfaces:**
- Consumes: HTTP API (Tasks 4–9).
- Produces: `build_server(api_url: str, http: httpx.AsyncClient | None = None) -> FastMCP`. Інструменти (спек 5.6), параметри = поля тіла/квері API + `tenant_id`:
  `get_tenant(tenant_id)`, `find_client_by_phone(tenant_id, phone)`, `get_client(tenant_id, client_id)`, `get_booking(tenant_id, booking_id)`, `find_slots(tenant_id, service_id, date_from, date_to, staff_id=None)`, `reschedule_booking(tenant_id, booking_id, start, reason, forfeit_prepayment, staff_id=None, by="agent")`, `cancel_booking(tenant_id, booking_id, reason, forfeit_prepayment, by="agent")`, `refund_booking(tenant_id, booking_id, amount, reason, by="agent")`, `waive_no_show(tenant_id, booking_id, reason, by="agent")`, `add_goodwill(tenant_id, client_id, booking_id, reason, by="agent")`, `send_message(tenant_id, client_id, text, channel="chat")`, `create_ticket(tenant_id, client_id, summary, priority="normal")`.
  Успіх → JSON відповіді API. 4xx → рядок `"{error}: {message}"` (не виняток). Кожен docstring: коли викликати, що змінює, що політику перевіряє агент.
  `__main__`: `MCP_TRANSPORT=http|stdio` (default http), host 0.0.0.0, port 8002, path `/mcp`; `APP_API_URL`.
- Перед реалізацією звірити API встановленої версії FastMCP (`uv run python -c "import fastmcp; print(fastmcp.__version__)"` і її docs: декоратор інструментів, `Client` для in-memory тестів, `run(transport=...)`).

- [ ] **Step 1:** `uv init`, `uv add fastmcp httpx`, `uv add --dev pytest pytest-asyncio`.
- [ ] **Step 2: Failing tests** (in-memory `fastmcp.Client(build_server(..., http=AsyncClient(transport=MockTransport(handler))))`):
  `find_slots` шле `GET /api/tenants/lumen/slots` з `service_id`, `from`, `to`; `reschedule_booking` шле POST з `by == "agent"`; відповідь 409 `slot_taken` → текст інструмента починається з `"slot_taken:"`; список інструментів містить усі 12 назв.
- [ ] **Step 3:** FAIL. **Step 4:** Реалізувати. **Step 5:** PASS.
- [ ] **Step 6:** Dockerfile (як бекенд), сервіс `mcp` у compose (порт 8002, `APP_API_URL=http://backend:8001`, `depends_on: backend`). `docker compose up -d --build mcp`.
- [ ] **Step 7: Verify проти живого стеку:** скрипт `app/mcp/scripts/smoke.py` через `fastmcp.Client("http://localhost:8002/mcp")`: `find_slots` для lumen → бере перший слот → `reschedule_booking b-olena-1` → `get_booking` показує новий `start` і подію з `by: agent`. Потім `curl -XPOST localhost:8001/api/admin/reset`.
- [ ] **Step 8:** `docs/features/mcp-server/` (10 файлів), включно з інструкцією підключення для тіммейта (HTTP URL і stdio-команда).
- [ ] **Step 9:** Commit `feat(mcp): MCP server over booking API`.

---

### Task 13: Next.js каркас у Docker, API-клієнт, головна

**Files:**
- Create: `app/web/*` (create-next-app: TypeScript, App Router, Tailwind, ESLint, без `src/`), `app/web/Dockerfile`, `app/web/lib/types.ts`, `app/web/lib/api.ts`, `app/web/app/page.tsx`
- Modify: `docker-compose.yml`

**Interfaces:**
- Produces: `lib/types.ts` — TS-типи, що дзеркалять відповіді API (`Tenant, Policy, Staff, Service, Client, Booking, Slot, OutgoingMessage, Ticket, Conversation, ChatMessage`); `lib/api.ts` — `api.get<T>(path)`, `api.post<T>(path, body)`, `api.patch`, `api.put`, `api.del`; кидає `ApiError {code, message}`; базовий URL `process.env.NEXT_PUBLIC_API_URL`; `useApi<T>(path | null, {refreshMs?})` на SWR. Спільні компоненти: `components/ui/{Button,Input,Select,Modal,Table,Badge,Toast}.tsx`.
  Сервіс `web`: `node:22`, bind mount `./app/web`, anonymous volume `node_modules`, `npm run dev -- -H 0.0.0.0 -p 3000`.

- [ ] **Step 1:** Згенерувати проєкт у контейнері: `docker run --rm -v "$PWD/app/web:/app" -w /app node:22 npx create-next-app@latest . --ts --app --tailwind --eslint --no-src-dir --use-npm --import-alias "@/*"`. `npm i swr`.
- [ ] **Step 2:** Реалізувати типи, клієнт, UI-примітиви, `/` — картки бізнесів (назва, тип, адреса) з посиланнями на `/b/[id]` і `/admin/[id]`.
- [ ] **Step 3: Verify:** `docker compose up -d --build web`; `docker compose exec web npx tsc --noEmit` → без помилок; `docker compose exec web npm run lint` → без помилок; `curl -s localhost:3000 | grep -c "Lumen Beauty"` ≥ 1 (або відкрити в браузері).
- [ ] **Step 4:** Commit `feat(web): next.js scaffold, api client, home`.

---

### Task 14: Сторінка бізнесу і запис + документація business-page

**Files:**
- Create: `app/web/lib/policy-text.ts`, `app/web/app/b/[tenant]/page.tsx`, `app/web/app/b/[tenant]/book/page.tsx`, `app/web/components/booking/*`, `docs/features/business-page/*`

**Interfaces:**
- Consumes: `GET /api/tenants/{t}`, `/services`, `/staff`, `/slots`, `POST /bookings`.
- Produces: `policyToText(policy: Policy): string[]` — людські правила, напр. для lumen: «Скасування або перенесення пізніше ніж за 24 год — передоплата не повертається», «Неявка — штраф 300 грн», «Потрібна передоплата». (agent_permissions не показуються клієнтам.)
- Запис: послуга → майстер (або «будь-хто») → дні на 7 днів уперед → слоти дня → ім'я + телефон → підтвердження з датою, майстром, сумою передоплати. 409 `slot_taken` → повідомлення «Цей час щойно зайняли» і оновлений список слотів.

- [ ] **Step 1:** Unit-тест для `policyToText` (додати `vitest`): lumen-політика дає рядки з «24 год» і «300 грн»; dentaplus — «48 год» і «500 грн».
- [ ] **Step 2:** `npx vitest run` → FAIL. **Step 3:** Реалізувати функцію → PASS.
- [ ] **Step 4:** Реалізувати сторінки.
- [ ] **Step 5: Verify в браузері:** `/b/lumen` показує інфо, послуги, правила, кнопки; пройти запис новим клієнтом → підтвердження; повторний запис на той самий слот з іншої вкладки → «щойно зайняли». `tsc --noEmit` і lint чисті. Reset.
- [ ] **Step 6:** `docs/features/business-page/` (10 файлів).
- [ ] **Step 7:** Commit `feat(web): business page and booking flow`.

---

### Task 15: Чат підтримки для клієнта + документація support-chat

**Files:**
- Create: `app/web/app/b/[tenant]/support/page.tsx`, `app/web/components/chat/*`, `docs/features/support-chat/*`

**Interfaces:**
- Consumes: Task 10 ендпоінти.
- Produces: старт — форма «Ім'я, телефон» (телефон потрібен, щоб агент знайшов бронювання) → `POST /support/conversations` → id розмови зберігається в `localStorage` під `support:<tenant>` (у try/catch); стрічка повідомлень з опитуванням `?after=` кожні 2 с; ролі `client`/`agent`/`human` різного вигляду (`human` — підпис «Адміністратор»); індикатор «агент друкує», поки чекаємо відповідь на POST. `?embed=1` — без шапки сайту, на всю висоту.

- [ ] **Step 1:** Реалізувати.
- [ ] **Step 2: Verify:** `/b/lumen/support` з телефоном Олени → повідомлення → у стрічці з'являється заглушка «Агент підтримки ще не підключений». Запустити тестовий агент-ехо (`app/backend/scripts/echo_agent.py`: FastAPI на 9000, `POST /chat` → `{"reply": "echo: <останній текст>"}`), задати `AGENT_URL=http://host.docker.internal:9000`, перезапустити backend → відповідь «echo: …». `?embed=1` без шапки. tsc/lint чисті.
- [ ] **Step 3:** `docs/features/support-chat/` (10 файлів) з контрактом `/chat` для тіммейта.
- [ ] **Step 4:** Commit `feat(web): customer support chat page`.

---

### Task 16: Адмінка — каркас і бронювання

**Files:**
- Create: `app/web/app/admin/[tenant]/layout.tsx`, `app/web/app/admin/[tenant]/page.tsx`, `app/web/components/admin/{BookingWeek,BookingCard,BookingForm,Timeline,ResetButton}.tsx`

**Interfaces:**
- Consumes: bookings CRUD (Task 8), дії (Task 9), slots.
- Produces: layout — бокове меню (Бронювання, Клієнти, Майстри, Послуги, Налаштування, Підтримка з бейджем відкритих тікетів), назва бізнесу, кнопка «Скинути демо» (`POST /api/admin/reset` з підтвердженням). Сторінка бронювань: тиждень (колонки — дні, рядки — майстри), навігація по тижнях, фільтр статусу, кольори статусів; опитування 3 с. `BookingCard` (модалка): деталі, передоплата, штраф, `Timeline` з history (події `by: agent` підсвічені й з міткою «AI»), дії: позначити completed/no_show, перенести (вибір слота), скасувати (з/без втрати передоплати), повернути, зняти штраф, видалити — усе з `by: "human:admin"`. «Нове бронювання» — форма з вибором клієнта/нового, послуги, майстра, слота. Помилки API — toast з `message`.

- [ ] **Step 1:** Реалізувати.
- [ ] **Step 2: Verify:** `/admin/lumen` показує `b-olena-1` завтра 10:00. Через MCP smoke-скрипт (Task 12) перенести → протягом ~3 с картка в новому місці, у таймлайні подія з міткою «AI». Створити, позначити no_show, видалити бронювання через UI. tsc/lint чисті. Reset.
- [ ] **Step 3:** Commit `feat(web): admin layout and bookings`.

---

### Task 17: Адмінка — клієнти, майстри, послуги

**Files:**
- Create: `app/web/app/admin/[tenant]/clients/page.tsx`, `clients/[id]/page.tsx`, `staff/page.tsx`, `services/page.tsx`, `app/web/components/admin/{ClientForm,StaffForm,ScheduleEditor,ServiceForm}.tsx`

**Interfaces:**
- Consumes: Tasks 5, 6, 8.
- Produces: клієнти — таблиця з пошуком (`?q=`), лічильники візитів/неявок, створення/редагування/видалення; картка клієнта — бронювання, винятки goodwill, нотатки. Майстри — список, форма (ім'я, послуги-чекбокси), `ScheduleEditor` (7 днів, вкл/викл, час з/до). Послуги — таблиця + форма (назва, тривалість, ціна). 409 при видаленні → toast «Є майбутні бронювання».

- [ ] **Step 1:** Реалізувати.
- [ ] **Step 2: Verify:** повний цикл створити→змінити→видалити для клієнта, майстра, послуги; видалення Марії → toast; новий майстер з графіком пн 12–14 → у `/b/lumen/book` у понеділок лише слоти 12:00 і 13:00. tsc/lint. Reset.
- [ ] **Step 3:** Commit `feat(web): admin CRUD for clients, staff, services`.

---

### Task 18: Адмінка — налаштування і підтримка + документація admin-panel

**Files:**
- Create: `app/web/app/admin/[tenant]/settings/page.tsx`, `app/web/app/admin/[tenant]/support/page.tsx`, `app/web/components/admin/{PolicyForm,ConversationList,ConversationView,TicketList,MessageLog}.tsx`, `docs/features/admin-panel/*`

**Interfaces:**
- Consumes: Task 4 (PATCH tenant, PUT policy), Tasks 9–10.
- Produces: налаштування — дані бізнесу + `PolicyForm` з усіма полями Policy (числа, перемикачі, селекти для `agent_permissions` з людськими підписами: «Сам», «З погодженням», «Заборонено», «Сам до ліміту»). Підтримка — три вкладки: розмови (список з опитуванням 3 с → перегляд, відповідь як `human`, закрити), тікети (пріоритет-бейдж, клієнт, summary, закрити), вихідні повідомлення (лог).

- [ ] **Step 1:** Реалізувати.
- [ ] **Step 2: Verify:** змінити `cancellation_window_hours` на 12 → `/b/lumen` показує «12 год»; через curl `POST /tickets` → з'являється у вкладці без перезавантаження; розмова з Task 15 видна, відповідь адміністратора з'являється в клієнтському чаті з підписом «Адміністратор». tsc/lint. Reset.
- [ ] **Step 3:** `docs/features/admin-panel/` (10 файлів).
- [ ] **Step 4:** Commit `feat(web): admin settings and support inbox`.

---

### Task 19: Наскрізна перевірка з нуля

**Files:**
- Create: `README.md` (запуск, порти, як підключити агента: MCP URL, `AGENT_URL`, контракт `/chat`, reset)

- [ ] **Step 1:** `docker compose down -v && docker compose up -d --build`. Expected: усі 4 сервіси up, `curl localhost:8001/api/health` → ok.
- [ ] **Step 2:** `cd app/backend && uv run pytest` → усі PASS; `cd app/mcp && uv run pytest` → PASS; `docker compose exec web npx vitest run` → PASS.
- [ ] **Step 3:** Демо-прогін: `/b/lumen/support` (телефон Олени) → `/admin/lumen`; MCP smoke → перенос видно в адмінці з «AI»; reset повертає все.
- [ ] **Step 4:** Commit `docs: README with run and agent integration`.

---

### Task 20 (stretch): Віджет для чужого сайту + документація support-widget

**Files:**
- Create: `app/web/public/widget.js`, `app/web/public/demo-salon-site.html`, `docs/features/support-widget/*`

**Interfaces:**
- Produces: `<script src="http://localhost:3000/widget.js" data-tenant="lumen"></script>` — додає плаваючу кнопку (правий нижній кут, без зовнішніх стилів сторінки — inline-стилі, `z-index` максимальний), клік відкриває/ховає iframe 380×600 на `/b/<tenant>/support?embed=1` (origin — з `src` скрипта). `demo-salon-site.html` — простий «власний сайт Lumen Beauty» з цим скриптом.

- [ ] **Step 1:** Реалізувати.
- [ ] **Step 2: Verify:** відкрити `localhost:3000/demo-salon-site.html` → кнопка → чат працює, повідомлення видно в `/admin/lumen/support`.
- [ ] **Step 3:** Документація (10 файлів). Commit `feat(web): embeddable support widget`.
