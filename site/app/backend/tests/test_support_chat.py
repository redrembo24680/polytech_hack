from datetime import timedelta

import httpx
import pytest

from booking.config import settings
from tests.conftest import NOW

BASE = "/api/tenants/lumen/support/conversations"
STUB = "Агент підтримки ще не підключений"
DOWN = "Агент тимчасово недоступний, адміністратор відповість найближчим часом"


class FakeResp:
    def __init__(self, status=200, data=None, bad_json=False):
        self.status_code = status
        self._data = data
        self._bad = bad_json

    def json(self):
        if self._bad:
            raise ValueError("bad")
        return self._data

    def raise_for_status(self):
        if self.status_code >= 300:
            raise httpx.HTTPStatusError("x", request=None, response=None)


@pytest.fixture
def agent(monkeypatch):
    monkeypatch.setattr(settings, "agent_url", "http://agent.test")
    calls = []

    def install(resp=None, exc=None):
        def fake(url, **kw):
            calls.append((url, kw))
            if exc:
                raise exc
            return resp
        monkeypatch.setattr("booking.services.chat.httpx.post", fake)
        return calls
    return install


def new_conv(client, **body):
    r = client.post(BASE, json=body)
    assert r.status_code == 201, r.text
    return r.json()


def send(client, cid, text="Привіт"):
    return client.post(f"{BASE}/{cid}/messages", json={"text": text})


def test_create_with_known_phone_links_client(client):
    c = new_conv(client, client_phone="+38 067 123 45 01", client_name="Олена")
    assert c["client_id"] == "olena" and c["status"] == "open"


def test_create_unknown_phone_no_client(client):
    c = new_conv(client, client_phone="380000000000", client_name="Хтось")
    assert c["client_id"] is None
    assert c["visitor_name"] == "Хтось" and c["visitor_phone"] == "380000000000"


def test_unknown_visitor_name_in_inbox(client):
    c = new_conv(client, client_phone="0 50 111 22 33", client_name="Гість")
    assert c["client_id"] is None and c["visitor_phone"] == "380501112233"
    row = [x for x in client.get(BASE).json() if x["id"] == c["id"]][0]
    assert row["client_name"] == "Гість"


def test_no_agent_url_gives_stub(client, monkeypatch):
    monkeypatch.setattr(settings, "agent_url", None)
    c = new_conv(client)
    r = send(client, c["id"])
    assert r.status_code == 201
    msgs = r.json()
    assert [m["role"] for m in msgs] == ["client", "agent"]
    assert msgs[1]["text"] == STUB
    assert msgs[0]["ts"] < msgs[1]["ts"]
    got = client.get(f"{BASE}/{c['id']}/messages").json()
    assert [m["text"] for m in got] == ["Привіт", STUB]


def test_agent_reply_and_payload(client, agent):
    calls = agent(FakeResp(data={"reply": "Вітаю!"}))
    c = new_conv(client, client_phone="380671234501")
    send(client, c["id"], "Перше")
    r = send(client, c["id"], "Друге")
    assert [m["text"] for m in r.json()] == ["Друге", "Вітаю!"]
    url, kw = calls[-1]
    assert url == "http://agent.test/chat"
    p = kw["json"]
    assert p["tenant_id"] == "lumen" and p["conversation_id"] == c["id"]
    assert p["client_id"] == "olena"
    assert [m["text"] for m in p["messages"]] == ["Перше", "Вітаю!", "Друге"]
    assert set(p["messages"][0]) == {"role", "text", "ts"}


@pytest.mark.parametrize("kw", [
    {"exc": httpx.TimeoutException("t")},
    {"resp": FakeResp(status=500, data={})},
    {"resp": FakeResp(bad_json=True)},
    {"resp": FakeResp(data=["x"])},
])
def test_agent_failure_gives_unavailable(client, agent, kw):
    agent(**kw)
    c = new_conv(client)
    r = send(client, c["id"])
    assert [m["text"] for m in r.json()][1] == DOWN


@pytest.mark.parametrize("reply", [None, "", "  "])
def test_empty_reply_stores_nothing(client, agent, reply):
    agent(FakeResp(data={"reply": reply}))
    c = new_conv(client)
    r = send(client, c["id"])
    assert len(r.json()) == 1


def test_after_filter(client, monkeypatch):
    monkeypatch.setattr(settings, "agent_url", None)
    c = new_conv(client)
    first = send(client, c["id"]).json()
    ts = first[0]["ts"]
    got = client.get(f"{BASE}/{c['id']}/messages", params={"after": ts}).json()
    assert [m["text"] for m in got] == [STUB]
    got = client.get(f"{BASE}/{c['id']}/messages", params={"after": first[1]["ts"]}).json()
    assert got == []
    r = client.get(f"{BASE}/{c['id']}/messages", params={"after": "2026-11-02T08:00:00"})
    assert r.status_code == 422


def test_chat_channel_message_lands_in_open_conversation(client):
    c = new_conv(client, client_phone="380671234501")
    r = client.post("/api/tenants/lumen/messages",
                    json={"client_id": "olena", "channel": "chat", "text": "Нагадування"})
    assert r.status_code == 201
    got = client.get(f"{BASE}/{c['id']}/messages").json()
    assert [(m["role"], m["text"]) for m in got] == [("agent", "Нагадування")]
    # sms does not
    client.post("/api/tenants/lumen/messages",
                json={"client_id": "olena", "channel": "sms", "text": "x"})
    assert len(client.get(f"{BASE}/{c['id']}/messages").json()) == 1


def test_chat_channel_skips_closed_conversation(client):
    c = new_conv(client, client_phone="380671234501")
    client.patch(f"{BASE}/{c['id']}", json={"status": "closed"})
    client.post("/api/tenants/lumen/messages",
                json={"client_id": "olena", "channel": "chat", "text": "x"})
    assert client.get(f"{BASE}/{c['id']}/messages").json() == []


def test_reply_and_closed_conflict(client):
    c = new_conv(client)
    r = client.post(f"{BASE}/{c['id']}/reply", json={"text": "Я людина", "role": "human"})
    assert r.status_code == 201 and r.json()["role"] == "human"
    assert client.post(f"{BASE}/{c['id']}/reply",
                       json={"text": "x", "role": "client"}).status_code == 422
    p = client.patch(f"{BASE}/{c['id']}", json={"status": "closed", "client_id": "max"})
    assert p.json()["status"] == "closed" and p.json()["client_id"] == "max"
    r = send(client, c["id"])
    assert r.status_code == 409 and r.json()["error"] == "invalid_state"
    assert client.post(f"{BASE}/{c['id']}/reply",
                       json={"text": "x", "role": "agent"}).status_code == 409


def test_list_conversations(client, monkeypatch):
    monkeypatch.setattr(settings, "agent_url", None)
    a = new_conv(client, client_phone="380671234501")
    b = new_conv(client)
    send(client, a["id"], "hello")
    lst = client.get(BASE).json()
    assert [x["id"] for x in lst] == [a["id"], b["id"]]
    assert lst[0]["client_name"] == "Олена Коваленко" and lst[1]["client_name"] is None
    assert lst[0]["last_message"]["text"] == STUB
    assert lst[0]["last_message"]["role"] == "agent"
    assert lst[1]["last_message"] is None
    client.patch(f"{BASE}/{b['id']}", json={"status": "closed"})
    assert [x["id"] for x in client.get(BASE, params={"status": "open"}).json()] == [a["id"]]


def test_tenant_isolation(client):
    c = new_conv(client)
    assert client.get(f"/api/tenants/dentaplus/support/conversations/{c['id']}/messages"
                      ).status_code == 404
