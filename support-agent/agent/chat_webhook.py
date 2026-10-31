"""Вебхук чат-віджета платформи: POST /chat -> {"reply": "<plain text>"}; картки рендеряться текстом."""
import os
import re
import secrets

from fastapi import APIRouter, Request

from agent.cards import card_to_text
from agent.datasource import DataError
from agent.sessions import get_or_create_session
from agent.voice import normalize_phone

router = APIRouter()

PHONE_IN_TEXT = re.compile(r"\+?\d[\d\s\-()]{7,16}\d")
ASK_PHONE_TEXT = "Підкажіть, будь ласка, номер телефону, на який робили запис, щоб я знайшов ваш запис."
ERROR_TEXT = "Вибачте, сталася технічна помилка. Адміністратор відповість найближчим часом."


def _verify_enabled() -> bool:
    return os.environ.get("VERIFY_PHONE", "1").strip() != "0"


def _mask_phone(phone: str | None) -> str:
    d = re.sub(r"\D", "", phone or "")
    return f"+{d[:3]}•••{d[-4:]}" if len(d) >= 7 else "вказаний у записі"


def _issue_code(app, session, client, key: str) -> None:
    """Згенерувати код, «надіслати SMS» (OutgoingMessage на платформі) і показати в стрічці копілота."""
    st = app.state
    code = os.environ.get("VERIFY_PHONE_DEMO_CODE", "").strip() or f"{secrets.randbelow(10000):04d}"
    session.meta.update(otp=code, otp_attempts=0)
    text = f"Код підтвердження для чату підтримки: {code}"
    try:
        st.ds.send_message(session.tenant_id, client.id, "sms", text)
    except Exception:
        pass
    st.events.emit(key, session.tenant_id, "sms", {"to": _mask_phone(client.phone), "code": code, "text": text})


def _verify_step(app, session, client, key: str, text: str) -> str | None:
    """None -> номер підтверджено, обробляти pending_text; інакше готова відповідь (без LLM)."""
    m = session.meta
    masked = _mask_phone(client.phone)
    if "otp" not in m:
        m["verified"], m["pending_text"] = False, text
        _issue_code(app, session, client, key)
        return (f"Щоб захистити ваші дані, я надіслав SMS із кодом підтвердження на номер {masked}. "
                "Введіть, будь ласка, 4 цифри з повідомлення.")
    if m.get("blocked"):
        return "Адміністратор зв'яжеться з вами найближчим часом."
    digits = re.sub(r"\D", "", text)
    if digits == m["otp"]:
        m["verified"] = True
        m.pop("otp", None)
        return None
    if len(digits) != 4 or re.search(r"[^\d\s]", text):
        m["pending_text"] = text  # не код: зберігаємо найновіший намір клієнта
        return "Щоб продовжити, введіть, будь ласка, 4-значний код із SMS."
    m["otp_attempts"] = m.get("otp_attempts", 0) + 1
    if m["otp_attempts"] < 3:
        return "Код не збігається. Спробуйте ще раз."
    if not m.get("otp_resent"):
        m["otp_resent"] = True
        _issue_code(app, session, client, key)
        return "Код не збігається. Я надіслав новий код у SMS, введіть його, будь ласка."
    m["blocked"] = True
    try:
        app.state.ds.create_ticket(session.tenant_id, client.id,
                                   "Клієнт не пройшов SMS-підтвердження в чаті підтримки", "normal")
    except Exception:
        pass
    return "Не вдалося підтвердити номер. Адміністратор зв'яжеться з вами найближчим часом."


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
    if client is None:  # невідомий відвідувач міг назвати номер у повідомленні
        m = PHONE_IN_TEXT.search(text)
        if m and 9 <= len(re.sub(r"\D", "", m.group())) <= 12:
            found = st.ds.find_client_by_phone(tenant_id, normalize_phone(m.group()))
            client = found[0] if found else None
    if client is None:
        return ASK_PHONE_TEXT
    conv = body.get("conversation_id") or ""
    key = f'chat:{tenant_id}:{conv}' if conv else f'chat:{tenant_id}:client:{client.id}'
    session = get_or_create_session(app, key, tenant_id, client.id, "chat")
    session.meta.update({"conversation_id": conv,
                         "site_base_url": os.environ.get("APP_API_URL", "")})
    with st.locks[key]:
        prefix = ""
        if _verify_enabled() and not session.meta.get("verified"):
            early = _verify_step(app, session, client, key, text)
            if early is not None:
                return early
            text = session.meta.pop("pending_text", None) or text
            prefix = "Дякую, номер підтверджено. "
        prior = st.events.since(key, 0)
        last_id = prior[-1].id if prior else 0
        reply = session.send(text)
        cards = [e.payload for e in st.events.since(key, last_id) if e.type == "card"]
    parts = [reply] if reply else []
    parts += [card_to_text(c) for c in cards]
    return prefix + "\n\n".join(parts)


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
