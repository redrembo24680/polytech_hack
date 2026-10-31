"""Спільне створення сесій для каналів (web, chat-вебхук): лінива ініціалізація LLM/оркестратора і лок на сесію."""
import os
import threading

import httpx

from agent.agent import Session
from agent.llm import make_client
from agent.orchestrator import make_orchestrator
from agent.tools import default_registry


def ensure_backends(app, llm_factory=None) -> None:
    """Лінива ініціалізація LLM і оркестратора; RuntimeError, якщо LLM не налаштовано."""
    st = app.state
    with st.guard:
        if st.llm is None:
            st.llm = (llm_factory or make_client)()
        if not st.orch_ready:
            st.orchestrator, st.orch_ready = make_orchestrator(), True


def _build(app, session_id: str, tenant_id: str, client_id: str, channel: str) -> Session:
    st = app.state
    return Session(session_id, tenant_id, client_id, channel, st.ds, st.events, st.approvals, st.llm,
                   default_registry(), st.now_fn, st.orchestrator,
                   os.environ.get("AGENT_MODEL") or getattr(st.llm, "model", None))


def get_or_create_session(app, key: str, tenant_id: str, client_id: str, channel: str) -> Session:
    """Сесія за детермінованим ключем (одна на розмову)."""
    ensure_backends(app)
    st = app.state
    with st.guard:
        s = st.sessions.get(key)
        if s is None:
            s = _build(app, key, tenant_id, client_id, channel)
            st.sessions[key] = s
            st.locks[key] = threading.Lock()
        return s


ACTION_NAMES = {
    "reschedule_booking": "перенесення запису",
    "cancel_booking": "скасування запису",
    "refund_prepayment": "повернення передоплати",
    "apply_goodwill_exception": "виняток з доброї волі",
    "waive_no_show_fee": "зняття штрафу за неявку",
}


def voice_decision_text(approval, result: dict) -> str:
    """Детермінована відповідь для голосового клієнта (без LLM): що вирішив адміністратор і що з цього вийшло."""
    verdict = "схвалив" if approval.status == "approved" else "відхилив"
    action = ACTION_NAMES.get(approval.tool, "дію")
    if approval.status != "approved":
        outcome = "Зміни не вносилися."
    elif result.get("status") == "done":
        outcome = "Дію виконано."
    else:
        outcome = f"Не вдалося виконати дію: {result.get('message') or result.get('error') or 'помилка'}."
    return f"Адміністратор {verdict} {action}. {outcome}"


def deliver_reply(session: Session, reply: str, transport: httpx.BaseTransport | None = None) -> None:
    """Доставити відповідь після апруву туди, де клієнт її побачить. Помилки йдуть у подію `error`."""
    def fail(e: Exception) -> None:
        session.events.emit(session.id, session.tenant_id, "error", {"message": f"deliver_reply: {type(e).__name__}: {e}"})

    if session.channel == "voice":
        try:
            session.ds.send_message(session.tenant_id, session.client_id, "sms", reply)
        except Exception as e:
            fail(e)
        return
    base, conv = session.meta.get("site_base_url"), session.meta.get("conversation_id")
    if session.channel != "chat" or not base or not conv:
        return
    url = f"{base.rstrip('/')}/api/tenants/{session.tenant_id}/support/conversations/{conv}/reply"
    try:
        with httpx.Client(timeout=10, transport=transport) as http:
            http.post(url, json={"text": reply, "role": "agent"}).raise_for_status()
    except Exception as e:
        fail(e)
