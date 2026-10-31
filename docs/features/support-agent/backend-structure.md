# Структура бекенду

```
support-agent/agent/
  main.py        FastAPI: create_app(ds, llm, now_fn), ендпоінти, обробники помилок, роздача web/
  agent.py       build_system_prompt, run_loop, execute_approved, клас Session
  tools.py       ToolRegistry (валідація, policy gating, події, WRITE_LOCK), 10 tools, default_registry()
  cards.py       SlotsCard/BookingSummaryCard/DecisionCard, parse_card(), card_json_schema() для Gemini
  policy.py      decide() -> Allow | NeedsApproval | Forbidden; is_late_change; goodwill_used_in_window
  datasource.py  Protocol DataSource, DataError, MemoryDataSource, HttpDataSource (в роботі), make_datasource()
  orchestrator.py Triage, Orchestrator (Claude Sonnet, LangChain), Answerer (Gemma 4), make_orchestrator()
  lingo.py       GLOSSARY, EMOTIONS, EMOTION_GUIDE, REGISTER_RULE
  voice.py       Vapi webhook: POST /voice/tools[/{tool_name}], сесії voice:{tenant}:{phone}
  chat_webhook.py POST /chat для сайту тіммейта (в роботі)
  sessions.py    get_or_create_session, ensure_backends (спільне для чату, голосу, вебхука)
  rules_text.py  RULES_TEXT_OVERRIDES для тенантів платформи (в роботі)
  models.py      pydantic: Tenant, Policy, AgentPermissions, Client, Booking, Slot, Ticket
  events.py      EventLog, Event, ApprovalStore, Approval, metrics()
  context.py     SessionCtx (contextvar), use(ctx), get_ctx()
  llm.py         Msg/TextPart/CallPart/ResultPart, LLMClient, GeminiClient, AnthropicClient, OpenAICompatClient, FakeClient, make_client()
  seed.json      сід-дані: tenants lumen і denta з клієнтами, бронюваннями
support-agent/scripts/smoke.py CLI-прогін сценаріїв
support-agent/tests/ pytest
```

## Деталі
- `create_app` тримає стан у `app.state`: `ds`, `events`, `approvals`, `sessions`, `locks` (по локу на сесію). Модульний `app = create_app()` це точка для uvicorn.
- Помилки API плоскі: `{"error": код, "message": текст}` (`ApiError`, валідація 422, 404/405).
- `ToolRegistry.call` ніколи не кидає виняток: помилки стають `{"error": ...}` у `tool_result`. Аргументи перевіряються за схемою (`_validate_args`): невідомі ключі, відсутні обов'язкові, типи, ISO-дати.
- Write-tool виконується лише після `Allow`; бронювання перевіряється на власника (`_own_booking`), чужі повертають `not_found`. Policy-рішення і виконання write-tools, а також `execute_approved`, ідуть під одним `agent.tools.WRITE_LOCK` (RLock), бо `MemoryDataSource` спільний для всіх сесій і потоків.
- Tools без аргументів не мають ключа `parameters` у декларації (Gemini відхиляє порожній OBJECT); `null` у необов'язкових аргументах відкидається до валідації; `start` без часового поясу отримує таймзону тенанта.
- Чи застосовано goodwill, визначається з даних (`client.goodwill_exceptions`) або з `SessionCtx.goodwill_applied`; повторний `apply_goodwill_exception` повертає `already_applied` без апруву і змін.
- `run_loop`: при помилці LLM / вичерпанні `max_iter` емітить `error`, а потім `assistant_message` із запасним текстом; порожня відповідь моделі замінюється на `EMPTY_REPLY_TEXT`. `GeminiClient` пропускає thought-частини, зберігає `thought_signature` у `CallPart.signature` і ретраїть 429/5xx (0,5/1/2 с).
- `Session` створює `SessionCtx` (tenant, client, `now`, ds, events, approvals, `goodwill_applied`) і передає tools через contextvar.
- Час усюди з таймзоною `Europe/Kyiv`, `now_fn` інжектиться (тести фіксують час). `MemoryDataSource(seed, now, now_fn)`: `now` будує демо-дані, `now_fn` використовується для перевірки "не в минулому", слотів і часу в історії.

- `support-agent/agent/orchestrator.py`: `Triage`, `Orchestrator` (LCEL: `ChatPromptTemplate | chat_model | JsonOutputParser`), `make_orchestrator()`. `Session` приймає `orchestrator`, `create_app(orchestrator=...)` створює його ліниво разом з `make_client()`. `EventType` має `triage`, `metrics()` повертає `intents`.
- Провайдери `make_client()` (`AGENT_PROVIDER`): `anthropic` (Sonnet 5.5), `gemini`, `ollama`/`openai_compat`, `fake`. Оркестратор: `ORCHESTRATOR_PROVIDER` anthropic|gemini|ollama; відповідач: `ANSWERER_PROVIDER` ollama|gemini.
- Нові ендпоінти: `GET /tenants`, `POST /voice/tools`, `POST /voice/tools/{tool_name}`, `POST /chat`. `make_datasource` обирає `HttpDataSource`, якщо задано `APP_API_URL`, інакше `MemoryDataSource`.
- Уточнення: стан з `git status` чистий, усі перелічені модулі закомічені; "в роботі" означає, що інтеграція з платформою тіммейта ще не перевірена наживо.
