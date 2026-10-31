"""Телефонний канал: Vapi викликає ці вебхуки як server tools; ті самі інструменти й ті самі політики/апруви."""
import json
import os
import re
import threading
import uuid

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from agent.agent import Session
from agent.cards import parse_card
from agent.context import use
from agent.datasource import DataError
from agent.tools import ToolSpec, default_registry, _schema

router = APIRouter()

NOT_FOUND_TEXT = "Клієнта з таким номером не знайдено"
SMS_SENT_TEXT = "картку надіслано SMS"
ASK_PHONE_FIRST = "Спочатку назвіть номер телефону, на який робили запис."


def normalize_phone(raw: str | None) -> str:
    digits = re.sub(r"[^\d]", "", raw or "")
    if not digits:
        return ""
    if digits.startswith("380"):
        return "+" + digits
    if digits.startswith("0") and len(digits) == 10:
        return "+38" + digits
    return "+" + digits


def render_card_text(card: dict) -> str:
    kind = card.get("type")
    if kind == "slots":
        lines = [card["title"]] + [f'{o["id"]}. {o["label"]}' for o in card["options"]]
    elif kind == "booking_summary":
        p = card["prepayment"]
        lines = [f'{card["service"]}, {card["staff"]}', f'Початок: {card["start"]}',
                 f'Статус: {card["status"]}', f'Передоплата: {p["amount"]} грн ({p["status"]})']
    else:
        lines = [card["title"], card["outcome"]] + [f"- {r}" for r in card["reasoning"]] \
            + [f"* {a}" for a in card["actions_taken"]]
    return "\n".join(lines)


def voice_registry(session_ref: list):
    """default_registry + identify_caller, прив'язаний до сесії (лише голосовий канал)."""
    reg = default_registry()

    def identify_caller(phone: str) -> dict:
        session: Session = session_ref[0]
        if session.client_id is not None:
            return {"error": "already_identified", "message": "Ви вже ідентифіковані за номером дзвінка."}
        found = session.ds.find_client_by_phone(session.tenant_id, normalize_phone(phone))
        if not found:
            return {"error": "not_found", "message": NOT_FOUND_TEXT}
        c = found[0]
        session.client_id = session.ctx.client_id = c.id
        session.meta["phone"] = c.phone
        return {"status": "identified", "name": c.name, "visits_count": c.visits_count,
                "no_show_count": c.no_show_count}

    reg.register(ToolSpec("identify_caller", "Визначити клієнта за номером телефону, який він назвав "
                          "(лише якщо номер дзвінка невідомий).",
                          _schema({"phone": ("string", "Номер телефону клієнта, на який робили запис")}),
                          identify_caller))
    return reg


def _new_session(app, key: str, tenant: str, client_id: str | None, phone: str | None) -> Session:
    st = app.state
    with st.guard:
        s = st.sessions.get(key)
        if s is None:
            ref: list = []
            s = Session(key, tenant, client_id, "voice", st.ds, st.events, st.approvals, st.llm,
                        voice_registry(ref), st.now_fn, None, None)
            ref.append(s)
            if phone:
                s.meta["phone"] = phone
            st.sessions[key] = s
            st.locks[key] = threading.Lock()
        return s


def _session_for(app, tenant: str, client) -> Session:
    return _new_session(app, f"voice:{tenant}:{client.phone}", tenant, client.id, client.phone)


def run_tool(app, tenant: str, phone: str, name: str, args: dict, call_id: str = "") -> str:
    st = app.state
    unbound_key = f"voice:{tenant}:call:{call_id or 'anon-' + uuid.uuid4().hex[:8]}"
    if normalize_phone(phone):
        try:
            clients = st.ds.find_client_by_phone(tenant, normalize_phone(phone))
        except DataError as e:
            return json.dumps({"error": e.code, "message": e.message}, ensure_ascii=False)
        if clients:
            session = _session_for(app, tenant, clients[0])
        else:  # номер дзвінка невідомий у даних: незв'язана сесія, клієнт назве номер через identify_caller
            session = _new_session(app, unbound_key, tenant, None, None)
    else:  # веб-дзвінок без номера: сесія за call.id, лише identify_caller до прив'язки
        session = _new_session(app, unbound_key, tenant, None, None)
    with st.locks[session.id]:
        if session.client_id is None and name != "identify_caller":
            return ASK_PHONE_FIRST
        session._refresh()
        with use(session.ctx):
            result = session.registry.call(name, args)
            if name == "show_card" and result.get("status") == "shown":
                text = render_card_text(parse_card(args["card"]).model_dump(mode="json"))
                st.ds.send_message(tenant, session.client_id, "sms", text)
                return SMS_SENT_TEXT
    return json.dumps(result, ensure_ascii=False)


def _args(raw) -> dict:
    if isinstance(raw, str):
        try:
            raw = json.loads(raw or "{}")
        except ValueError:
            raw = {}
    return raw if isinstance(raw, dict) else {}


def _tenant(message: dict) -> str:
    meta = (message.get("assistant") or {}).get("metadata") or {}
    return meta.get("tenant_id") or os.environ.get("VOICE_TENANT_ID") or "lumen"


@router.post("/voice/tools")
def vapi_tools(request: Request, body: dict):
    message = body.get("message") or {}
    if message.get("type") != "tool-calls":
        return {"ok": True}
    call = message.get("call") or {}
    phone = (call.get("customer") or {}).get("number", "")
    call_id = call.get("id") or ""
    tenant = _tenant(message)
    results = []
    for tc in message.get("toolCallList") or []:
        fn = tc.get("function") or {}
        name = fn.get("name") or tc.get("name") or ""
        args = _args(fn.get("arguments", tc.get("arguments")))
        try:
            text = run_tool(request.app, tenant, phone, name, args, call_id)
        except Exception:
            text = json.dumps({"error": "internal", "message": "Внутрішня помилка інструмента."}, ensure_ascii=False)
        results.append({"toolCallId": tc.get("id"), "result": text})
    return {"results": results}


def manual_tool(tool_name: str, request: Request, body: dict):
    tenant = body.get("tenant_id") or os.environ.get("VOICE_TENANT_ID") or "lumen"
    text = run_tool(request.app, tenant, body.get("phone", ""), tool_name, _args(body.get("args")))
    return JSONResponse({"result": text})

