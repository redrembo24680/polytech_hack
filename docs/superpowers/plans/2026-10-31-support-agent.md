# Support Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** AI support-агент для мульти-тенант платформи бронювань: розуміє звернення клієнта, діє через tools у межах дозволів тенанта, ризикове віддає людині на апрув, показує картки, логує reasoning для copilot.

**Architecture:** FastAPI-сервіс `agent/` з провайдер-агностичним tool-loop; між моделлю і будь-якою дією стоїть `policy.decide()`. Дані через `DataSource` (in-memory із `seed.json`, пізніше MCP/HTTP тіммейта). Статичний фронт `web/` з двома панелями поллить події.

**Tech Stack:** Python 3.12+, uv, FastAPI, uvicorn, pydantic v2, google-genai (Gemma 4 через Gemini API), httpx, pytest. Фронт: голий HTML/JS/CSS.

**Spec:** `docs/superpowers/specs/2026-10-31-support-agent-design.md` (контракт даних: `docs/superpowers/specs/2026-10-31-booking-app-design.md`).

## Global Constraints

- Мова коду/ідентифікаторів англійська; тексти для клієнта, докстрінги tools і `reason` рішень — українською.
- Усі id — рядки; час — ISO 8601 з таймзоною (`Europe/Kyiv`); гроші — цілі гривні.
- Модель за замовчуванням `gemma-4-31b-it`; провайдер/модель через env `AGENT_PROVIDER` (default `gemini`), `AGENT_MODEL`; ключ `GEMINI_API_KEY`.
- Жодна мутація даних не виконується без `policy.decide()` → `Allow`.
- Тести без мережі: `GeminiClient` ніколи не імпортується в тестах, крім `tests/test_llm_gemini.py`, який підміняє SDK.
- Після кожної задачі: `uv run pytest -q` зелений, коміт, рядок у `docs/WORKLOG.md`.
- Документація фічі: `docs/features/support-agent/` (10 файлів) заповнюється в Task 9.

## Review Focus

1. Клієнт пише про "завтра", а бронювання вже скасоване або completed → tools повертають `invalid_state`, агент пояснює і не вигадує (Task 1, 4).
2. Два запити на той самий слот → другий отримує `slot_taken`, агент пропонує інший (Task 1).
3. Refund на суму більшу за передоплату або коли prepayment не `held` → `validation`/`invalid_state`, не "успіх" (Task 1, 4).
4. Approval вирішено двічі або для чужої сесії → 409, стан не змінюється (Task 3, 7).
5. Модель викликає невідомий tool або з невалідними аргументами → `tool_result` з помилкою, loop продовжується, сервер не падає (Task 6).

---

## File Structure

```
pyproject.toml                 uv-проєкт, залежності, pytest config
agent/__init__.py
agent/models.py                pydantic-моделі сутностей і Policy
agent/seed.json                сід-дані (2 тенанти, 5 клієнтів) з відносними датами
agent/datasource.py            DataSource Protocol, DataError, MemoryDataSource
agent/policy.py                decide(), is_late_change(), Decision-типи
agent/events.py                EventLog, Approval, ApprovalStore, metrics()
agent/context.py               contextvar поточної сесії для tools
agent/tools.py                 ToolSpec, ToolRegistry, 10 tools
agent/llm.py                   Msg/Part типи, LLMClient Protocol, FakeClient, GeminiClient
agent/agent.py                 build_system_prompt(), run_loop(), Session
agent/main.py                  FastAPI app, ендпоінти, статика
web/index.html, web/app.js, web/style.css
scripts/smoke.py               живий прогін сценарію A/B з реальною моделлю
tests/conftest.py              фікстури: now, datasource, events, session ctx
tests/test_datasource.py
tests/test_policy.py
tests/test_events.py
tests/test_tools.py
tests/test_llm.py
tests/test_agent.py
tests/test_api.py
```

Фіксований `NOW` у тестах: `datetime(2026, 10, 31, 12, 0, tzinfo=ZoneInfo("Europe/Kyiv"))`.

---

### Task 1: Models, seed data, MemoryDataSource

**Files:**
- Create: `pyproject.toml`, `agent/__init__.py`, `agent/models.py`, `agent/seed.json`, `agent/datasource.py`, `tests/conftest.py`
- Test: `tests/test_datasource.py`

