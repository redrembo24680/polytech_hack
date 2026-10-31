import json

import httpx

from agent.agent import Session
from agent.datasource import MemoryDataSource
from agent.events import ApprovalStore, EventLog
from agent.sessions import deliver_reply
from agent.tools import default_registry
from tests.conftest import NOW, SEED_PATH


def mk(channel, meta=None):
    ds = MemoryDataSource.from_file(SEED_PATH, NOW)
    s = Session("k", "lumen", "olena", channel, ds, EventLog(), ApprovalStore(), None, default_registry(),
                lambda: NOW)
    s.meta.update(meta or {})
    return s, ds


def test_chat_posts_to_site():
    seen = []

    def handler(req):
        seen.append((str(req.url), json.loads(req.content)))
        return httpx.Response(200, json={})

    s, _ = mk("chat", {"conversation_id": "cv1", "site_base_url": "http://site:8001/"})
    deliver_reply(s, "Готово", httpx.MockTransport(handler))
    assert seen == [("http://site:8001/api/tenants/lumen/support/conversations/cv1/reply",
                     {"text": "Готово", "role": "agent"})]


def test_chat_error_emits_event():
    s, _ = mk("chat", {"conversation_id": "cv1", "site_base_url": "http://site"})
    deliver_reply(s, "x", httpx.MockTransport(lambda r: httpx.Response(500)))
    assert [e.type for e in s.events.since("k", 0)] == ["error"]


def test_voice_sends_sms():
    s, ds = mk("voice")
    deliver_reply(s, "Готово")
    assert any(m.channel == "sms" and m.text == "Готово" for m in ds._messages)


def test_web_session_noop():
    def boom(req):
        raise AssertionError("no http")

    s, ds = mk("chat")
    deliver_reply(s, "x", httpx.MockTransport(boom))
    assert ds._messages == [] and s.events.since("k", 0) == []
