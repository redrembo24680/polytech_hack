# Спека: AI support-агент для платформи бронювань

Дата: 2026-10-31 · Статус: чернетка для затвердження · Бюджет: ~4 години
Пов'язана спека: `2026-10-31-booking-app-design.md` (продукт і API, які агент використовує).

## 1. Мета і межі

Агент, який не відповідає, а **вирішує** звернення клієнтів бізнесу-тенанта: розуміє мету,
зважує політику тенанта та історію клієнта, виконує дії через tools у межах дозволів, ризикові
дії віддає людині на апрув, показує інтерактивні картки замість стін тексту і логує reasoning
для support-людини.

Входить у MVP: ядро агента, permission engine, 9 tools, картки, чат клієнта + copilot, два
демо-сценарії. Stretch: голосовий канал через managed-платформу, міні-метрики.
Не входить: автентифікація, персистентність між рестартами, реальні SMS.

## 2. Структура

```
agent/                  Python 3.12+, FastAPI, anthropic SDK, uv
  main.py               FastAPI app, ендпоінти
  agent.py              сесія, системний промпт, tool_runner
  tools.py              @beta_tool функції
  policy.py             permission engine (чиста логіка)
  datasource.py         Protocol DataSource + MemoryDataSource + HttpDataSource
  seed.json             копія сід-даних зі спеки апки (для MemoryDataSource)
  events.py             лог подій сесій, approvals, метрики
  cards.py              схеми карток (pydantic)
  tests/                pytest
web/
  index.html            два екрани поруч: чат клієнта | copilot
  app.js, style.css
```

Запуск: `uv run uvicorn agent.main:app --port 8000`, фронт відкривається як статичний файл
або роздається FastAPI з `/`.

## 3. DataSource

`DataSource` — Protocol з методами 1:1 до API апки: `get_tenant`, `get_client`,
`find_client_by_phone`, `get_booking`, `find_slots`, `reschedule`, `cancel`, `refund`,
`waive_no_show`, `add_goodwill`, `send_message`, `create_ticket`.
Помилки апки (`slot_taken`, `invalid_state`, `not_found`) піднімаються як `DataError(code, message)`.

- `MemoryDataSource` — читає `seed.json`, тримає стан у пам'яті, реалізує ту саму валідацію,
  що й апка (слот зайнятий, сума ≤ передоплати, статуси).
- `McpDataSource` — клієнт до MCP-сервера платформи (`APP_MCP_URL`, streamable HTTP; пакет
  `mcp`), викликає tools з тими самими іменами, що методи Protocol.
- `HttpDataSource` — httpx-клієнт до `APP_API_URL` (запасний варіант, якщо MCP не готовий).
- Вибір: `APP_MCP_URL` → Mcp, інакше `APP_API_URL` → Http, інакше Memory. Агент не знає різниці.
- Чому не віддаємо MCP-tools моделі напряму: між моделлю і дією має стояти permission engine
  і approval-флоу. Тому tools агента — наші обгортки, а MCP лише транспорт до даних.

## 4. Permission engine (`policy.py`)

Чиста функція `decide(action, ctx) -> Decision`, де
`action` ∈ {reschedule, cancel, refund, goodwill_exception, waive_no_show_fee, escalate},
`ctx` містить policy тенанта, клієнта (visits, no_shows, goodwill history), бронювання, аргументи
(сума refund, час до візиту) і `now`.

`Decision = Allow(reason) | NeedsApproval(reason) | Forbidden(reason)`. `reason` — одне речення
українською, яке йде і моделі, і в copilot.

Правила (у порядку перевірки):
1. Режим дії з `agent_permissions`: `forbidden` → Forbidden; `approval` → NeedsApproval.
2. `refund`: при `auto_under_limit` сума ≤ `refund_auto_limit` → Allow, інакше NeedsApproval.
3. `goodwill_exception` при `auto`: NeedsApproval, якщо `goodwill_requires_zero_no_shows` і
   `no_show_count > 0` (людина може зробити виняток, агент сам — ні); NeedsApproval, якщо за
   180 днів винятків ≥ ліміту; інакше Allow.
4. `reschedule`/`cancel` при `auto` → Allow. Чи згорає передоплата — окреме обчислення
   `is_late_change(policy, booking, now) -> bool` (час до візиту < cancellation_window_hours
   і `late_change_forfeits_prepayment`). Пізня зміна без goodwill → `forfeit_prepayment=True`
   і для cancel, і для reschedule.
5. `escalate` завжди Allow.

Усе покривається табличними тестами без мережі.

## 5. Tools (`tools.py`)

