# AI-агент підтримки для платформи бронювань

Агент, який не просто відповідає клієнтам, а вирішує їхні звернення: читає профіль клієнта і правила бізнесу, викликає tools (перенести, скасувати, повернути передоплату, виняток з доброї волі), а ризикові дії віддає адміністратору на апрув. У чаті показує інтерактивні картки (вільні слоти, підсумок рішення), а в copilot адміністратора видно весь хід міркування, виклики tools і метрики.

Проєкт зроблено для PolyTech Code Fest / Hacktoberfest Hack Day Lviv (трек "AI Customer Support Automation") і претендує на челенджі "Best Use of Gemma 4" (модель `gemma-4-31b-it` через Gemini API, нативний function calling, власний tool-loop з permission engine) та "Best Open-Source AI Project". Мульти-тенант: демо на салоні Lumen Beauty і клініці DentaPlus.

## Швидкий старт
```bash
cd support-agent   # усі команди виконуються з цієї папки
uv sync
cp .env.example .env   # вписати GEMINI_API_KEY (aistudio.google.com)
uv run uvicorn agent.main:app --port 8000
# відкрити http://localhost:8000
# в іншому терміналі: консольний прогін сценарію (A, B або C)
uv run python scripts/smoke.py --scenario A
```
Тести (з `support-agent/`): `uv run pytest -q`.

## Офлайн-демо
З папки `support-agent/`: `AGENT_PROVIDER=fake uv run uvicorn agent.main:app --port 8000` запускає UI і API без ключа та мережі. Fake-провайдер на кожне повідомлення повертає фіксований текст "Тестова відповідь" без tool-викликів: цього досить, щоб перевірити інтерфейс, але не сценарії.

## Змінні середовища
`GEMINI_API_KEY`, `ANTHROPIC_API_KEY`, `AGENT_PROVIDER` (`gemini` | `anthropic` | `ollama`/`openai_compat` | `fake`), `OPENAI_BASE_URL`, `OPENAI_API_KEY`, `AGENT_MODEL` (за замовчуванням `gemma-4-31b-it`), `AGENT_SYSTEM_AS_PREFIX=1`. Деталі в `.env.example`.

## Локальна модель через Ollama
Агент працює і з локальною моделлю через OpenAI-сумісний API, без ключа Gemini:
```bash
brew install ollama
ollama pull gemma4:<тег>   # потрібен Ollama >= 0.20; на 16 ГБ RAM лише e4b/12b
# у .env:
#   AGENT_PROVIDER=ollama
#   AGENT_MODEL=gemma4:<тег>
#   OPENAI_BASE_URL=http://localhost:11434/v1
uv run uvicorn agent.main:app --port 8000
```
Хід із кількома tools може тривати 30-60 с.

## Claude через Anthropic API
```bash
# у .env:
#   AGENT_PROVIDER=anthropic
#   ANTHROPIC_API_KEY=...
#   AGENT_MODEL=claude-sonnet-5-5   # за замовчуванням; за потреби claude-opus-5-5
uv run uvicorn agent.main:app --port 8000
```
Міркування моделі (thinking) зберігаються в історії й повертаються API без змін; клієнту вони не показуються.

## Демо-сценарії
- A. Олена (`lumen/olena`): "дитина захворіла, не зможу завтра на 10". Агент сам застосовує виняток з доброї волі, шукає слоти, показує картку, переносить без втрати передоплати.
- B. Максим (`lumen/max`, 2 неявки): той самий запит, виняток вимагає апруву. Адміністратор схвалює в copilot, агент переносить зі збереженням передоплати. У консолі: `--scenario B` схвалює автоматично.
- C. Петро (`denta/petro`): "скасувати запис і повернути гроші". Агент створює два апруви (спершу повернення, потім скасування) й чекає людину. Схвалювати треба спершу повернення.

## Структура репозиторію
```
support-agent/
  agent/     FastAPI, агент, tools, policy, events, DataSource, seed.json
  web/       чат клієнта + copilot (без фреймворку)
  scripts/   smoke.py
  tests/     pytest (без мережі)
../docs/       WORKLOG, specs, plans, features (в корені репо)
```

## Документація
- Спеки: `../docs/superpowers/specs/2026-10-31-support-agent-design.md`, `../docs/superpowers/specs/2026-10-31-booking-app-design.md`
- План: `../docs/superpowers/plans/2026-10-31-support-agent.md`
- Опис фічі за кодом: `../docs/features/support-agent/` (почати з `FEATURE.md`)
- Журнал робіт: `../docs/WORKLOG.md`

## Оркестратор на Gemma 4 (LangChain)
Gemma 4 (через LangChain: локальна Ollama `gemma4:12b` або Gemini API `gemma-4-31b-it` безкоштовно, `agent/orchestrator.py`) на кожне повідомлення клієнта робить тріаж: намір, терміновість, тон і маршрут. Основний агент (Claude або інший провайдер) лишається воркером і діє лише через tools/policy/approvals.
- `answer`: просте питання (`question`, терміновість до `normal`) Gemma відповідає сама, воркер не викликається.
- `escalate`: скарга в гніві або дуже термінова; воркер отримує підказку викликати `escalate_to_human`.
- `agent`: звичайний цикл; підказка оркестратора потрапляє в системний промпт цього ходу.
Дії зі зміни запису, скасування і повернення коштів завжди йдуть через `agent` (це примусово в коді, незалежно від відповіді моделі). Подія `triage` видна в copilot і в метриках (`intents`).
Налаштування: `ORCHESTRATOR=on|off`, `ORCHESTRATOR_PROVIDER=ollama|gemini` (за замовчуванням `ollama`), `ORCHESTRATOR_MODEL` (за замовчуванням `gemma4:12b`; для `gemini` `gemma-4-31b-it`, потрібен `GEMINI_API_KEY`, без ключа оркестратор вимкнено), `ORCHESTRATOR_BASE_URL` (лише ollama). Якщо Gemma недоступна, оркестратор мовчки пропускається.
