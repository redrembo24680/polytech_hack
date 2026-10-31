from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from agent.context import SessionCtx, get_ctx
from agent.datasource import DataError
from agent.policy import Allow, Decision, Forbidden, NeedsApproval, PolicyContext, decide, is_late_change

APPROVAL_INSTRUCTION = "Повідом клієнту, що уточнюєш в адміністратора, і заверши відповідь."


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict
    fn: Callable[..., dict]
    kind: str = "read"  # read | write | ui
    action: str | None = None  # policy action for write tools


def _policy_ctx(c: SessionCtx, booking_id: str | None, amount: int | None = None) -> PolicyContext:
    return PolicyContext(
        policy=c.ds.get_tenant(c.tenant_id).policy,
        client=c.ds.get_client(c.tenant_id, c.client_id),
        booking=_own_booking(c, booking_id) if booking_id else None,
        now=c.now,
        amount=amount,
    )


def _decision_name(d: Decision) -> str:
    return {Allow: "allow", NeedsApproval: "needs_approval", Forbidden: "forbidden"}[type(d)]


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        self._tools[spec.name] = spec

    def get(self, name: str) -> ToolSpec:
        return self._tools[name]

    def declarations(self) -> list[dict]:
        return [{"name": t.name, "description": t.description, "parameters": t.parameters} for t in self._tools.values()]

    def call(self, name: str, args: dict) -> dict:
        spec = self._tools.get(name)
        if spec is None:
            return {"error": "unknown_tool", "message": f"Невідомий інструмент: {name}"}
        c = get_ctx()

        def emit(type_: str, payload: dict) -> None:
            c.events.emit(c.session_id, c.tenant_id, type_, payload)

        decision: Decision | None = None
        label = {"read": "read", "ui": "ui"}.get(spec.kind, "error")
        called = False
        detail = None
        try:
            _validate_args(spec, args)
            if spec.kind == "write":
                # policy decision is computed BEFORE anything is executed or logged as done
                decision = _decide_for(spec, c, args)
                label = _decision_name(decision)
            emit("tool_call", {"name": name, "args": args, "decision": label})
            called = True
            result = _run(spec, c, args, decision)
        except DataError as e:
            result = {"error": e.code, "message": e.message}
        except _ArgError as e:
            result = {"error": "validation", "message": str(e)}
        except Exception as e:  # never let model input or a misconfiguration crash the loop
            result = {"error": "internal", "message": "Внутрішня помилка інструмента."}
            detail = f"{type(e).__name__}: {e}"
        if not called:  # failed before the call event was emitted
            emit("tool_call", {"name": name, "args": args, "decision": label})
        payload = {"name": name, "result": result}
        if detail:
            payload["detail"] = detail
        emit("tool_result", payload)
        if spec.kind == "ui" and result.get("status") == "shown":
            emit("card", args["card"])
        return result


class _ArgError(Exception):
    pass


_TYPES = {"string": str, "integer": int, "object": dict}
_DATE_PARAMS = {"start": datetime.fromisoformat, "from_date": date.fromisoformat, "to_date": date.fromisoformat}


def _validate_args(spec: ToolSpec, args: dict) -> None:
    props = spec.parameters["properties"]
    unknown = sorted(set(args) - set(props))
    if unknown:
        raise _ArgError(f"Невідомі аргументи: {unknown}")
    missing = [k for k in spec.parameters.get("required", []) if k not in args]
    if missing:
        raise _ArgError(f"Відсутні обов'язкові аргументи: {missing}")
    for key, value in args.items():
        expected = _TYPES[props[key]["type"]]
        if not isinstance(value, expected) or (expected is int and isinstance(value, bool)):
            raise _ArgError(f"Аргумент {key} має бути типу {props[key]['type']}")
        if key in _DATE_PARAMS:
            try:
                _DATE_PARAMS[key](value)
            except ValueError:
                raise _ArgError(f"Аргумент {key} не є коректною датою ISO") from None


def _own_booking(c: SessionCtx, booking_id: str):
    b = c.ds.get_booking(c.tenant_id, booking_id)
    if b.client_id != c.client_id:
        raise DataError("not_found", "Бронювання не знайдено.")
    return b


