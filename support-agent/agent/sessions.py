"""Спільне створення сесій для каналів (web, chat-вебхук): лінива ініціалізація LLM/оркестратора і лок на сесію."""
import os
import threading

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