Усі через `@beta_tool`, докстрінги українською з чіткими аргументами. Tools мають доступ до
поточної сесії (tenant_id, client_id, session_id) через contextvar.

| Tool | Ризик | Що робить |
|---|---|---|
| `get_client_profile()` | read | профіль + історія бронювань поточного клієнта |
| `get_booking(booking_id)` | read | бронювання з деталями |
| `find_slots(service_id, from_date, to_date, staff_id?)` | read | вільні слоти |
| `reschedule_booking(booking_id, start, staff_id?, reason)` | write | policy → дія; сам рахує `is_late_change` і передає `forfeit_prepayment`, якщо goodwill не застосовано |
| `cancel_booking(booking_id, reason)` | write | policy → дія; сам рахує `is_late_change` і передає `forfeit_prepayment` |
| `refund_prepayment(booking_id, amount, reason)` | write | policy → дія |
| `apply_goodwill_exception(booking_id, reason)` | write | policy → дія; при Allow також зберігає передоплату при пізньому скасуванні/перенесенні |
| `waive_no_show_fee(booking_id, reason)` | write | policy → дія |
| `escalate_to_human(summary, priority)` | write | створює Ticket, завжди дозволено |
| `show_card(card)` | ui | емітить картку в події сесії, повертає "картку показано" |

Поведінка write-tool:
- `Allow` → виконує через DataSource, повертає JSON результату + `decision.reason`.
- `NeedsApproval` → створює `Approval{id, session_id, tool, args, reason, status=pending}`,
  емітить подію, повертає моделі
  `{"status":"pending_approval","approval_id":..,"reason":..,"instruction":"Повідом клієнту, що уточнюєш в адміністратора, і заверши хід."}`.
- `Forbidden` → повертає `{"status":"forbidden","reason":..}`; модель пояснює і пропонує альтернативу або ескалює.
- `DataError` → `tool_result` з `is_error=True` і текстом помилки.

## 6. Агент (`agent.py`)

- **Провайдер моделі визначається кредитами спонсорів хакатону** (через MLH DevRelay,
  `devrelay-offers`), власні гроші на API не витрачаємо. Рішення фіксується в
  `docs/features/support-agent/integration-points.md` після перевірки офферів.
  Кандидати: Anthropic (`claude-opus-5-5`, Tool Runner SDK), Google Gemini (`google-genai`,
  function calling), локальна модель через OpenAI-сумісний сервер.
- Межа `llm.py`: один клас `LLM` з методом `run_turn(system, messages, tools) -> events`,
  який крутить tool-loop для обраного провайдера і віддає уніфіковані події (text, tool_call,
  tool_result, reasoning). Решта агента (policy, tools, events, API) провайдера не знає.
  Назва моделі і провайдер — env `AGENT_PROVIDER`, `AGENT_MODEL`.
- Для Anthropic: `thinking={"type":"adaptive","display":"summarized"}`,
  `output_config={"effort":"medium"}`, `max_tokens=4096`, `fallbacks="default"`
  з betas `server-side-fallback-2026-07-01` (якщо `tool_runner` приймає).
- Системний промпт (стабільна частина кешується через `cache_control`):
  роль, принципи (спочатку зрозумій мету, потім дані, потім дія; не вигадуй; ризикове — через
  апрув; коротко і по-людськи українською), опис карток і коли їх показувати, правило "після
  pending_approval заверши хід". Динамічна частина: тенант і його політика у читабельному
  вигляді (жорсткі ворота `agent_permissions` + `rules_text` власника дослівно, з інструкцією:
текст уточнює поведінку, але не дає прав понад ворота), профіль клієнта, поточна дата/час.
RAG не потрібен: правила тенанта це кілька абзаців, вони повністю входять у промпт.
- Сесія = `messages` список + метадані. `send(text)` додає user-повідомлення, запускає
  `client.beta.messages.tool_runner(...)`, ітерує повідомлення, емітить події
  (thinking summary, tool_call, tool_result, assistant_message), зберігає повний `content`
  кожного assistant-повідомлення в історію.
- Після рішення апруву: `resume_after_approval(approval, result)` додає user-повідомлення
  `[SYSTEM] Апрув #id: схвалено/відхилено людиною (нотатка). Результат дії: ...` і знову
  запускає runner, щоб агент відповів клієнту.

## 7. Картки (`cards.py`)

Модель викликає `show_card(card)` з одним із типів:
- `slots`: `{type, title, options:[{id, start, staff_name, label}]}` — фронт рендерить кнопки;
  клік шле в чат текст "Обираю слот <id>".
