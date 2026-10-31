# Support-агент

Спека: `docs/superpowers/specs/2026-10-31-support-agent-design.md`. План: `docs/superpowers/plans/2026-10-31-support-agent.md`. Статус: MVP реалізовано (2026-10-31), 96 тестів; live-прогін з Gemma 4 очікує `GEMINI_API_KEY`.

## Що це
AI-агент підтримки для платформи бронювань (мульти-тенант: салони, клініки). Агент не лише відповідає, а вирішує звернення клієнта: читає профіль і правила тенанта, викликає tools, виконує дозволені дії сам, а ризикові віддає адміністратору на апрув. У відповідях показує інтерактивні картки (слоти, підсумок рішення). Support-людина бачить у copilot весь хід міркування і всі виклики tools.

## Ключові рішення
- Провайдер Gemini API, модель Gemma 4 (`gemma-4-31b-it`), SDK `google-genai`; провайдер ховається за `LLMClient` (`agent/llm.py`), є `FakeClient` для тестів і офлайн-демо (спека, розділ 6).
- Власний tool-loop (`run_loop`, `max_iter=8`), автоматичний function calling SDK вимкнено, щоб між викликом і дією стояв permission engine (розділ 4).
- Permission engine: чиста функція `decide()` у `agent/policy.py` повертає `Allow | NeedsApproval | Forbidden`; `rules_text` власника лише уточнює, права дають лише ворота `agent_permissions`.
- Approval-флоу: `NeedsApproval` створює `Approval` у `ApprovalStore`, рішення адміна виконує `execute_approved` рівно один раз, потім `Session.resume_after_approval` повертає агента в розмову.
- Дані через протокол `DataSource`; реалізовано лише `MemoryDataSource` (seed `agent/seed.json`). `McpDataSource`/`HttpDataSource` зі спеки ще не написані (розділ 3).
- 10 tools: 3 read, 6 write, 1 ui (`show_card`); картки: `slots`, `booking_summary`, `decision`.
- Події (`EventLog`) живлять фронт полінгом; метрики рахуються з подій і апрувів.
- Фронт без фреймворку (`web/`), роздається FastAPI з `/`.
- Відхилення від спеки: немає `agent/cards.py` (картка це довільний `dict` у `show_card`), немає `POST /voice/tools/...` (stretch), немає prompt caching.
