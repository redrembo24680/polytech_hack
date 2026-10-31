# Структура бекенду

```
agent/
  main.py        FastAPI: create_app(ds, llm, now_fn), ендпоінти, обробники помилок, роздача web/
  agent.py       build_system_prompt, run_loop, execute_approved, клас Session
  tools.py       ToolRegistry (валідація, policy gating, події), 10 tools, default_registry()
  policy.py      decide() -> Allow | NeedsApproval | Forbidden; is_late_change; goodwill_used_in_window
  datasource.py  Protocol DataSource, DataError(code, message), MemoryDataSource
  models.py      pydantic: Tenant, Policy, AgentPermissions, Client, Booking, Slot, Ticket
  events.py      EventLog, Event, ApprovalStore, Approval, metrics()
  context.py     SessionCtx (contextvar), use(ctx), get_ctx()
  llm.py         Msg/TextPart/CallPart/ResultPart, LLMClient, GeminiClient, FakeClient, make_client()
  seed.json      сід-дані: tenants lumen і denta з клієнтами, бронюваннями
scripts/smoke.py CLI-прогін сценаріїв
tests/           pytest
```

## Деталі
- `create_app` тримає стан у `app.state`: `ds`, `events`, `approvals`, `sessions`, `locks` (по локу на сесію). Модульний `app = create_app()` це точка для uvicorn.
- Помилки API плоскі: `{"error": код, "message": текст}` (`ApiError`, валідація 422, 404/405).
- `ToolRegistry.call` ніколи не кидає виняток: помилки стають `{"error": ...}` у `tool_result`. Аргументи перевіряються за схемою (`_validate_args`): невідомі ключі, відсутні обов'язкові, типи, ISO-дати.
- Write-tool виконується лише після `Allow`; бронювання перевіряється на власника (`_own_booking`), чужі повертають `not_found`.
- `Session` створює `SessionCtx` (tenant, client, `now`, ds, events, approvals, `goodwill_applied`) і передає tools через contextvar.
- Час усюди з таймзоною `Europe/Kyiv`, `now_fn` інжектиться (тести фіксують час).
