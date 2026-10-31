# Support-агент

Спека: `docs/superpowers/specs/2026-10-31-support-agent-design.md`. План: `docs/superpowers/plans/2026-10-31-support-agent.md`. Статус: MVP реалізовано (2026-10-31), 218 тестів; живий прогін на Claude Sonnet 5.5 пройшов (сценарії A і C), інтеграція з платформою тіммейта в роботі.

## Що це
AI-агент підтримки для платформи бронювань (мульти-тенант: салони, клініки). Агент не лише відповідає, а вирішує звернення клієнта: читає профіль і правила тенанта, викликає tools, виконує дозволені дії сам, а ризикові віддає адміністратору на апрув. У відповідях показує інтерактивні картки (слоти, підсумок рішення). Support-людина бачить у copilot весь хід міркування і всі виклики tools.

## Ключові рішення
- Провайдери за `LLMClient` (`support-agent/agent/llm.py`, `AGENT_PROVIDER`): `anthropic` (Claude Sonnet 5.5, типовий воркер), `gemini` (Gemma 4 через Gemini API), `ollama`/`openai_compat` (локальна Gemma 4), `fake`. Рішення "Gemma 4 як головна модель" замінено (superseded); Gemma 4 відповідає на прості питання.
- Власний tool-loop (`run_loop`, `max_iter=8`), автоматичний function calling SDK вимкнено, щоб між викликом і дією стояв permission engine (розділ 4).
- Permission engine: чиста функція `decide()` у `support-agent/agent/policy.py` повертає `Allow | NeedsApproval | Forbidden`; `rules_text` власника лише уточнює, права дають лише ворота `agent_permissions`.
- Approval-флоу: `NeedsApproval` створює `Approval` у `ApprovalStore`, рішення адміна виконує `execute_approved` рівно один раз, потім `Session.resume_after_approval` повертає агента в розмову.
- Дані через протокол `DataSource`; `MemoryDataSource` (seed `support-agent/agent/seed.json`) і `HttpDataSource` до платформи тіммейта (`APP_API_URL`, `make_datasource`; в роботі). `McpDataSource` не реалізовано, замінено HTTP.
- 10 tools: 3 read, 6 write, 1 ui (`show_card`); картки: `slots`, `booking_summary`, `decision` — pydantic-моделі в `support-agent/agent/cards.py`, `show_card` валідує картку через `parse_card` (некоректна дає `validation`), а в `card`-подію йде провалідований dump. JSON-схема аргументу `card` для Gemini генерується з цих моделей.
- Події (`EventLog`) живлять фронт полінгом; метрики рахуються з подій і апрувів.
- Фронт без фреймворку (`support-agent/web/`), роздається FastAPI з `/`.
- Відхилення від спеки: немає prompt caching; `McpDataSource` замінено `HttpDataSource`; голос (`voice.py`) і `POST /chat` додано понад початкову спеку. У `cards.py` одна об'єднана схема `card` (union полів трьох типів, `required: [type]`) замість `anyOf`, бо Gemini Schema приймає лише `type/properties/required/items/enum/nullable/description`; суворість по типу перевіряє `parse_card`. У слот-опції додано `staff_id` (потрібен для `reschedule_booking`).

## Оркестратор (Claude Sonnet + LangChain), відповідач Gemma 4
`support-agent/agent/orchestrator.py`: Claude Sonnet (`claude-sonnet-5-5`) тріажить кожне повідомлення (intent, urgency, tone, route) і веде маршрут; Gemma 4 (`Answerer`) відповідає лише на дуже прості інформаційні питання (`answer`); усе, що стосується дій, іде в основний цикл (воркер, Sonnet). Маршрути: `answer`, `escalate` (підказка викликати `escalate_to_human`), `agent` (звичайний цикл + підказка в системному промпті). Якщо відповідача немає або він не відповів, маршрут стає `agent` (`fallback: answerer_unavailable` у `triage`). Правила маршрутів примусово в коді: зміни/скасування/повернення завжди `agent`. Безпека не змінюється: усі дії лише через tools/policy/approvals. Налаштування: `ORCHESTRATOR*`, `ANSWERER*`.

## Емоції та розмовна українська
`agent/lingo.py`: глосарій суржику/галицької говірки/чат-сленгу (`GLOSSARY`), `EMOTIONS`, `EMOTION_GUIDE`, `REGISTER_RULE`. Тріаж додатково повертає `emotion`, `intensity` (1-3), `register` (formal/casual/slang), `normalized` (суть літературною мовою); `tone` виводиться з емоції. Відсутні поля мають типові значення (calm, 1, formal, ""). Воркер отримує розділи "Мова клієнта" та "Емоції" й рядок "Оркестратор: емоція … регістр … суть …" у системному промпті ходу. `angry` + intensity 3 + `complaint` примусово дає `escalate`. Подія `triage` містить нові поля; метрики мають `emotions`; copilot показує емодзі емоції та `normalized`.

## Провайдери
| Роль | Провайдер / модель | Env |
|---|---|---|
| Воркер (дії) | `anthropic` Claude Sonnet 5.5 (типово), `gemini` Gemma 4, `ollama`/`openai_compat` локальна Gemma 4, `fake` | `AGENT_PROVIDER`, `AGENT_MODEL` |
| Оркестратор (тріаж) | Claude Sonnet 5.5 (LangChain); альтернативи `gemini`, `ollama` | `ORCHESTRATOR_PROVIDER`, `ORCHESTRATOR_MODEL` |
| Відповідач простих питань | Gemma 4 (Ollama `gemma4:12b` або Gemini API `gemma-4-31b-it`) | `ANSWERER_PROVIDER`, `ANSWERER_MODEL` |

## Канали та інтеграції
- Чат і copilot: `support-agent/web/`. Голос: Vapi webhook `POST /voice/tools` (`voice.py`). Чат сайту тіммейта: `POST /chat` (`chat_webhook.py`, в роботі). Дані платформи: `HttpDataSource` на :8001 (в роботі).