**Interfaces:**
- Produces (`agent/models.py`, pydantic BaseModel): `AgentPermissions`, `Policy`, `Tenant`, `Client`, `Staff`, `Service`, `Prepayment`, `HistoryEntry`, `Booking`, `Slot`, `OutgoingMessage`, `Ticket` з полями рівно як у спеці апки, розділ 3. `Booking.start`/`end`: `datetime` (aware). `Client.goodwill_exceptions: list[GoodwillException]` (`date: datetime, booking_id: str, reason: str`).
- Produces (`agent/datasource.py`):
  - `class DataError(Exception)`: `code: str` ∈ {`not_found`,`invalid_state`,`slot_taken`,`validation`}, `message: str`.
  - `class DataSource(Protocol)` з методами: `get_tenant(tenant_id) -> Tenant`, `get_client(tenant_id, client_id) -> Client`, `find_client_by_phone(tenant_id, phone) -> list[Client]`, `list_client_bookings(tenant_id, client_id) -> list[Booking]` (нові зверху), `get_booking(tenant_id, booking_id) -> Booking`, `find_slots(tenant_id, service_id, from_dt, to_dt, staff_id=None) -> list[Slot]`, `reschedule(tenant_id, booking_id, start, staff_id, reason, by, forfeit_prepayment) -> Booking`, `cancel(tenant_id, booking_id, reason, by, forfeit_prepayment) -> Booking`, `refund(tenant_id, booking_id, amount, reason, by) -> Booking`, `waive_no_show(tenant_id, booking_id, reason, by) -> Booking`, `add_goodwill(tenant_id, client_id, booking_id, reason, by) -> Client`, `send_message(tenant_id, client_id, channel, text) -> OutgoingMessage`, `create_ticket(tenant_id, client_id, summary, priority) -> Ticket`.
  - `class MemoryDataSource(DataSource)`: `__init__(self, seed: dict, now: datetime)`; `@classmethod from_file(path, now)`.
- Seed format (`agent/seed.json`): як у спеці апки розділ 5 + `rules_text`; дати бронювань відносні: `"day_offset": 1, "time": "10:00"`; робочі години майстрів `"hours": ["10:00","19:00"]`, крок 60 хв. Ід тенантів: `lumen`, `denta`. Ід бронювань: `b-olena-1` (st-maria), `b-max-1` (st-olha, завтра 11:00), `b-ira-1` (st-maria), `b-petro-1` (st-ivan), `b-anna-1` (st-oksana, status `no_show`, `day_offset: -1`). Сервіси: `lumen`: `svc-cut` "Стрижка + укладка" 60 хв 800; `denta`: `svc-consult` "Консультація" 60 хв 1200. Майстри: `lumen`: `st-maria` Марія, `st-olha` Ольга; `denta`: `st-ivan` Іван, `st-oksana` Оксана.

- [ ] **Step 1: Scaffold project**

`pyproject.toml`: `[project] name="polytech-agent"`, `requires-python=">=3.12"`, deps: `fastapi`, `uvicorn[standard]`, `pydantic>=2`, `google-genai`, `httpx`, `python-dotenv`; dev: `pytest`, `pytest-asyncio`. `[tool.pytest.ini_options] testpaths=["tests"]`. Run `uv sync` → Expected: `.venv` створено, `uv run python -c "import fastapi, google.genai"` без помилок.

- [ ] **Step 2: Write failing tests**

```python
# tests/conftest.py
NOW = datetime(2026, 10, 31, 12, 0, tzinfo=ZoneInfo("Europe/Kyiv"))
@pytest.fixture
def ds(): return MemoryDataSource.from_file(Path("agent/seed.json"), NOW)

# tests/test_datasource.py
def test_get_tenant_policy(ds):
    t = ds.get_tenant("lumen")
    assert t.policy.agent_permissions.refund == "auto_under_limit"
    assert t.policy.agent_permissions.refund_auto_limit == 500
    assert "24 годин" in t.policy.rules_text
def test_get_client_with_bookings(ds):
    c = ds.get_client("lumen", "olena")
    assert (c.visits_count, c.no_show_count) == (12, 0)
    assert ds.list_client_bookings("lumen", "olena")[0].id == "b-olena-1"
def test_booking_start_is_tomorrow_10(ds):
    b = ds.get_booking("lumen", "b-olena-1")
    assert b.start == NOW.replace(hour=10, minute=0) + timedelta(days=1)
    assert b.prepayment.amount == 500 and b.prepayment.status == "held"
def test_unknown_booking_raises_not_found(ds):
    with pytest.raises(DataError) as e: ds.get_booking("lumen", "nope")
    assert e.value.code == "not_found"
def test_find_slots_excludes_taken(ds):
    slots = ds.find_slots("lumen", "svc-cut", NOW + timedelta(days=1), NOW + timedelta(days=2), staff_id="st-maria")
    starts = [s.start for s in slots]
    assert NOW.replace(hour=10, minute=0) + timedelta(days=1) not in starts   # зайнято Оленою
    assert NOW.replace(hour=11, minute=0) + timedelta(days=1) in starts
    assert len(slots) >= 3
def test_reschedule_moves_and_keeps_prepayment(ds):
    new = NOW.replace(hour=14, minute=0) + timedelta(days=2)
    b = ds.reschedule("lumen", "b-olena-1", new, "st-maria", "хвороба", "agent", forfeit_prepayment=False)
    assert b.start == new and b.prepayment.status == "held" and b.history[-1].event == "rescheduled"
def test_reschedule_to_taken_slot_raises(ds):
    taken = ds.get_booking("lumen", "b-max-1").start
    with pytest.raises(DataError) as e: ds.reschedule("lumen", "b-olena-1", taken, "st-olha", "x", "agent", False)
    assert e.value.code == "slot_taken"
def test_reschedule_cancelled_is_invalid_state(ds):
    ds.cancel("lumen", "b-olena-1", "x", "agent", forfeit_prepayment=False)
    with pytest.raises(DataError) as e: ds.reschedule("lumen", "b-olena-1", NOW + timedelta(days=3), None, "x", "agent", False)
    assert e.value.code == "invalid_state"
def test_cancel_forfeits(ds):
    b = ds.cancel("lumen", "b-max-1", "late", "agent", forfeit_prepayment=True)
    assert b.status == "cancelled" and b.prepayment.status == "forfeited"
def test_refund_over_amount_is_validation(ds):
    with pytest.raises(DataError) as e: ds.refund("lumen", "b-olena-1", 900, "x", "agent")
    assert e.value.code == "validation"
def test_refund_marks_refunded(ds):
    assert ds.refund("lumen", "b-olena-1", 500, "x", "agent").prepayment.status == "refunded"
def test_refund_twice_is_invalid_state(ds):
    ds.refund("lumen", "b-olena-1", 500, "x", "agent")
    with pytest.raises(DataError) as e: ds.refund("lumen", "b-olena-1", 1, "x", "agent")
    assert e.value.code == "invalid_state"
def test_waive_no_show_only_for_no_show(ds):
    assert ds.waive_no_show("denta", "b-anna-1", "x", "human:Оля").history[-1].event == "no_show_fee_waived"
    with pytest.raises(DataError): ds.waive_no_show("lumen", "b-olena-1", "x", "agent")
def test_goodwill_message_ticket(ds):
    c = ds.add_goodwill("lumen", "olena", "b-olena-1", "хвороба дитини", "agent")
    assert c.goodwill_exceptions[-1].booking_id == "b-olena-1"
    assert ds.send_message("lumen", "olena", "chat", "привіт").text == "привіт"
    assert ds.create_ticket("lumen", "olena", "складний кейс", "high").status == "open"
def test_ira_has_used_exception_30_days_ago(ds):
    ex = ds.get_client("lumen", "ira").goodwill_exceptions
    assert len(ex) == 1 and (NOW - ex[0].date).days == 30
```

