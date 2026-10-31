# Спека: скелет застосунку — мульти-тенант платформа бронювань

Дата: 2026-10-31 · Для: тіммейт, який будує продукт · Статус: чернетка для узгодження
Пов'язана спека: `2026-10-31-support-agent-design.md` (агент, який викликає цей API).

## 1. Мета

Мінімальний продукт-сцена для демо support-агента. Платформа, де бізнеси (тенанти: салони,
клініки, студії) ведуть розклад і бронювання, а їхні клієнти бронюють послуги з передоплатою.
Продукт навмисно простий. Він має: (а) тримати дані, (б) виставити HTTP JSON API, який викликає
агент, (в) мати сід-дані для двох демо-сценаріїв. UI продукту опціональний.

Часовий бюджет: ~4 години. Пріоритети строго в такому порядку:
1. Сід-дані (розділ 5) + інтерфейс для агента (розділ 4: MCP або HTTP). Без цього демо немає.
2. Адмінка тенанта: список бронювань, черга апрувів (бере з агента), метрики (розділ 6).
3. CRUD власника (послуги, майстри, розклад, правила текстом) і сторінка запису для клієнта.
4. Реєстрація і підписка — лише як заглушка, якщо лишиться час.

Бачення платформи (для контексту): одна SaaS для всіх бізнесів "за записом" (салони, барбершопи,
стоматології, фітнес, СТО). Бізнес підключається, задає послуги, розклад і правила, і AI-підтримка
працює одразу. Агент не знає нічого про бізнес наперед, усе читає через інтерфейс нижче.

## 2. Технічні рамки

- Мова і фреймворк на вибір тіммейта. Єдина жорстка вимога: HTTP JSON API за контрактом нижче.
- База: in-memory або SQLite, скидається при рестарті, засівається з `seed` на старті.
- CORS відкритий (агент і фронт ходять з інших портів).
- Порт за замовчуванням 8001. Агент читає `APP_API_URL` (наприклад `http://localhost:8001`).
- Код живе в `app/` у цьому ж репо.

## 3. Модель даних

Усі id — рядки. Час — ISO 8601 з таймзоною (`2026-11-01T10:00:00+02:00`). Гроші — цілі гривні.

**Tenant**
```
id, name, kind ("salon" | "clinic"), timezone, policy: Policy
```

**Policy** (правила тенанта; агент читає їх і сам вирішує, що можна)

