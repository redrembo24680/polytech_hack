# WORKLOG

## 2026-10-31
- Ініціалізовано репо, створено `CLAUDE.md` із правилами та конвенцією документації фіч
  (10 файлів на фічу, з лекції на хакатоні).
- Розібрано бриф хакатону (PDF). Ключове: AI має не відповідати, а **діяти**; критерії —
  Operational Impact, Innovation, Use of AI, Reasoning & Context, Demo.
- Дослідження ринку (веб): головні болі AI-підтримки —
  1) бот не розуміє запит / не вирішує складні кейси;
  2) неможливо дістатись людини, а при handoff губиться контекст розмови;
  3) бот "пояснює, але не діє" (dead end);
  4) ризик дій (помилкові refund/зміни акаунта) → потрібні permissions, staged autonomy,
     human review;
  5) ефективність міряють vendor-метриками, а не реальними CSAT/escalation/error rate.
- Розпочато brainstorming агента (architectural path). Спека ще не написана.
- Brainstorming (продовження): розглянуто 14 варіантів продукту-сцени. Обрано
  **мульти-тенант платформу бронювань** (B2B тенанти + B2C клієнти). Новизна в агенті:
  staged autonomy з політиками тенанта, approval cards, інтерактивні HTML-картки, copilot.
- Написано `docs/IDEA.md` для розмови з ментором. Відкрите рішення: де агент живе в MVP
  (два екрани / тільки чат / тільки copilot).
- Перевірено claude-mem: сервіс на 127.0.0.1:37701 здоровий (v15.7.0, initialized, mcpReady).
- Репо запушено в https://github.com/redrembo24680/polytech_hack (origin, гілка main).
- **Фідбек ментора:** ідея ок, але (1) великі бізнеси мають свої системи, малим не треба →
  цілитись у середні; (2) клієнти таких бізнесів здебільшого **дзвонять**, а не пишуть →
  потрібен голосовий канал. Ідея команди: голосовий агент + чат, оператори теж користуються
  агентом як copilot. Рішення щодо каналів поки відкрите.
- Рішення після ментора: ICP — середній бізнес без support-відділу; голос як канал (stretch).
  Бюджет: ~4 години. Стек: Python FastAPI агент + статичний фронт; тіммейт — будь-що з HTTP API.
- Написано дві спеки в `docs/superpowers/specs/`: `2026-10-31-booking-app-design.md` (контракт
  API і сід-дані для тіммейта) та `2026-10-31-support-agent-design.md` (агент).
- Блокер: на маку немає `ANTHROPIC_API_KEY` і `ant` CLI — потрібен ключ з console.anthropic.com.
- Узгоджено з баченням тіммейта (SaaS для бізнесів "за записом"): інтерфейс агент↔платформа =
  MCP (HTTP як запасний), правила = жорсткі `agent_permissions` + `rules_text` у промпті (без RAG),
  апруви й метрики живуть в агента, адмінка платформи їх читає. Спеки оновлено.
- Правило в CLAUDE.md: документація по кожній спеці ведеться в `docs/features/<фіча>/` з 10
  файлами (конвенція з лекції). Створено скелети для `support-agent` і `booking-platform`.
- Рішення: на свої гроші API не палимо; модель береться з токенів, які дає хакатон, або локальна.
- Встановлено DevRelay (MLH) v0.1.27: бінарник `~/.devrelay/bin/devrelay`, MCP `devrelay-gateway`
  зареєстровано в Claude Code (`~/.claude.json`), 10 skills у `~/.claude/skills`. Інсталер
  прочитано перед запуском (ставить бінарник, патчить MCP-конфіги, launchd-апдейтер, PATH).
  Потрібно: `devrelay login` у терміналі (браузер), перезапуск Claude Code. Далі через
  devrelay-offers дивимось, які API-кредити дає спонсор — від цього залежить SDK агента.
- Спека агента: додано межу `llm.py` (провайдер-агностичний tool-loop), провайдер і модель
  через env; фінальний вибір після перевірки спонсорських кредитів у DevRelay.
- DevRelay login ок (MLH: Hacktoberfest Hack Day Lviv, checked in; DEV: @stasblack31).
  Офферів/промокодів на івенті немає. Sponsor skill: DigitalOcean App Platform (Gradient AI).
  Челенджі івенту: **Best Use of Gemma 4** (відкрита модель через Gemini API) і **Best Open-Source
  AI Project**. Висновок: LLM — Gemma 4 / Gemini через безкоштовний тір Gemini API (або локально
  через Ollama), це закриває обидва додаткові призи. Перевіряємо tool calling у Gemma 4.
- Пошук Claude-кредитів: сторінка івенту MLH (партнер SKELAR) не згадує Anthropic/кредити, зате
  має Gemma-ресурси і воркшоп про local LLMs; DevRelay офферів нуль; у вебі нічого.
  **Рішення: Gemma 4 через Gemini API (free), SDK google-genai.** Спека агента оновлена.