- [ ] **Step 3: Run tests, verify fail** — `uv run pytest tests/test_datasource.py -q` → ImportError.

- [ ] **Step 4: Implement `agent/models.py`, `agent/seed.json`, `agent/datasource.py`**

Seed loader: `day_offset`/`time` → aware datetime у `Europe/Kyiv` від `now`; `goodwill_exceptions` у seed: `{"days_ago": 30, ...}`. `find_slots`: для кожного майстра з `service_id` у `service_ids` (або лише `staff_id`) генерує старти по годинах у робочий час на кожен день в діапазоні, викидає ті, що перетинаються зі `scheduled` бронюваннями майстра; повертає ≤ 12, відсортовано. `reschedule`: перевіряє `status == "scheduled"` (інакше `invalid_state`), слот вільний (інакше `slot_taken`), `end = start + duration`; `forfeit_prepayment=True` → `prepayment.status="forfeited"`. `refund`: `prepayment.status != "held"` → `invalid_state`; `amount > prepayment.amount` або `≤ 0` → `validation`. Кожна мутація додає `HistoryEntry(ts=now, event, by, note=reason)` з подіями `rescheduled|cancelled|refunded|no_show_fee_waived|goodwill_applied`.

- [ ] **Step 5: Run tests, verify pass** — `uv run pytest -q` → all PASS.

- [ ] **Step 6: Commit** — `git add pyproject.toml uv.lock agent tests && git commit -m "feat(agent): models, seed data, MemoryDataSource"`

---

### Task 2: Permission engine

**Files:**
- Create: `agent/policy.py`
- Test: `tests/test_policy.py`

**Interfaces:**
- Consumes: `Policy`, `Client`, `Booking` з Task 1.
- Produces: `Action = Literal["reschedule","cancel","refund","goodwill_exception","waive_no_show_fee","escalate"]`; dataclasses `Allow(reason)`, `NeedsApproval(reason)`, `Forbidden(reason)`; `Decision = Allow | NeedsApproval | Forbidden`; `PolicyContext(policy: Policy, client: Client, booking: Booking | None, now: datetime, amount: int | None = None)`; `decide(action: Action, ctx: PolicyContext) -> Decision`; `is_late_change(policy: Policy, booking: Booking, now: datetime) -> bool`; `goodwill_used_in_window(client: Client, now: datetime, days: int = 180) -> int`.

- [ ] **Step 1: Write failing tests** (табличні, фікстури з `ds` і `NOW`)

