"""Вебхук чат-віджета платформи: POST /chat -> {"reply": "<plain text>"}; картки рендеряться текстом."""
import os
from datetime import datetime

from fastapi import APIRouter, Request

from agent.datasource import DataError
from agent.sessions import get_or_create_session
from agent.voice import normalize_phone

router = APIRouter()

ASK_PHONE_TEXT = "Підкажіть, будь ласка, номер телефону, на який робили запис, щоб я знайшов ваш запис."
ERROR_TEXT = "Вибачте, сталася технічна помилка. Адміністратор відповість найближчим часом."


def _when(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso).strftime("%d.%m %H:%M")
    except ValueError:
        return iso


def card_to_text(card: dict) -> str:
    kind = card.get("type")
    if kind == "slots":
        lines = ["Вільні варіанти:"]
        for i, o in enumerate(card.get("options") or [], 1):
            lines.append(f'{o.get("id") or i}) {_when(o["start"])} — {o["staff_name"]}')
        lines.append("Напишіть номер варіанта.")
        return "\n".join(lines)
    if kind == "booking_summary":
        p = card["prepayment"]
        return (f'{card["service"]}, {card["staff"]}, {_when(card["start"])}, '
                f'передоплата {p["amount"]} грн ({p["status"]})')
    return f'✅ {card["title"]}\n{card["outcome"]}'


def _last_client_text(messages: list[dict]) -> str:
    for m in reversed(messages):
        if m.get("role") == "client" and (m.get("text") or "").strip():
            return m["text"]
    return ""


def _resolve_client(ds, tenant_id: str, body: dict):
    if body.get("client_id"):
        try:
            return ds.get_client(tenant_id, body["client_id"])
        except DataError as e:
            if e.code != "not_found":
                raise
    phone = normalize_phone(body.get("visitor_phone"))
    if phone:
        found = ds.find_client_by_phone(tenant_id, phone)
        if found:
            return found[0]
    return None


def _handle(app, tenant_id: str, body: dict) -> str:
    st = app.state
    text = _last_client_text(body.get("messages") or [])
    if not text:
        return ""
    client = _resolve_client(st.ds, tenant_id, body)
    if client is None:
        return ASK_PHONE_TEXT
    key = f'chat:{tenant_id}:{body.get("conversation_id")}'
    session = get_or_create_session(app, key, tenant_id, client.id, "chat")
    session.meta.update({"conversation_id": body.get("conversation_id"),
                         "site_base_url": os.environ.get("APP_API_URL", "")})
    with st.locks[key]:
        prior = st.events.since(key, 0)
        last_id = prior[-1].id if prior else 0
        reply = session.send(text)
        cards = [e.payload for e in st.events.since(key, last_id) if e.type == "card"]
    parts = [reply] if reply else []
    parts += [card_to_text(c) for c in cards]
    return "\n\n".join(parts)


@router.post("/chat")
def chat(request: Request, body: dict):
    app = request.app
    tenant_id = body.get("tenant_id") or ""
    try:
        return {"reply": _handle(app, tenant_id, body)}
    except Exception as e:
        app.state.events.emit(f'chat:{tenant_id}:{body.get("conversation_id")}', tenant_id, "error",
                              {"message": f"{type(e).__name__}: {e}"})
        return {"reply": ERROR_TEXT}
