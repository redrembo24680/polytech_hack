"""Телефонний канал: Vapi викликає ці вебхуки як server tools; ті самі інструменти й ті самі політики/апруви."""
import json
import os
import re
import threading

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from agent.agent import Session
from agent.cards import parse_card
from agent.context import use
from agent.datasource import DataError
from agent.tools import default_registry

router = APIRouter()

NOT_FOUND_TEXT = "Клієнта з таким номером не знайдено"
SMS_SENT_TEXT = "картку надіслано SMS"


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


def _session_for(app, tenant: str, client) -> Session:
    st = app.state
    key = f"voice:{tenant}:{client.phone}"
    with st.guard:
        s = st.sessions.get(key)
        if s is None:
            s = Session(key, tenant, client.id, "voice", st.ds, st.events, st.approvals, st.llm,
                        default_registry(), st.now_fn, None, None)
            st.sessions[key] = s
            st.locks[key] = threading.Lock()
        return s


def run_tool(app, tenant: str, phone: str, name: str, args: dict) -> str:
    st = app.state
    try:
        clients = st.ds.find_client_by_phone(tenant, normalize_phone(phone))
    except DataError as e:
        return json.dumps({"error": e.code, "message": e.message}, ensure_ascii=False)
    if not clients:
        return NOT_FOUND_TEXT
    session = _session_for(app, tenant, clients[0])
    with st.locks[session.id]:
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
    phone = ((message.get("call") or {}).get("customer") or {}).get("number", "")
    tenant = _tenant(message)
    results = []
    for tc in message.get("toolCallList") or []:
        fn = tc.get("function") or {}
        name = fn.get("name") or tc.get("name") or ""
        args = _args(fn.get("arguments", tc.get("arguments")))
        try:
            text = run_tool(request.app, tenant, phone, name, args)
        except Exception:
            text = json.dumps({"error": "internal", "message": "Внутрішня помилка інструмента."}, ensure_ascii=False)
        results.append({"toolCallId": tc.get("id"), "result": text})
    return {"results": results}


@router.post("/voice/tools/{tool_name}")
def manual_tool(tool_name: str, request: Request, body: dict):
    tenant = body.get("tenant_id") or os.environ.get("VOICE_TENANT_ID") or "lumen"
    text = run_tool(request.app, tenant, body.get("phone", ""), tool_name, _args(body.get("args")))
    return JSONResponse({"result": text})
