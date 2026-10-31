from fastapi.testclient import TestClient

from agent.chat_webhook import ASK_PHONE_TEXT, ERROR_TEXT
from agent.datasource import MemoryDataSource
from agent.llm import CallPart, FakeClient, Msg, TextPart
from agent.main import create_app
from tests.conftest import NOW, SEED_PATH


def make(script, fallback="…"):
    fake = FakeClient(script, fallback)
    c = TestClient(create_app(ds=MemoryDataSource.from_file(SEED_PATH, NOW), llm=fake, now_fn=lambda: NOW))
    return c, fake


def body(text="привіт", client_id="olena", phone=None, conv="c1", extra=None):
    msgs = (extra or []) + [{"role": "client", "text": text, "ts": NOW.isoformat()}]
    return {"tenant_id": "lumen", "conversation_id": conv, "client_id": client_id,
            "visitor_name": None, "visitor_phone": phone, "messages": msgs}


def test_known_client_gets_reply():
    c, fake = make([Msg("model", [TextPart("Вітаю, Олено!")])])
    r = c.post("/chat", json=body())
    assert r.status_code == 200 and r.json() == {"reply": "Вітаю, Олено!"}
    assert len(fake.calls) == 1


def test_phone_resolves_client():
    c, _ = make([Msg("model", [TextPart("ok")])])
    r = c.post("/chat", json=body(client_id=None, phone="380501110001"))
    assert r.json() == {"reply": "ok"}
    assert "chat:lumen:c1" in c.app.state.sessions


def test_unknown_phone_asks_for_phone_without_session():
    c, fake = make([])
    r = c.post("/chat", json=body(client_id=None, phone="380990000000"))
    assert r.status_code == 200 and r.json() == {"reply": ASK_PHONE_TEXT}
    assert c.app.state.sessions == {} and fake.calls == []
    assert c.post("/chat", json=body(client_id=None)).json() == {"reply": ASK_PHONE_TEXT}


def test_same_conversation_reuses_session():
    c, _ = make([Msg("model", [TextPart("один")]), Msg("model", [TextPart("два")])])
    c.post("/chat", json=body("a"))
    c.post("/chat", json=body("b"))
    st = c.app.state
    assert list(st.sessions) == ["chat:lumen:c1"]
    assert [e.type for e in st.events.since("chat:lumen:c1")].count("user_message") == 2
    c.post("/chat", json=body("x", conv="c2"))
    assert len(st.sessions) == 2


def test_card_is_appended_as_text():
    slots = {"type": "slots", "title": "Вільні слоти", "options": [
        {"id": "1", "start": "2026-11-03T13:00:00+02:00", "staff_id": "st-maria", "staff_name": "Марія", "label": "x"},
        {"id": "2", "start": "2026-11-03T14:00:00+02:00", "staff_id": "st-olha", "staff_name": "Ольга", "label": "y"}]}
    c, _ = make([Msg("model", [CallPart("show_card", {"card": slots})]),
                 Msg("model", [TextPart("Оберіть час.")])])
    reply = c.post("/chat", json=body("перенесіть")).json()["reply"]
    assert reply.startswith("Оберіть час.")
    assert "Вільні варіанти:\n1) 03.11 13:00 — Марія\n2) 03.11 14:00 — Ольга\nНапишіть номер варіанта." in reply


def test_old_cards_not_repeated_next_turn():
    slots = {"type": "slots", "title": "t", "options": [
        {"id": "1", "start": "2026-11-03T13:00:00+02:00", "staff_id": "st-maria", "staff_name": "Марія", "label": "x"}]}
    c, _ = make([Msg("model", [CallPart("show_card", {"card": slots})]), Msg("model", [TextPart("a")]),
                 Msg("model", [TextPart("b")])])
    c.post("/chat", json=body("1"))
    assert c.post("/chat", json=body("2")).json() == {"reply": "b"}


def test_only_last_client_message_processed():
    c, fake = make([Msg("model", [TextPart("ok")])])
    history = [{"role": "client", "text": "стара", "ts": "t"}, {"role": "agent", "text": "відповідь", "ts": "t"}]
    c.post("/chat", json=body("нова", extra=history))
    assert len(fake.calls) == 1
    users = [e.payload["text"] for e in c.app.state.events.since("chat:lumen:c1") if e.type == "user_message"]
    assert users == ["нова"]


def test_exception_gives_friendly_reply_and_error_event():
    def explode(self, text):
        raise RuntimeError("boom")

    from agent.agent import Session
    c, _ = make([])
    orig = Session.send
    Session.send = explode
    try:
        r = c.post("/chat", json=body())
    finally:
        Session.send = orig
    assert r.status_code == 200 and r.json() == {"reply": ERROR_TEXT}
    assert any(e.type == "error" for e in c.app.state.events.for_tenant("lumen"))
