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