def _decide_for(spec: ToolSpec, c: SessionCtx, args: dict) -> Decision:
    pc = _policy_ctx(c, args.get("booking_id"), args.get("amount"))
    if spec.action == "refund" and pc.booking is not None and isinstance(pc.amount, int):
        # an impossible amount is a data error, not something worth an admin's approval
        if not 0 < pc.amount <= pc.booking.prepayment.amount:
            raise DataError("validation", f"Сума повернення має бути від 1 до {pc.booking.prepayment.amount} грн")
    return decide(spec.action, pc)  # type: ignore[arg-type]


def _run(spec: ToolSpec, c: SessionCtx, args: dict, decision: Decision | None) -> dict:
    if decision is None:
        return spec.fn(**args)
    if isinstance(decision, Forbidden):
        return {"status": "forbidden", "reason": decision.reason}
    if isinstance(decision, NeedsApproval):
        ap = c.approvals.create(c.session_id, c.tenant_id, spec.name, dict(args), decision.reason)
        c.events.emit(c.session_id, c.tenant_id, "approval_created", ap.model_dump(mode="json"))
        return {
            "status": "pending_approval", "approval_id": ap.id,
            "reason": decision.reason, "instruction": APPROVAL_INSTRUCTION,
        }
    out = spec.fn(**args)
    return {"status": "done", "decision_reason": decision.reason, **out}


def _booking_json(b) -> dict:
    return b.model_dump(mode="json")


# ---------- read tools ----------

def get_client_profile() -> dict:
    c = get_ctx()
    client = c.ds.get_client(c.tenant_id, c.client_id)
    bookings = sorted(c.ds.list_client_bookings(c.tenant_id, c.client_id), key=lambda b: b.start, reverse=True)
    return {**client.model_dump(mode="json"), "bookings": [_booking_json(b) for b in bookings]}


def get_booking(booking_id: str) -> dict:
    c = get_ctx()
    return _booking_json(_own_booking(c, booking_id))


def find_slots(service_id: str, from_date: str, to_date: str, staff_id: str | None = None) -> dict:
    c = get_ctx()
    tz = c.now.tzinfo or ZoneInfo("Europe/Kyiv")
    start = datetime.combine(date.fromisoformat(from_date), time.min, tzinfo=tz)
    end = datetime.combine(date.fromisoformat(to_date), time.max, tzinfo=tz)
    slots = c.ds.find_slots(c.tenant_id, service_id, start, end, staff_id)
    return {"slots": [s.model_dump(mode="json") for s in slots]}


# ---------- write tools (called only after Allow) ----------

def _forfeit(c: SessionCtx, booking_id: str) -> bool:
    b = _own_booking(c, booking_id)
    policy = c.ds.get_tenant(c.tenant_id).policy
    return is_late_change(policy, b, c.now) and booking_id not in c.goodwill_applied


def _saved_by_goodwill(c: SessionCtx, booking_id: str) -> dict:
    b = _own_booking(c, booking_id)
    policy = c.ds.get_tenant(c.tenant_id).policy
    if booking_id in c.goodwill_applied and is_late_change(policy, b, c.now) and b.prepayment.status == "held":
        return {"saved_uah": b.prepayment.amount}
    return {}


def reschedule_booking(booking_id: str, start: str, reason: str, staff_id: str | None = None) -> dict:
    c = get_ctx()
    new_start = datetime.fromisoformat(start)
    forfeit = _forfeit(c, booking_id)
    saved = _saved_by_goodwill(c, booking_id)
    b = c.ds.reschedule(c.tenant_id, booking_id, new_start, staff_id, reason, "agent", forfeit)
    return {"booking": _booking_json(b), **saved}


def cancel_booking(booking_id: str, reason: str) -> dict:
    c = get_ctx()
    forfeit = _forfeit(c, booking_id)
    saved = _saved_by_goodwill(c, booking_id)
    b = c.ds.cancel(c.tenant_id, booking_id, reason, "agent", forfeit)
    return {"booking": _booking_json(b), **saved}


def refund_prepayment(booking_id: str, amount: int, reason: str) -> dict:
    c = get_ctx()
    return {"booking": _booking_json(c.ds.refund(c.tenant_id, booking_id, amount, reason, "agent"))}


def apply_goodwill_exception(booking_id: str, reason: str) -> dict:
    c = get_ctx()
    b = _own_booking(c, booking_id)
    c.ds.add_goodwill(c.tenant_id, c.client_id, booking_id, reason, "agent")
    c.goodwill_applied.add(booking_id)
    return {"booking": _booking_json(b)}