```python
def test_mode_forbidden_wins():            # denta waive_no_show_fee forbidden
    assert isinstance(decide("waive_no_show_fee", ctx("denta","anna","b-anna-1")), Forbidden)
def test_mode_approval():                  # denta cancel approval
    assert isinstance(decide("cancel", ctx("denta","petro","b-petro-1")), NeedsApproval)
def test_refund_under_limit_allowed():     # lumen 500 <= 500
    assert isinstance(decide("refund", ctx("lumen","olena","b-olena-1", amount=500)), Allow)
def test_refund_over_limit_needs_approval():
    assert isinstance(decide("refund", ctx("lumen","olena","b-olena-1", amount=501)), NeedsApproval)
def test_goodwill_allowed_for_loyal_client():   # olena: 0 no-show, 0 винятків
    assert isinstance(decide("goodwill_exception", ctx("lumen","olena","b-olena-1")), Allow)
def test_goodwill_with_no_shows_needs_approval():  # max: 2 no-show
    d = decide("goodwill_exception", ctx("lumen","max","b-max-1"))
    assert isinstance(d, NeedsApproval) and "неявк" in d.reason
def test_goodwill_limit_reached_needs_approval():  # ira: виняток 30 днів тому, ліміт 1/180
    assert isinstance(decide("goodwill_exception", ctx("lumen","ira","b-ira-1")), NeedsApproval)
def test_reschedule_auto_allowed():
    assert isinstance(decide("reschedule", ctx("lumen","olena","b-olena-1")), Allow)
def test_escalate_always_allowed():
    assert isinstance(decide("escalate", ctx("denta","anna",None)), Allow)
def test_is_late_change_true_within_window():   # завтра 10:00, window 24h, now 12:00 → 22h
    assert is_late_change(policy("lumen"), booking("lumen","b-olena-1"), NOW) is True
def test_is_late_change_false_outside_window(): # ira через 3 дні
    assert is_late_change(policy("lumen"), booking("lumen","b-ira-1"), NOW) is False
def test_every_decision_has_ukrainian_reason():
    for a in ["reschedule","cancel","refund","goodwill_exception","waive_no_show_fee","escalate"]:
        assert decide(a, ctx("lumen","olena","b-olena-1", amount=100)).reason
```

- [ ] **Step 2: Run, verify fail.**
- [ ] **Step 3: Implement `agent/policy.py`** за правилами спеки розділ 4 (порядок 1→5). `reason` — одне речення українською з конкретикою (сума, ліміт, кількість неявок).
- [ ] **Step 4: Run, verify pass.**
- [ ] **Step 5: Commit** — `git commit -m "feat(agent): permission engine"`

---

### Task 3: Events, approvals, metrics

**Files:**
- Create: `agent/events.py`
- Test: `tests/test_events.py`

**Interfaces:**
- Produces: `EventType = Literal["user_message","assistant_message","thinking","tool_call","tool_result","card","approval_created","approval_decided","error"]`; `Event(id: int, ts: datetime, session_id: str, tenant_id: str, type: EventType, payload: dict)`; `class EventLog`: `emit(session_id, tenant_id, type, payload) -> Event`, `since(session_id, after_id: int = 0) -> list[Event]`, `for_tenant(tenant_id) -> list[Event]`; `Approval(id: str, session_id: str, tenant_id: str, tool: str, args: dict, reason: str, status: Literal["pending","approved","rejected"], decided_by: str | None, note: str | None, created_at, decided_at)`; `class ApprovalStore`: `create(session_id, tenant_id, tool, args, reason) -> Approval`, `get(id) -> Approval` (KeyError), `pending(tenant_id) -> list[Approval]`, `decide(id, approve: bool, by: str, note: str | None) -> Approval` (піднімає `ValueError("already_decided")` якщо не pending); `metrics(log: EventLog, approvals: ApprovalStore, tenant_id) -> dict` з ключами `sessions, messages, tool_calls, auto_actions, approvals_pending, approvals_approved, approvals_rejected, escalations, money_saved_uah`.

- [ ] **Step 1: Write failing tests**: `test_emit_increments_ids_and_since_filters`, `test_approval_lifecycle` (create → pending містить → decide approve → status approved, decided_by), `test_decide_twice_raises`, `test_metrics_counts` (емітити 2 tool_call з payload `{"name":"refund_prepayment","decision":"allow"}`, 1 `{"name":"escalate_to_human"}`; створити 1 approval; `money_saved_uah` = сума payload `saved_uah` у `tool_result`).
- [ ] **Step 2: Run, fail.** **Step 3: Implement.** **Step 4: Run, pass.**
- [ ] **Step 5: Commit** — `git commit -m "feat(agent): event log, approvals, metrics"`

---

### Task 4: Tools with policy gating

**Files:**
- Create: `agent/context.py`, `agent/tools.py`
- Test: `tests/test_tools.py`