Два шари. `agent_permissions` — жорсткі ворота, перевіряються кодом (permission engine агента).
`rules_text` — правила вільним текстом, як їх написав власник; агент читає їх у промпті і
використовує для нюансів ("постійним клієнтам один раз пробачаємо", "у суботу перенесення не
робимо"). Текст не може розширити ворота, лише звузити або уточнити.
```
rules_text: str                         # вільний текст власника, 1–5 абзаців
cancellation_window_hours: int          # напр. 24
late_change_forfeits_prepayment: bool   # пізнє скасування АБО перенесення = передоплата згорає
no_show_fee: int                        # грн
prepayment_required: bool
agent_permissions:
  reschedule: "auto" | "approval"
  cancel: "auto" | "approval"
  refund: "auto_under_limit" | "approval" | "forbidden"
  refund_auto_limit: int                # грн, для auto_under_limit
  goodwill_exception: "auto" | "approval" | "forbidden"
  goodwill_per_client_per_180d: int     # скільки винятків на клієнта за пів року
  goodwill_requires_zero_no_shows: bool
  waive_no_show_fee: "auto" | "approval" | "forbidden"
```

**Client**
```
id, tenant_id, name, phone, visits_count, no_show_count,
goodwill_exceptions: [ {date, booking_id, reason} ], notes: str
```

**Staff** `id, tenant_id, name, service_ids: [..]`

**Service** `id, tenant_id, name, duration_min, price`

**Booking**
```
id, tenant_id, client_id, staff_id, service_id, start, end,
status: "scheduled" | "completed" | "cancelled" | "no_show",
prepayment: { amount: int, status: "held" | "refunded" | "forfeited" | "none" },
history: [ {ts, event, by, note} ]        # для таймлайну в картках
```

**Availability** — для кожного майстра: робочі години на день (напр. 10:00–19:00, крок 60 хв).
Вільний слот = робочий час мінус існуючі бронювання.

**OutgoingMessage** `id, tenant_id, client_id, channel ("chat"|"sms"), text, ts`

**Ticket** (ескалація людині) `id, tenant_id, client_id, summary, priority ("low"|"normal"|"high"|"urgent"), status ("open"|"closed"), ts`

## 4. Інтерфейс для агента: MCP (основний) або HTTP (запасний)

**MCP-сервер** — один для всіх тенантів, `tenant_id` передається аргументом кожного tool.
Транспорт: streamable HTTP на `APP_MCP_URL` (напр. `http://localhost:8001/mcp`) або stdio.
Імена tools і їхні аргументи = рядки таблиць нижче (`get_tenant`, `list_clients`, `get_client`,
`list_client_bookings` (= bookings із `get_client`, окремо для зручності), `find_client_by_phone`, `get_booking`, `find_slots`, `reschedule_booking`, `cancel_booking`,
`refund_prepayment`, `waive_no_show_fee`, `add_goodwill`, `send_message`, `create_ticket`).
Результат tool — той самий JSON, що й відповідь HTTP; помилка — `{"error": код, "message": ...}`.
Опціонально (stretch): `get_no_show_risk(tenant_id, client_id)` → `{score: 0..1, factors: [..]}`
(проста евристика з no_show_count і visits_count) і `find_waitlist_candidates(tenant_id, slot)`.

**HTTP API** — якщо MCP не встигається, той самий контракт як REST.
Префікс: `/api/tenants/{tenant_id}`. Відповідь 2xx — JSON сутності. Помилки — 4xx з
`{"error": "код", "message": "людський текст"}`. Коди: `not_found`, `invalid_state`
(напр. перенести скасоване), `slot_taken`, `validation`.

**Читання**
| Метод | Шлях | Відповідь |
|---|---|---|
| GET | `/` | Tenant із policy |
| GET | `/clients` | `[Client]` усі клієнти тенанта (для селектора в UI агента) |
| GET | `/clients/{client_id}` | Client + `bookings: [Booking]` (усі, нові зверху) |
| GET | `/clients?phone=...` | `[Client]` (пошук для голосу/ідентифікації) |
| GET | `/bookings/{booking_id}` | Booking + вкладені `client`, `staff`, `service` |
| GET | `/slots?service_id=&from=&to=&staff_id=` | `[{staff_id, staff_name, start, end}]` вільні слоти; `staff_id` опціональний |

**Дії**
| Метод | Шлях | Тіло | Ефект |
|---|---|---|---|
| POST | `/bookings/{id}/reschedule` | `{start, staff_id?, reason, by, forfeit_prepayment: bool}` | status лишається scheduled, start/end оновлені; передоплата переноситься або (forfeit=true) стає forfeited; запис в history. 409 `slot_taken` якщо зайнято |
| POST | `/bookings/{id}/cancel` | `{reason, by, forfeit_prepayment: bool}` | status=cancelled; prepayment.status = forfeited або held (далі refund окремо) |
| POST | `/bookings/{id}/refund` | `{amount, reason, by}` | prepayment.status=refunded, amount ≤ prepayment.amount |
| POST | `/bookings/{id}/waive-no-show` | `{reason, by}` | для status=no_show: знімає fee, запис у history |
| POST | `/clients/{id}/goodwill` | `{booking_id, reason, by}` | додає запис у `goodwill_exceptions` |
| POST | `/messages` | `{client_id, channel, text}` | створює OutgoingMessage, повертає його |
| POST | `/tickets` | `{client_id, summary, priority}` | створює Ticket |

Поле `by` — хто зробив дію: `"agent"`, `"human:<ім'я>"`. Йде в history для таймлайну.

Відповідність MCP ↔ HTTP: `get_tenant`=GET `/`, `list_clients`=GET `/clients`, `get_client`=GET `/clients/{id}`,
`list_client_bookings`=поле `bookings` з GET `/clients/{id}`,
`find_client_by_phone`=GET `/clients?phone=`, `get_booking`=GET `/bookings/{id}`,
`find_slots`=GET `/slots`, `reschedule_booking`=POST `.../reschedule`, `cancel_booking`=POST
`.../cancel`, `refund_prepayment`=POST `.../refund`, `waive_no_show_fee`=POST
`.../waive-no-show`, `add_goodwill`=POST `/clients/{id}/goodwill`, `send_message`=POST
`/messages`, `create_ticket`=POST `/tickets`.

**Важливо:** апка **не** перевіряє політику тенанта (чи можна агенту робити refund). Це робить
permission engine агента. Апка перевіряє лише цілісність даних (слот вільний, сума ≤ передоплати,
статус валідний).

## 5. Сід-дані (обов'язково для демо)

**Тенант A — "Lumen Beauty"** (салон), м'яка політика:
cancellation_window 24h, late change forfeits prepayment, no_show_fee 300, prepayment required;
permissions: reschedule auto, cancel auto, refund auto_under_limit (limit 500),
goodwill auto (1 на 180 днів, requires zero no-shows), waive_no_show_fee approval.

**Тенант B — "DentaPlus"** (клініка), жорстка політика:
cancellation_window 48h, no_show_fee 500; permissions: reschedule auto, cancel approval,
refund approval, goodwill approval (1 на 180 днів), waive_no_show_fee forbidden.

**Клієнти тенанта A:**
- `olena` — Олена, 12 візитів, 0 no-show, без винятків. Бронювання `b-olena-1`: завтра 10:00,
  "Стрижка + укладка", майстер Марія, передоплата 500 held.
- `max` — Максим, 2 візити, 2 no-show. Бронювання `b-max-1`: завтра 11:00, передоплата 400 held.
- `ira` — Ірина, 5 візитів, 0 no-show, виняток уже використаний 30 днів тому.
  Бронювання `b-ira-1`: через 3 дні 15:00, передоплата 500.

**Клієнти тенанта B:**
- `petro` — Петро, 3 візити, 0 no-show. Бронювання `b-petro-1`: завтра 09:00, консультація,
  передоплата 800 held.
- `anna` — Анна, статус no_show за вчорашнє бронювання `b-anna-1`, fee 500 нарахований.

**Майстри і слоти:** у кожного тенанта 2–3 майстри, робочі години 10:00–19:00, так щоб на
найближчі 7 днів було по кілька вільних слотів у кожного (агент має знайти 3 варіанти).

## 6. Адмінка тенанта (пріоритет 2)

Одна сторінка: список бронювань на тиждень зі статусом і history (щоб у демо було видно, що
перенесення реально сталось), черга апрувів і метрики. Апруви та метрики апка **не** рахує сама,
а бере з агента: `GET http://localhost:8000/tenants/{id}/approvals?status=pending`,
`POST .../approvals/{id}/decide`, `GET .../tenants/{id}/metrics` (звернень, закрито автоматично,
апрувів, ескалацій, збережено грн). Можна голим HTML + fetch.

Сід-дані мають також містити `rules_text` для обох тенантів, наприклад для Lumen Beauty:
"Скасування менш ніж за 24 години — депозит не повертаємо. Постійним клієнтам без неявок один
раз на пів року йдемо назустріч. У суботу перенесення тільки через адміністратора."
Для DentaPlus: "Скасування менш ніж за 48 годин — депозит згорає. Повернення коштів тільки через
адміністратора. Неявка — 500 грн, не знімаємо."


## 7. Що НЕ робимо

Авторизація, реальні платежі, нотифікації, мульти-валюта, редагування політики через UI,
міграції. Політика задається в seed.

## 8. Готовність

API вважається готовим, коли проходить ручний сценарій:
1. `GET /api/tenants/lumen/clients/olena` повертає Олену з `b-olena-1`.
2. `GET /api/tenants/lumen/slots?service_id=...&from=завтра&to=+7д` повертає ≥3 слоти.
3. `POST .../bookings/b-olena-1/reschedule` на один із них повертає оновлене бронювання.
4. Повторний reschedule на той самий слот іншого клієнта дає 409 `slot_taken`.
