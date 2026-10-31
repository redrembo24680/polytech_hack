# Флоу крок за кроком

1. Користувач у `support-agent/web/` обирає тенанта і клієнта, натискає "Нова сесія": `POST /sessions` (`support-agent/agent/main.py`, `create_session`) створює `Session` з `default_registry()` і LLM-клієнтом (`make_client()` ліниво, при першій сесії).
2. Клієнт пише повідомлення: `POST /sessions/{id}/messages` бере лок сесії (зайнято: 409 `busy`) і виконує `Session.send` у threadpool.
3. `Session.send` оновлює `now`, перебудовує системний промпт (`build_system_prompt`: політика, дозволи, профіль клієнта, час), емітить `user_message`.
4. `run_loop` викликає `llm.generate(system, history, tool_declarations)`. Помилка LLM дає подію `error` і дружню відповідь.
5. Якщо в відповіді є `CallPart`: текст перед першим викликом емітиться як `thinking`; кожен виклик іде в `ToolRegistry.call`.
6. `ToolRegistry.call` відкидає `null` у необов'язкових аргументах, валідує аргументи, для write-tools під `WRITE_LOCK` викликає `policy.decide`, емітить `tool_call` (з `decision`; `noop` для повторного goodwill), виконує за рішенням і емітить `tool_result` (для `show_card` ще `card` з провалідованою карткою).
7. Результати tools додаються в історію як повідомлення `tool`, цикл повторюється до відповіді без викликів (ліміт 8 кроків) і емітить `assistant_message`.
8. Якщо policy дала `NeedsApproval`: `ApprovalStore.create`, подія `approval_created`, tool повертає `pending_approval`, агент завершує хід.
9. Фронт кожні 700 мс опитує `GET /sessions/{id}/events?after=`, а copilot кожні 1500 мс опитує `GET /tenants/{id}/approvals?status=pending` і показує апрув із кнопками.
10. Адмін натискає "Схвалити": `POST /approvals/{id}/decide` викликає `ApprovalStore.decide` (повторне рішення: 409 `already_decided`).
11. `finish` під локом сесії викликає `execute_approved` (DataSource з `by="human:<ім'я>"`), потім `Session.resume_after_approval` додає `[SYSTEM]`-повідомлення, емітить `approval_decided` і агент відповідає клієнту.
12. Фронт показує відповідь, картки і оновлені метрики (`GET /tenants/{id}/metrics`).

Без HTTP той самий шлях проходить `support-agent/scripts/smoke.py` (сценарій B вирішує апрув сам).

## Крок 0: тріаж оркестратором
Після `user_message` `Session.send` викликає `Orchestrator.triage` (Claude Sonnet через LangChain) і емітить `triage`. `answer`: `Answerer` (Gemma 4) формує відповідь, емітиться `assistant_message` з `model` відповідача, воркер не викликається; якщо відповідача немає або він не відповів, `triage` отримує `route: agent`, `fallback: answerer_unavailable`, і працює воркер. `escalate` або `agent`: далі звичайний цикл, а підказка (`hint`) додається в системний промпт розділом "Підказка оркестратора". Відповіді воркера теж мають `model`. Якщо оркестратор недоступний, `triage` відсутня і флоу без змін.

Тріаж також визначає емоцію (`emotion`, `intensity`), регістр і `normalized` (нейтральне переформулювання розмовного запиту); вони потрапляють у подію `triage` і в системний промпт воркера, який підлаштовує тон за `EMOTION_GUIDE`.
## Голосовий потік (Vapi)

Дзвінок -> Vapi STT -> LLM Vapi вирішує викликати tool -> `POST /voice/tools` -> клієнт за номером (`find_client_by_phone`) -> сесія `voice:{tenant}:{phone}` (канал voice, одна на номер) -> `registry.call` під тим самим policy/approval gating -> результат рядком у `results`. Write-дія, що потребує апруву, створює pending approval у copilot; агент каже, що перевірить в адміністратора й передзвонить. `show_card` надсилає картку SMS-повідомленням.

## Потік чату на платформі тіммейта
Клієнт відкриває віджет (http://localhost:3000/b/lumen/support), вводить ім'я та телефон, отримує «SMS» із 4-значним кодом (`POST /api/tenants/{t}/messages`, channel sms) і підтверджує його у стартовій формі (клієнтська демо-логіка) -> пише у віджет -> бекенд сайту `POST {AGENT_URL}/chat` з повною історією -> клієнт за `client_id` або `visitor_phone` (немає: просимо номер, сесії немає) -> сесія `chat:{tenant}:{conversation_id}` -> (лише якщо `VERIFY_PHONE=1`; у демо вимкнено, бо код підтверджується у стартовій формі сайту) якщо сесія не підтверджена: код з 4 цифр (`secrets`, `session.meta["otp"]`), `ds.send_message(..., "sms", ...)`, подія `sms`, відповідь «введіть код», LLM не викликається; правильний код -> обробка збереженого `pending_text` з префіксом «Дякую, номер підтверджено.»; 3 помилки -> новий код, ще 3 -> тікет `create_ticket` і відповідь про адміністратора; не-код -> нагадування і оновлення `pending_text` -> `Session.send(останнє повідомлення client)` під локом сесії -> картки цього ходу дописуються текстом (слоти: "Вільні варіанти: 1) 03.11 13:00 — Марія ... Напишіть номер варіанта.") -> `{"reply": ...}` -> сайт сам зберігає відповідь у розмові. Помилка агента: дружній текст із HTTP 200 і подія `error`. Апруви вирішує адмін у нашому copilot (http://localhost:8000); рішення в чат сайту автоматично не повертається.

## Після рішення адміністратора
`POST /approvals/{id}/decide` -> `finish()` під локом сесії: чат-сесія вебхука: `resume_after_approval` -> відповідь агента `POST .../support/conversations/{id}/reply` на сайт (клієнт бачить її в тому ж чаті). Голосова сесія: LLM не викликається (Vapi має власний цикл), текст детермінований ("Адміністратор схвалив/відхилив {дія}. {результат}") і йде SMS. Web-UI: відповідь лише в copilot.