**Interfaces:**
- Consumes: `DataSource`, `decide`, `is_late_change`, `EventLog`, `ApprovalStore`.
- Produces (`agent/context.py`): `@dataclass SessionCtx(session_id, tenant_id, client_id, now: datetime, ds: DataSource, events: EventLog, approvals: ApprovalStore)`; `current: ContextVar[SessionCtx]`; `use(ctx)` context manager.
- Produces (`agent/tools.py`): `@dataclass ToolSpec(name, description, parameters: dict, fn: Callable[..., dict])`; `class ToolRegistry`: `register(spec)`, `get(name) -> ToolSpec`, `declarations() -> list[dict]` (`{"name","description","parameters"}` JSON-schema, `additionalProperties` не використовувати), `call(name, args: dict) -> dict` (невідомий tool → `{"error":"unknown_tool"}`; TypeError аргументів → `{"error":"validation","message":...}`; `DataError` → `{"error": code, "message"}`); `default_registry() -> ToolRegistry` з 10 tools зі спеки розділ 5. Результати write-tools: Allow → `{"status":"done", "decision_reason": ..., "booking": {...}}` (+ `"saved_uah": amount` коли goodwill зберіг передоплату або знято fee); NeedsApproval → `{"status":"pending_approval","approval_id","reason","instruction":"Повідом клієнту, що уточнюєш в адміністратора, і заверши відповідь."}`; Forbidden → `{"status":"forbidden","reason"}`. `apply_goodwill_exception` при Allow: `ds.add_goodwill(...)` і позначає в ctx `goodwill_applied.add(booking_id)`; `reschedule_booking`/`cancel_booking` передають `forfeit_prepayment = is_late_change(...) and booking_id not in ctx.goodwill_applied`. `show_card(card: dict)` емітить `card` подію, повертає `{"status":"shown"}`. Кожен tool емітить `tool_call` (payload `name, args, decision`) і `tool_result`.

- [ ] **Step 1: Write failing tests** (фікстура `ctx_lumen_olena`, `ctx_lumen_max`, `ctx_denta_petro`):

```python
def test_registry_has_10_tools_with_schemas(reg):
    names = {d["name"] for d in reg.declarations()}
    assert names == {"get_client_profile","get_booking","find_slots","reschedule_booking","cancel_booking","refund_prepayment","apply_goodwill_exception","waive_no_show_fee","escalate_to_human","show_card"}
def test_get_client_profile_returns_history(reg, ctx_lumen_olena):
    r = reg.call("get_client_profile", {}); assert r["visits_count"] == 12 and r["bookings"][0]["id"] == "b-olena-1"
def test_goodwill_allowed_then_late_reschedule_keeps_prepayment(reg, ctx_lumen_olena):
    assert reg.call("apply_goodwill_exception", {"booking_id":"b-olena-1","reason":"хвороба"})["status"] == "done"
    r = reg.call("reschedule_booking", {"booking_id":"b-olena-1","start": iso(NOW + timedelta(days=2, hours=2)),"reason":"хвороба"})
    assert r["status"] == "done" and r["booking"]["prepayment"]["status"] == "held" and r["saved_uah"] == 500
def test_late_reschedule_without_goodwill_forfeits(reg, ctx_lumen_max):
    r = reg.call("reschedule_booking", {"booking_id":"b-max-1","start": iso(NOW + timedelta(days=2, hours=2)),"reason":"x"})
    assert r["booking"]["prepayment"]["status"] == "forfeited"
def test_goodwill_for_max_creates_approval_and_does_not_apply(reg, ctx_lumen_max):
    r = reg.call("apply_goodwill_exception", {"booking_id":"b-max-1","reason":"x"})
    assert r["status"] == "pending_approval"
    assert ctx_lumen_max.approvals.pending("lumen")[0].tool == "apply_goodwill_exception"
    assert ctx_lumen_max.ds.get_client("lumen","max").goodwill_exceptions == []
def test_forbidden_waive_on_denta(reg, ctx_denta_anna):
    assert reg.call("waive_no_show_fee", {"booking_id":"b-anna-1","reason":"x"})["status"] == "forbidden"
def test_data_error_surfaces_as_error(reg, ctx_lumen_olena):
    assert reg.call("refund_prepayment", {"booking_id":"b-olena-1","amount":900,"reason":"x"})["error"] == "validation"
def test_unknown_tool_and_bad_args(reg, ctx_lumen_olena):
    assert reg.call("nope", {})["error"] == "unknown_tool"
    assert reg.call("get_booking", {"wrong": 1})["error"] == "validation"
def test_show_card_emits_event(reg, ctx_lumen_olena):
    reg.call("show_card", {"card": {"type":"slots","title":"t","options":[]}})
    assert ctx_lumen_olena.events.since("s1")[-1].type == "card"
def test_tool_call_events_emitted(reg, ctx_lumen_olena):
    reg.call("get_booking", {"booking_id":"b-olena-1"})
    types = [e.type for e in ctx_lumen_olena.events.since("s1")]
    assert types[-2:] == ["tool_call","tool_result"]
```