- `booking_summary`: `{type, booking_id, service, staff, start, prepayment, status, timeline:[{ts,event}]}`.
- `decision`: `{type, title, outcome, reasoning:[..], actions_taken:[..]}` — підсумок для клієнта.
Approval-картка генерується системою (не моделлю) у copilot із tool, args, reason і кнопками.

## 8. Події і API (`events.py`, `main.py`)

Подія: `{id, ts, session_id, type, payload}`, `type` ∈ user_message, assistant_message,
thinking, tool_call, tool_result, card, approval_created, approval_decided, error.

| Метод | Шлях | Опис |
|---|---|---|
| POST | `/sessions` `{tenant_id, client_id, channel}` | створює сесію |
| POST | `/sessions/{id}/messages` `{text}` | запускає агента, повертає після завершення ходу |
| GET | `/sessions/{id}/events?after=<event_id>` | полінг подій (фронт кожні 700 мс) |
| GET | `/tenants/{id}/approvals?status=pending` | для copilot |
| POST | `/approvals/{id}/decide` `{approve: bool, note, by}` | виконує/відхиляє, резюмить агента |
| GET | `/tenants/{id}/metrics` | лічильники: сесій, дій auto, апрувів, ескалацій, середній час до рішення |
| POST | `/voice/tools/{tool_name}` | stretch: webhook для голосової платформи, той самий tools+policy шлях |

Запуск агента синхронний у threadpool FastAPI. Одна сесія обробляє одне повідомлення за раз.

## 9. Фронт (`web/`)

Один HTML, два стовпці:
- **Ліворуч: чат клієнта.** Вибір тенанта і клієнта зверху (для демо), повідомлення, картки
  (slots як кнопки, summary як таблиця, decision як блок).
- **Праворуч: copilot.** Живий потік подій: reasoning, виклики tools із результатами, approval-
  картки з кнопками "Схвалити" / "Відхилити" і полем нотатки, блок метрик тенанта.
Без фреймворку, fetch + setInterval.

## 10. Демо-сценарії (acceptance)

**A. Олена, Lumen Beauty (автономно).** "Дитина захворіла, не встигну завтра на 10, можна щось
зробити?" → агент читає профіль, бачить 12 візитів / 0 no-show, застосовує goodwill (Allow),
шукає слоти, показує картку з 3 слотами, після вибору переносить, передоплата збережена, показує
decision-картку. У copilot видно reasoning і всі tool-виклики.

**B. Максим, Lumen Beauty (апрув).** Той самий запит → goodwill NeedsApproval (2 no-show) →
агент чесно пояснює: перенести може, але за правилами передоплата згорає, виняток має
підтвердити адміністратор → картка в copilot з reasoning і рекомендацією → людина схвалює →
агент застосовує виняток, переносить зі збереженням передоплати і відповідає клієнту.
(Якщо людина відхиляє — агент пропонує перенесення зі згорянням або скасування.)

**C. Петро, DentaPlus.** "Хочу скасувати і повернути гроші" → cancel approval + refund approval
→ дві approval-картки, агент коректно чекає.

## 11. Тести

- `tests/test_policy.py` — табличні тести `decide` на всі режими і граничні випадки (ліміт refund, 180 днів, no-show).
- `tests/test_datasource.py` — MemoryDataSource: slot_taken, refund > суми, статуси.
- `tests/test_tools.py` — tools з MemoryDataSource і фейковою сесією: Allow виконує, NeedsApproval створює approval і не виконує.
- `tests/test_api.py` — FastAPI TestClient з підмінним агентом (без мережі): сесії, події, decide.
- Smoke з реальним API: прогін сценаріїв A і B вручну після появи `ANTHROPIC_API_KEY`.

## 12. Stretch: голос

Managed-платформа (Vapi або ElevenLabs Conversational) з tools, що б'ють у
`POST /voice/tools/{tool_name}` з `{tenant_id, phone, args}`; сервер знаходить клієнта за
телефоном, створює/знаходить сесію каналу `voice`, проганяє через policy і DataSource. Картки
в голосі замінюються на `send_message` (SMS-лог). Потрібен ngrok. Робимо тільки після того, як
сценарії A і B працюють у чаті.

## 13. Ризики

- Немає `ANTHROPIC_API_KEY` на машині — отримати до старту `agent.py`.
- MCP/API тіммейта не готовий — працюємо на MemoryDataSource до кінця, перемикання через env.
- Розбіжність семантики MCP-tools і Protocol — контракт зафіксовано у спеці апки, розділ 4;
  будь-яка зміна іменувань узгоджується там.
- Латентність Opus із thinking — effort medium, короткий промпт, кешування системної частини.
