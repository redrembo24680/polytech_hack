# Бізнес-контекст і правила

Спека: `docs/superpowers/specs/2026-10-31-support-agent-design.md`, розділи 1, 4, 10.

## Хто користувач і який біль
- Клієнт бізнесу-тенанта (салон Lumen Beauty, клініка DentaPlus) пише в чат: перенести, скасувати, повернути гроші.
- Адміністратор бізнесу витрачає час на типові звернення і має приймати лише справді спірні рішення.
- Агент закриває типові звернення сам у межах прав, решту готує для людини з причиною і рекомендацією.

## Правила тенанта (два шари)
1. `agent_permissions` — жорсткі ворота, перевіряє код (`agent/policy.py`). Режими: `auto` / `approval` / `forbidden`; для refund ще `auto_under_limit` з `refund_auto_limit`.
2. `rules_text` — вільний текст власника, потрапляє в системний промпт дослівно. Він уточнює поведінку моделі, але не розширює права.

Lumen Beauty (seed): reschedule і cancel `auto`; refund до 500 грн `auto`, більше через апрув; goodwill `auto` (1 виняток на клієнта за 180 днів, лише без неявок); `waive_no_show_fee` через апрув; вікно скасування 24 год, пізня зміна спалює передоплату; штраф за неявку 300 грн.

## Пізня зміна і виняток з доброї волі
- `is_late_change`: час до візиту менше `cancellation_window_hours` і `late_change_forfeits_prepayment`. Тоді cancel/reschedule передають `forfeit_prepayment=True`.
- Якщо для бронювання застосовано `apply_goodwill_exception`, передоплата зберігається, а `saved_uah` потрапляє в метрику `money_saved_uah`.
- `waive_no_show_fee` теж рахує `saved_uah` (розмір штрафу тенанта).

## Рішення policy
- `Allow` — агент виконує дію сам, у `tool_result` є `decision_reason`.
- `NeedsApproval` — створюється апрув, агент повідомляє клієнту, що уточнює в адміністратора, і завершує хід.
- `Forbidden` — агент пояснює і пропонує альтернативу або ескалує.
- `escalate` дозволено завжди.
- Refund із сумою поза `1..prepayment.amount` — помилка даних `validation`, а не апрув.

## Демо-сценарії (acceptance)
- A. lumen/olena (12 візитів, 0 неявок): goodwill `Allow`, пошук слотів, картка `slots`, перенесення без втрати передоплати.
- B. lumen/max (2 неявки): goodwill `NeedsApproval`, адмін схвалює в copilot, агент переносить зі збереженням передоплати.
- C. denta/petro: "скасувати і повернути гроші", агент створює апруви й чекає людину.

## Критерії оцінювання хакатону
Operational Impact, Innovation, Use of AI, Reasoning & Context Handling, Presentation & Demo. Челенджі: "Best Use of Gemma 4", "Best Open-Source AI Project".