- [ ] **Step 2: Run, fail.** **Step 3: Implement `agent/context.py`, `agent/tools.py`.** У conftest: фікстура `reg = default_registry()`, `iso(dt) -> str`, фікстури `ctx_lumen_olena`, `ctx_lumen_max`, `ctx_denta_petro`, `ctx_denta_anna` — кожна створює `SessionCtx(session_id="s1", ...)` зі свіжими `EventLog`, `ApprovalStore`, `ds` і активує через `use(ctx)` на час тесту. `SessionCtx` має поле `goodwill_applied: set[str]` (default empty). Докстрінги tools українською, параметри: `booking_id: str`, `start: str` (ISO), `staff_id: str | None`, `reason: str`, `amount: int`, `service_id: str`, `from_date: str`, `to_date: str`, `summary: str`, `priority: str`, `card: dict`. Серіалізація pydantic через `model_dump(mode="json")`.
- [ ] **Step 4: Run, pass.** **Step 5: Commit** — `git commit -m "feat(agent): tools with policy gating and approvals"`

---

### Task 5: LLM adapter (Gemini) + FakeClient

**Files:**
- Create: `agent/llm.py`
- Test: `tests/test_llm.py`

**Interfaces:**
- Produces: `Part = TextPart(text) | CallPart(name, args: dict) | ResultPart(name, response: dict)`; `Msg(role: Literal["user","model","tool"], parts: list[Part])`; `class LLMClient(Protocol): def generate(self, system: str, history: list[Msg], tools: list[dict]) -> Msg`; `class FakeClient(LLMClient)`: `__init__(self, script: list[Msg])` повертає відповіді по черзі, `calls: list[dict]` фіксує вхід; `class GeminiClient(LLMClient)`: `__init__(self, model: str, api_key: str, client=None)` (інжект для тестів), `generate(...)` конвертує `Msg`→`google.genai.types.Content` (`user`→role `user`, `model`→`model`, `tool`→role `user` з `Part.from_function_response`), `tools`→`types.Tool(function_declarations=[...])`, `config=types.GenerateContentConfig(system_instruction=system, tools=[...], automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True), temperature=0.3)`; відповідь → `Msg(role="model")` з `TextPart` для `part.text` і `CallPart` для `part.function_call`. Якщо env `AGENT_SYSTEM_AS_PREFIX=1`, system не передається в config, а префіксується до першого user-повідомлення як `"[Інструкції]\n...\n\n[Повідомлення клієнта]\n"`. `make_client() -> LLMClient` читає `AGENT_PROVIDER`, `AGENT_MODEL` (default `gemma-4-31b-it`), `GEMINI_API_KEY` (через `python-dotenv`).

