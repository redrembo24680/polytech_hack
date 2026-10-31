# Support-агент

Спека: `docs/superpowers/specs/2026-10-31-support-agent-design.md`. План: `docs/superpowers/plans/2026-10-31-support-agent.md`. Статус: MVP реалізовано (2026-10-31), 137 тестів; live-прогін з Gemma 4 очікує `GEMINI_API_KEY`.

## Що це
AI-агент підтримки для платформи бронювань (мульти-тенант: салони, клініки). Агент не лише відповідає, а вирішує звернення клієнта: читає профіль і правила тенанта, викликає tools, виконує дозволені дії сам, а ризикові віддає адміністратору на апрув. У відповідях показує інтерактивні картки (слоти, підсумок рішення). Support-людина бачить у copilot весь хід міркування і всі виклики tools.

## Ключові рішення
- Провайдер Gemini API, модель Gemma 4 (`gemma-4-31b-it`), SDK `google-genai`; провайдер ховається за `LLMClient` (`support-agent/agent/llm.py`), є `FakeClient` для тестів і офлайн-демо (спека, розділ 6).
- Власний tool-loop (`run_loop`, `max_iter=8`), автоматичний function calling SDK вимкнено, щоб між викликом і дією стояв permission engine (розділ 4).
- Permission engine: чиста функція `decide()` у `support-agent/agent/policy.py` повертає `Allow | NeedsApproval | Forbidden`; `rules_text` власника лише уточнює, права дають лише ворота `agent_permissions`.
- Approval-флоу: `NeedsApproval` створює `Approval` у `ApprovalStore`, рішення адміна виконує `execute_approved` рівно один раз, потім `Session.resume_after_approval` повертає агента в розмову.
- Дані через протокол `DataSource`; реалізовано лише `MemoryDataSource` (seed `support-agent/agent/seed.json`). `McpDataSource`/`HttpDataSource` зі спеки ще не написані (розділ 3).
- 10 tools: 3 read, 6 write, 1 ui (`show_card`); картки: `slots`, `booking_summary`, `decision` — pydantic-моделі в `support-agent/agent/cards.py`, `show_card` валідує картку через `parse_card` (некоректна дає `validation`), а в `card`-подію йде провалідований dump. JSON-схема аргументу `card` для Gemini генерується з цих моделей.
- Події (`EventLog`) живлять фронт полінгом; метрики рахуються з подій і апрувів.
- Фронт без фреймворку (`support-agent/web/`), роздається FastAPI з `/`.
- Відхилення від спеки: немає `POST /voice/tools/...` (stretch), немає prompt caching. `support-agent/agent/cards.py` є, але одна об'єднана схема `card` (union полів трьох типів, `required: [type]`) замість `anyOf`, бо Gemini Schema приймає лише `type/properties/required/items/enum/nullable/description`; суворість по типу перевіряє `parse_card`. У слот-опції додано `staff_id` (потрібен для `reschedule_booking`).

## Оркестратор (Gemma 4 + LangChain)
`support-agent/agent/orchestrator.py`: Gemma 4 тріажить кожне повідомлення (intent, urgency, tone, route) і веде маршрут; воркер (Claude/інший провайдер) говорить і діє. Маршрути: `answer` (Gemma відповідає сама на просте питання), `escalate` (підказка викликати `escalate_to_human`), `agent` (звичайний цикл + підказка в системному промпті). Правила маршрутів примусово в коді: зміни/скасування/повернення завжди `agent`. Безпека не змінюється: усі дії лише через tools/policy/approvals. Налаштування: `ORCHESTRATOR`, `ORCHESTRATOR_MODEL`, `ORCHESTRATOR_BASE_URL`.
