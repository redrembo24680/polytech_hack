# AI-агент підтримки для платформи бронювань

Агент, який не просто відповідає клієнтам, а вирішує їхні звернення: читає профіль клієнта і правила бізнесу, викликає tools (перенести, скасувати, повернути передоплату, виняток з доброї волі), а ризикові дії віддає адміністратору на апрув. У чаті показує інтерактивні картки (вільні слоти, підсумок рішення), а в copilot адміністратора видно весь хід міркування, виклики tools і метрики.

Проєкт зроблено для PolyTech Code Fest / Hacktoberfest Hack Day Lviv (трек "AI Customer Support Automation") і претендує на челенджі "Best Use of Gemma 4" (модель `gemma-4-31b-it` через Gemini API, нативний function calling, власний tool-loop з permission engine) та "Best Open-Source AI Project". Мульти-тенант: демо на салоні Lumen Beauty і клініці DentaPlus.

## Швидкий старт
```bash
uv sync
cp .env.example .env   # вписати GEMINI_API_KEY (aistudio.google.com)
uv run uvicorn agent.main:app --port 8000
# відкрити http://localhost:8000
uv run python scripts/smoke.py --scenario A   # консольний прогін сценарію
```
Тести: `uv run pytest -q`.

## Офлайн-демо
`AGENT_PROVIDER=fake uv run uvicorn agent.main:app --port 8000` запускає UI і API без ключа та мережі. Fake-провайдер повертає лише фіксований текст "Тестова відповідь" без tool-викликів: цього досить, щоб перевірити інтерфейс, але не сценарії.

## Змінні середовища
`GEMINI_API_KEY`, `AGENT_PROVIDER` (`gemini` | `fake`), `AGENT_MODEL` (за замовчуванням `gemma-4-31b-it`), `AGENT_SYSTEM_AS_PREFIX=1`. Деталі в `.env.example`.

## Демо-сценарії
- A. Олена (`lumen/olena`): "дитина захворіла, не зможу завтра на 10". Агент сам застосовує виняток з доброї волі, шукає слоти, показує картку, переносить без втрати передоплати.
- B. Максим (`lumen/max`, 2 неявки): той самий запит, виняток вимагає апруву. Адміністратор схвалює в copilot, агент переносить зі збереженням передоплати. У консолі: `--scenario B` схвалює автоматично.
- C. Петро (`denta/petro`): "скасувати запис і повернути гроші". Агент створює апруви й чекає людину.

## Структура репозиторію
```
agent/     FastAPI, агент, tools, policy, events, DataSource, seed.json
web/       чат клієнта + copilot (без фреймворку)
scripts/   smoke.py
tests/     pytest (без мережі)
docs/      WORKLOG, specs, plans, features
```

## Документація
- Спеки: `docs/superpowers/specs/2026-10-31-support-agent-design.md`, `docs/superpowers/specs/2026-10-31-booking-app-design.md`
- План: `docs/superpowers/plans/2026-10-31-support-agent.md`
- Опис фічі за кодом: `docs/features/support-agent/` (почати з `FEATURE.md`)
- Журнал робіт: `docs/WORKLOG.md`