- [ ] **Step 1: Write failing tests**: `test_fake_client_returns_script_in_order`; `test_gemini_converts_history_and_parses_function_call` (підмінний `client` із `models.generate_content` → об'єкт з `candidates[0].content.parts=[SimpleNamespace(text="думаю", function_call=None), SimpleNamespace(text=None, function_call=SimpleNamespace(name="get_booking", args={"booking_id":"b-olena-1"}))]`; перевірити, що в `generate_content` передано `config.automatic_function_calling.disable is True` і `contents[-1].role == "user"` для tool-msg, і що результат має `[TextPart("думаю"), CallPart("get_booking", {...})]`); `test_system_as_prefix_env` (з env=1 → `config.system_instruction is None`, перший `contents[0].parts[0].text` починається з `[Інструкції]`).
- [ ] **Step 2: Run, fail.** **Step 3: Implement.** **Step 4: Run, pass.**
- [ ] **Step 5: Commit** — `git commit -m "feat(agent): LLM adapter with Gemini client and fake"`

---

### Task 6: Agent loop, system prompt, Session

**Files:**
- Create: `agent/agent.py`
- Test: `tests/test_agent.py`

**Interfaces:**
- Consumes: Task 1–5.
- Produces: `build_system_prompt(tenant: Tenant, client: Client, now: datetime) -> str` (секції: роль і принципи; "Правила бізнесу" = `rules_text` дослівно + таблиця `agent_permissions` людською мовою + "текст уточнює, але не дає прав понад ворота"; "Клієнт" = ім'я, візити, неявки, винятки; "Поточний час"; "Картки" = коли викликати `show_card` з типами `slots|booking_summary|decision`; "Правило апруву" = після `pending_approval` повідом клієнту й заверши; "Перед кожним викликом tool напиши одне коротке речення, що і чому робиш"); `run_loop(llm: LLMClient, system: str, history: list[Msg], registry: ToolRegistry, ctx: SessionCtx, max_iter: int = 8) -> list[Msg]` (додає model/tool повідомлення в history, емітить `thinking` для тексту перед CallPart, `assistant_message` для фінального тексту, `error` при `max_iter`; повертає нову history); `class Session`: `__init__(id, tenant_id, client_id, channel, ds, events, approvals, llm, registry, now_fn)`; публічні атрибути `id, tenant_id, client_id, channel, ds, events, approvals, ctx: SessionCtx, history: list[Msg], system: str`; `send(text) -> str` (емітить `user_message`, викликає loop, повертає фінальний текст), `resume_after_approval(approval: Approval, result: dict) -> str` (додає user-msg `"[SYSTEM] Апрув {id}: {схвалено|відхилено} ({by}). Нотатка: {note}. Результат дії: {json}"`, запускає loop); `execute_approved(approval, ctx) -> dict` виконує underlying дію напряму через `ds` (мапа tool→метод: `apply_goodwill_exception`→`add_goodwill` + позначка `goodwill_applied`; `refund_prepayment`→`refund`; `cancel_booking`→`cancel`; `waive_no_show_fee`→`waive_no_show`; `reschedule_booking`→`reschedule`), `by=f"human:{decided_by}"`.

- [ ] **Step 1: Write failing tests** (усе з `FakeClient`):

```python
def test_system_prompt_contains_rules_and_client(ds):
    p = build_system_prompt(ds.get_tenant("lumen"), ds.get_client("lumen","olena"), NOW)
    assert "24 годин" in p and "Олена" in p and "12" in p and "show_card" in p
def test_loop_executes_tool_and_returns_text(sess_factory):
    fake = FakeClient([Msg("model",[TextPart("Перевіряю бронювання."), CallPart("get_booking",{"booking_id":"b-olena-1"})]),
                       Msg("model",[TextPart("Ваш запис завтра о 10:00.")])])
    s = sess_factory("lumen","olena", fake)
    assert s.send("коли мій запис?") == "Ваш запис завтра о 10:00."
    types = [e.type for e in s.events.since(s.id)]
    assert types == ["user_message","thinking","tool_call","tool_result","assistant_message"]
    assert fake.calls[1]["history"][-1].role == "tool"
def test_loop_stops_at_max_iter_with_error_event(sess_factory):
    fake = FakeClient([Msg("model",[CallPart("get_booking",{"booking_id":"b-olena-1"})])]*9)
    s = sess_factory("lumen","olena", fake); s.send("x")
    assert s.events.since(s.id)[-1].type == "error"
def test_unknown_tool_does_not_crash(sess_factory):
    fake = FakeClient([Msg("model",[CallPart("nope",{})]), Msg("model",[TextPart("ok")])])
    assert sess_factory("lumen","olena", fake).send("x") == "ok"
def test_resume_after_approval_executes_and_continues(sess_factory):
    fake = FakeClient([Msg("model",[CallPart("apply_goodwill_exception",{"booking_id":"b-max-1","reason":"x"})]),
                       Msg("model",[TextPart("Уточню в адміністратора.")]),
                       Msg("model",[TextPart("Адміністратор погодив, переношу.")])])
    s = sess_factory("lumen","max", fake); s.send("дитина захворіла")
    ap = s.approvals.pending("lumen")[0]
    result = execute_approved(ap, s.ctx); ap = s.approvals.decide(ap.id, True, "Оля", "ок")
    assert s.resume_after_approval(ap, result) == "Адміністратор погодив, переношу."
    assert s.ds.get_client("lumen","max").goodwill_exceptions[-1].booking_id == "b-max-1"
    assert "[SYSTEM] Апрув" in fake.calls[2]["history"][-1].parts[0].text
```

- [ ] **Step 2: Run, fail.** **Step 3: Implement `agent/agent.py`.** У conftest: фікстура `sess_factory(tenant_id, client_id, llm) -> Session` зі свіжими `ds/events/approvals`, `registry=default_registry()`, `now_fn=lambda: NOW`, `id="s-test"`. **Step 4: Run, pass.**
- [ ] **Step 5: Commit** — `git commit -m "feat(agent): loop, system prompt, session, approval resume"`

---

### Task 7: FastAPI API

**Files:**
- Create: `agent/main.py`
- Test: `tests/test_api.py`

**Interfaces:**
- Consumes: Task 1–6.
- Produces: `create_app(ds=None, llm=None, now_fn=None) -> FastAPI` (дефолти: `MemoryDataSource.from_file("agent/seed.json", now)`, `make_client()`); глобальні `EventLog`, `ApprovalStore`, `dict[str, Session]`. Ендпоінти зі спеки розділ 8: `POST /sessions {tenant_id, client_id, channel}` → `{session_id}` (404 якщо тенант/клієнт невідомі); `POST /sessions/{id}/messages {text}` → `{reply}` (409 якщо сесія зайнята: `threading.Lock` на сесію, `run_in_threadpool`); `GET /sessions/{id}/events?after=` → `{events:[...]}`; `GET /tenants/{id}/approvals?status=pending`; `POST /approvals/{id}/decide {approve, note, by}` → `{approval, reply}` (409 `already_decided`; при approve: `execute_approved` → якщо `DataError` → approval лишається approved, `result={"error":...}`; потім `resume_after_approval`); `GET /tenants/{id}/metrics`; `GET /tenants/{id}` (тенант + клієнти для селектора UI); `app.mount("/", StaticFiles(directory="web", html=True))` останнім; CORS `*`. `app = create_app()` на рівні модуля.

- [ ] **Step 1: Write failing tests** (TestClient, `FakeClient` інжект): `test_create_session_and_message_flow` (fake повертає один текст; `events` містить `user_message` і `assistant_message`), `test_unknown_client_404`, `test_approval_decide_flow` (сценарій B як у Task 6, через HTTP; після decide `pending` порожній, `metrics.approvals_approved == 1`, reply непорожній), `test_decide_twice_409`, `test_metrics_shape` (усі ключі зі списку Task 3), `test_tenant_endpoint_lists_clients`.
- [ ] **Step 2: Run, fail.** **Step 3: Implement.** **Step 4: Run, pass.**
- [ ] **Step 5: Commit** — `git commit -m "feat(agent): FastAPI endpoints"`

---

### Task 8: Web UI (two panes)

**Files:**
- Create: `web/index.html`, `web/app.js`, `web/style.css`

**Interfaces:**
- Consumes: HTTP API Task 7.

- [ ] **Step 1: Build `web/index.html`**: шапка з селекторами тенанта і клієнта (`GET /tenants/lumen`, `GET /tenants/denta`), кнопка "Нова сесія" (`POST /sessions`). Ліва панель "Чат клієнта": список повідомлень, поле вводу, картки: `slots` → кнопки, клік шле `"Обираю слот {start} ({staff_name})"`; `booking_summary` → таблиця + таймлайн; `decision` → блок із outcome і списком reasoning. Права панель "Copilot": стрічка подій (`thinking` курсивом, `tool_call` як `name(args) → decision`, `tool_result` згорнуто, `error` червоним), блок "Апруви" з картками (tool, args, reason, поле нотатки, кнопки Схвалити/Відхилити → `POST /approvals/{id}/decide` з `by: "Адміністратор"`), блок "Метрики" (`GET /tenants/{id}/metrics` кожні 3 с). Полінг `GET /sessions/{id}/events?after=` кожні 700 мс. Без фреймворків, темна тема, дві колонки 55/45.
- [ ] **Step 2: Verify manually**: `uv run uvicorn agent.main:app --port 8000`, відкрити `http://localhost:8000/`, створити сесію, надіслати текст з `AGENT_PROVIDER=fake` (додати в `make_client()`: `fake` → `FakeClient` з одним текстом "Тестова відповідь") → повідомлення і події з'являються в обох панелях. Expected: без помилок у консолі браузера.
- [ ] **Step 3: Commit** — `git commit -m "feat(web): customer chat + copilot panes"`

---

### Task 9: Live smoke with Gemma 4 + feature docs

**Files:**
- Create: `scripts/smoke.py`, `.env.example`
- Modify: `docs/features/support-agent/*` (10 файлів), `docs/WORKLOG.md`, `README.md`

- [ ] **Step 1: `scripts/smoke.py`**: створює `MemoryDataSource`, `make_client()`, сесію `lumen/olena`, шле "Вибачте, в мене дитина захворіла, я не зможу завтра на 10, можна щось зробити?", друкує всі події і відповідь; потім сесію `lumen/max` з тим самим текстом і друкує pending approvals. Аргумент `--scenario A|B|C`.
- [ ] **Step 2: Run** `uv run python scripts/smoke.py --scenario A` з `GEMINI_API_KEY`. Expected: агент викликає `get_client_profile`, `apply_goodwill_exception` (done), `find_slots`, `show_card` (slots), текст українською. Якщо модель не викликає tools або ламає JSON: спробувати `AGENT_SYSTEM_AS_PREFIX=1`, потім `AGENT_MODEL=gemini-2.5-flash`; зафіксувати робочу конфігурацію в `.env.example` і `known-gotchas.md`.
- [ ] **Step 3: Fill `docs/features/support-agent/`** усі 10 файлів по факту коду (entry-points.json: HTTP-ендпоінти і tools; integration-points: env, порти, контракт DataSource ↔ MCP/HTTP тіммейта).
- [ ] **Step 4: README.md**: запуск за 5 команд, env, демо-сценарії.
- [ ] **Step 5: Commit** — `git commit -m "docs: feature docs, smoke script, README"`

---

### Task 10 (stretch): HttpDataSource / McpDataSource для платформи тіммейта

**Files:** Modify `agent/datasource.py`; Test `tests/test_http_datasource.py` (httpx `MockTransport`).
- `HttpDataSource(base_url)`: методи 1:1 до REST зі спеки апки; 4xx → `DataError(code=body["error"])`.
- `McpDataSource(url)` (якщо тіммейт віддає MCP): пакет `mcp`, streamable HTTP, `tools/call` з іменами зі спеки апки розділ 4; результат `{"error": code}` → `DataError`.
- `make_datasource()`: `APP_MCP_URL` → Mcp, інакше `APP_API_URL` → Http, інакше Memory. Commit `feat(agent): HttpDataSource/McpDataSource`.

### Task 11 (stretch): Voice webhook

**Files:** Modify `agent/main.py`.
- `POST /voice/tools/{tool_name} {tenant_id, phone, args}` → знайти клієнта за телефоном, знайти/створити сесію каналу `voice`, `registry.call` у `SessionCtx` → JSON. Тест: виклик `get_client_profile` для телефону Олени повертає `visits_count == 12`. Commit `feat(agent): voice tool webhook`.