def waive_no_show_fee(booking_id: str, reason: str) -> dict:
    c = get_ctx()
    b = c.ds.waive_no_show(c.tenant_id, booking_id, reason, "agent")
    return {"booking": _booking_json(b), "saved_uah": c.ds.get_tenant(c.tenant_id).policy.no_show_fee}


def escalate_to_human(summary: str, priority: str) -> dict:
    c = get_ctx()
    t = c.ds.create_ticket(c.tenant_id, c.client_id, summary, priority)
    return {"ticket": t.model_dump(mode="json")}


def show_card(card: dict) -> dict:
    """The registry emits the `card` event right after the tool_result."""
    return {"status": "shown"}


def _schema(props: dict[str, tuple[str, str]], optional: tuple[str, ...] = ()) -> dict:
    return {
        "type": "object",
        "properties": {k: {"type": t, "description": d} for k, (t, d) in props.items()},
        "required": [k for k in props if k not in optional],
    }


BOOKING_ID = ("string", "Ідентифікатор бронювання, наприклад b-olena-1")
REASON = ("string", "Причина дії, зрозуміла адміністратору")


def default_registry() -> ToolRegistry:
    reg = ToolRegistry()
    specs = [
        ToolSpec("get_client_profile", "Профіль поточного клієнта та історія його бронювань (найновіші першими).",
                 _schema({}), get_client_profile),
        ToolSpec("get_booking", "Деталі бронювання за ідентифікатором.", _schema({"booking_id": BOOKING_ID}), get_booking),
        ToolSpec("find_slots", "Знайти вільні слоти для послуги в діапазоні дат.", _schema({
            "service_id": ("string", "Ідентифікатор послуги"),
            "from_date": ("string", "Початок діапазону, дата ISO (РРРР-ММ-ДД)"),
            "to_date": ("string", "Кінець діапазону, дата ISO (РРРР-ММ-ДД)"),
            "staff_id": ("string", "Ідентифікатор майстра (необов'язково)"),
        }, optional=("staff_id",)), find_slots),
        ToolSpec("reschedule_booking", "Перенести бронювання на новий час. Дія проходить перевірку політики закладу.",
                 _schema({
                     "booking_id": BOOKING_ID,
                     "start": ("string", "Новий початок, дата й час ISO 8601"),
                     "reason": REASON,
                     "staff_id": ("string", "Ідентифікатор майстра (необов'язково)"),
                 }, optional=("staff_id",)), reschedule_booking, "write", "reschedule"),
        ToolSpec("cancel_booking", "Скасувати бронювання. Дія проходить перевірку політики закладу.",
                 _schema({"booking_id": BOOKING_ID, "reason": REASON}), cancel_booking, "write", "cancel"),
        ToolSpec("refund_prepayment", "Повернути передоплату (повністю). Дія проходить перевірку політики закладу.",
                 _schema({"booking_id": BOOKING_ID, "amount": ("integer", "Сума повернення в гривнях"), "reason": REASON}),
                 refund_prepayment, "write", "refund"),
        ToolSpec("apply_goodwill_exception", "Застосувати виняток з доброї волі: передоплата не згорає при пізній зміні. "
                 "Дія проходить перевірку політики закладу.",
                 _schema({"booking_id": BOOKING_ID, "reason": REASON}), apply_goodwill_exception, "write",
                 "goodwill_exception"),
        ToolSpec("waive_no_show_fee", "Зняти штраф за неявку. Дія проходить перевірку політики закладу.",
                 _schema({"booking_id": BOOKING_ID, "reason": REASON}), waive_no_show_fee, "write", "waive_no_show_fee"),
        ToolSpec("escalate_to_human", "Передати питання людині: створює тікет для адміністратора.",
                 _schema({
                     "summary": ("string", "Короткий опис проблеми"),
                     "priority": ("string", "Пріоритет: low, normal, high або urgent"),
                 }), escalate_to_human, "write", "escalate"),
        ToolSpec("show_card", "Показати клієнту картку в чаті (слоти, підтвердження тощо).",
                 _schema({"card": ("object", "Картка: type, title, options")}), show_card, "ui"),
    ]
    for s in specs:
        reg.register(s)
    return reg
