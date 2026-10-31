import json
from datetime import datetime

from agent.context import SessionCtx, use
from agent.datasource import DataError, DataSource
from agent.events import Approval, ApprovalStore, EventLog
from agent.llm import CallPart, LLMClient, Msg, ResultPart, TextPart
from agent.models import Client, Tenant
from agent.policy import is_late_change
from agent.tools import ToolRegistry

MAX_ITER_TEXT = "Вибачте, не вдалося завершити обробку. Передаю запит адміністратору."
LLM_ERROR_TEXT = "Вибачте, сталася технічна помилка. Спробуйте ще раз за хвилину."

_MODE = {"auto": "сам, без погодження", "approval": "лише через апрув адміністратора", "forbidden": "заборонено"}


def _permissions_text(p) -> str:
    refund = {
        "auto_under_limit": f"сам до {p.refund_auto_limit} грн, більше лише через апрув",
        "approval": _MODE["approval"],
        "forbidden": _MODE["forbidden"],
    }[p.refund]
    goodwill = _MODE[p.goodwill_exception]
    if p.goodwill_exception == "auto":
        goodwill += f" (не більше {p.goodwill_per_client_per_180d} за 180 днів"
        goodwill += ", лише клієнтам без неявок)" if p.goodwill_requires_zero_no_shows else ")"
    return "\n".join([
        f"- Перенесення: {_MODE[p.reschedule]}",
        f"- Скасування: {_MODE[p.cancel]}",
        f"- Повернення передоплати: {refund}",
        f"- Виняток з доброї волі: {goodwill}",
        f"- Зняття штрафу за неявку: {_MODE[p.waive_no_show_fee]}",
    ])


def build_system_prompt(tenant: Tenant, client: Client, now: datetime) -> str:
    policy = tenant.policy
    return f"""Ти — AI-агент підтримки закладу «{tenant.name}». Спілкуєшся з клієнтом українською: коротко, по-людськи, доброзичливо.
Принципи: спершу зрозумій мету клієнта, потім дізнайся дані через інструменти, і лише тоді дій. Ніколи не вигадуй дані (час, ціни, статуси). Ризиковані дії проходять через апрув адміністратора.

## Правила бізнесу
{policy.rules_text}

Що агенту дозволено самостійно:
{_permissions_text(policy.agent_permissions)}

Текст правил уточнює, але не дає прав понад ворота: те, що дозволено, вирішують лише інструменти.

## Клієнт
Ім'я: {client.name}. Візитів: {client.visits_count}. Неявок: {client.no_show_count}. Використано винятків з доброї волі: {len(client.goodwill_exceptions)}.

## Поточний час
{now.isoformat()}

## Картки
Викликай show_card з типом `slots`, `booking_summary` або `decision`. Після find_slots покажи картку `slots`. Після виконаної дії покажи картку `decision`.

## Правило апруву
Якщо інструмент повернув `pending_approval`, повідом клієнту, що уточнюєш в адміністратора, і заверши відповідь.

Перед кожним викликом tool напиши одне коротке речення, що і чому робиш.
"""


def run_loop(llm: LLMClient, system: str, history: list[Msg], registry: ToolRegistry,
             ctx: SessionCtx, max_iter: int = 8) -> list[Msg]:
    def emit(type_: str, payload: dict) -> None:
        ctx.events.emit(ctx.session_id, ctx.tenant_id, type_, payload)  # type: ignore[arg-type]

    for _ in range(max_iter):
        try:
            msg = llm.generate(system, history, registry.declarations())
        except Exception as e:
            emit("error", {"message": str(e)})
            history.append(Msg("model", [TextPart(LLM_ERROR_TEXT)]))
            return history
        history.append(msg)
        calls = [p for p in msg.parts if isinstance(p, CallPart)]
        if not calls:
            emit("assistant_message", {"text": "".join(p.text for p in msg.parts if isinstance(p, TextPart))})
            return history
        first = next(i for i, p in enumerate(msg.parts) if isinstance(p, CallPart))
        thought = "".join(p.text for p in msg.parts[:first] if isinstance(p, TextPart))
        if thought:
            emit("thinking", {"text": thought})
        with use(ctx):
            results = [ResultPart(c.name, registry.call(c.name, c.args)) for c in calls]
        history.append(Msg("tool", results))
    emit("error", {"message": "Перевищено ліміт кроків агента."})
    history.append(Msg("model", [TextPart(MAX_ITER_TEXT)]))
    return history