- Рішення: DevRelay-кредити не чекаємо. Написано план `docs/superpowers/plans/2026-10-31-support-agent.md`
  (11 задач, 9 основних + 2 stretch). Виконання: subagent-driven-development, TDD, субагенти на Sonnet,
  оркестратор — ця сесія.
- Імплементація (гілка `feat/agent`, SDD: Sonnet-імплементер → Sonnet/Haiku-рев'юер на кожну задачу):
  - Task 1 ✅ models + seed.json + MemoryDataSource (19 тестів). Фікс: укр. повідомлення помилок, валідація reschedule.
  - Task 2 ✅ permission engine `policy.py` (40 тестів). Фікс: refund без суми → апрув, невідомий режим → ValueError (fail-closed).
  - Task 3 ✅ EventLog / ApprovalStore / metrics (46 тестів). Фікс: locks для threadpool.
  - Task 4 ✅ tools з policy gating (69 тестів). Фікс: перевірка власника бронювання, валідація аргументів per-tool, registry ніколи не кидає.
  - Task 5 ✅ LLM-адаптер: GeminiClient (google-genai 2.34) + FakeClient (74 тестів), без правок.
  - Task 6 ✅ agent loop + системний промпт + Session + execute_approved (83 тестів). Фікс: перевірка статусу апруву, never-raises.
  - Task 7 ✅ FastAPI: sessions, messages, events, approvals/decide, metrics, static web (96 тестів). Фікс: виконання апруву під локом сесії, плоскі помилки, контракт при збої після виконання.
  - Відкрито: dev-залежність `httpx2` (прибирає попередження Starlette у тестах) — інсталяцію субагенту заблокував permission-класифікатор; рішення за користувачем (`uv add --dev httpx2`).
- Task 9: smoke script, feature docs, README; live run: pending key
  - Task 8 ✅ web UI: чат клієнта з картками + copilot (події, апруви, метрики), без правок після рев'ю.
  - Task 9 ✅ smoke-скрипт, .env.example, 10 файлів `docs/features/support-agent/`, README. Живий прогін Gemma 4 відкладено до появи `GEMINI_API_KEY`.
  - Контракт апки доповнено: `list_clients`, `list_client_bookings`.
  - Фінальне рев'ю всієї гілки `feat/agent` запущено (Opus).
- Фікс-хвиля після фінального рев'ю гілки `feat/agent` (137 тестів):
  - Policy/дані: повернення по активному запису лише через апрув; forfeit лише з `held` (скасування після повернення лишає `refunded`); демо-бронювання відносно старту (`hours_ahead`), `MemoryDataSource(seed, now, now_fn)`; з rules_text Lumen прибрано "субота через адміністратора" (жодні ворота цього не виражають).
  - Tools: `agent/cards.py` (pydantic-картки, `parse_card`, Gemini-схема `card`), no-arg tools без `parameters`, `null` в optional відкидається, naive `start` → таймзона тенанта, goodwill з даних + `already_applied`, `WRITE_LOCK`; метрика `money_saved_uah` тепер читає `tool_result.result.saved_uah`.
  - Агент/LLM: клієнт бачить запасний текст при помилці LLM / max_iter / порожній відповіді; промпт з днем тижня, прикладами карток і правилами (goodwill перед зміною, refund перед cancel, id з профілю, без null, [SYSTEM]); thought-частини пропускаються, `thought_signature` зберігається; ретраї 429/5xx; fake-провайдер відповідає завжди; 503 без ключа.
  - Web/доки/smoke: захисний `renderCard`, `decided_by`; smoke підставляє реальний час запису, вибирає перший слот у A, схвалює апруви в B і C, без ключа → код 2.
- Агент перенесено в `support-agent/` (корінь репо: support-agent/, app/, docs/).
- Фінальне рев'ю (Opus): 4 Critical + 10 Important закрито однією хвилею фіксів (137 тестів), ре-рев'ю чистий.
  Ключові зміни: Gemini-сумісні схеми tools, валідація карток (`agent/cards.py`), фолбек-текст
  клієнту при помилках, таймзона для naive-часу, refund активного запису → апрув, forfeit лише
  для held, goodwill з даних, ретраї 429/5xx, write-lock, сід відносно старту сервера (`hours_ahead`).
- `feat/agent` злито в `main` (e5c8ec8). Структура: `support-agent/`, `app/` (тіммейт), `docs/`.
- **Відкрито:** живий прогін Gemma 4 (потрібен `GEMINI_API_KEY` у `support-agent/.env`), dev-залежність
  `httpx2`, stretch: HttpDataSource/McpDataSource до платформи тіммейта, голосовий webhook.
- Додано провайдер `openai_compat`/`ollama` (локальна Gemma 4 через Ollama).