def _last_text(history: list[Msg]) -> str:
    return "".join(p.text for p in history[-1].parts if isinstance(p, TextPart))


def execute_approved(approval: Approval, ctx: SessionCtx) -> dict:
    by = f"human:{approval.decided_by or 'адміністратор'}"
    a, ds, t = approval.args, ctx.ds, approval.tenant_id
    try:
        if approval.tool in ("reschedule_booking", "cancel_booking"):
            b = ds.get_booking(t, a["booking_id"])
            forfeit = is_late_change(ds.get_tenant(t).policy, b, ctx.now) and a["booking_id"] not in ctx.goodwill_applied
            if approval.tool == "cancel_booking":
                out = ds.cancel(t, a["booking_id"], a["reason"], by, forfeit)
            else:
                out = ds.reschedule(t, a["booking_id"], datetime.fromisoformat(a["start"]),
                                    a.get("staff_id"), a["reason"], by, forfeit)
            return {"status": "done", "booking": out.model_dump(mode="json")}
        if approval.tool == "refund_prepayment":
            out = ds.refund(t, a["booking_id"], a["amount"], a["reason"], by)
        elif approval.tool == "waive_no_show_fee":
            out = ds.waive_no_show(t, a["booking_id"], a["reason"], by)
        elif approval.tool == "apply_goodwill_exception":
            out = ds.add_goodwill(t, ctx.client_id, a["booking_id"], a["reason"], by)
            ctx.goodwill_applied.add(a["booking_id"])
            return {"status": "done", "client": out.model_dump(mode="json")}
        else:
            return {"error": "unknown_tool"}
        return {"status": "done", "booking": out.model_dump(mode="json")}
    except DataError as e:
        return {"error": e.code, "message": e.message}


class Session:
    def __init__(self, id: str, tenant_id: str, client_id: str, channel: str, ds: DataSource,
                 events: EventLog, approvals: ApprovalStore, llm: LLMClient,
                 registry: ToolRegistry, now_fn):
        self.id, self.tenant_id, self.client_id, self.channel = id, tenant_id, client_id, channel
        self.ds, self.events, self.approvals = ds, events, approvals
        self.llm, self.registry, self._now_fn = llm, registry, now_fn
        self.history: list[Msg] = []
        self.ctx = SessionCtx(id, tenant_id, client_id, now_fn(), ds, events, approvals)
        self.system = self._build_system()

    def _build_system(self) -> str:
        return build_system_prompt(self.ds.get_tenant(self.tenant_id),
                                   self.ds.get_client(self.tenant_id, self.client_id), self.ctx.now)

    def _run(self) -> str:
        self.history = run_loop(self.llm, self.system, self.history, self.registry, self.ctx)
        return _last_text(self.history)

    def _refresh(self) -> None:
        self.ctx.now = self._now_fn()
        self.system = self._build_system()

    def send(self, text: str) -> str:
        self._refresh()
        self.events.emit(self.id, self.tenant_id, "user_message", {"text": text})
        self.history.append(Msg("user", [TextPart(text)]))
        return self._run()

    def resume_after_approval(self, approval: Approval, result: dict) -> str:
        self._refresh()
        verdict = "схвалено" if approval.status == "approved" else "відхилено"
        note = approval.note or "—"
        self.history.append(Msg("user", [TextPart(
            f"[SYSTEM] Апрув {approval.id}: {verdict} ({approval.decided_by}). Нотатка: {note}. "
            f"Результат дії: {json.dumps(result, ensure_ascii=False)}")]))
        self.events.emit(self.id, self.tenant_id, "approval_decided",
                         {**approval.model_dump(mode="json"), "result": result})
        return self._run()
