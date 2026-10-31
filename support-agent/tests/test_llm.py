from types import SimpleNamespace

import pytest

from agent.llm import (
    CallPart,
    FakeClient,
    GeminiClient,
    Msg,
    ResultPart,
    TextPart,
    make_client,
)

TOOLS = [
    {
        "name": "get_booking",
        "description": "Get a booking",
        "parameters": {
            "type": "object",
            "properties": {"booking_id": {"type": "string"}},
            "required": ["booking_id"],
        },
    }
]


class FakeSDK:
    def __init__(self, parts, errors=()):
        self.kwargs = None
        response = SimpleNamespace(
            candidates=[SimpleNamespace(content=SimpleNamespace(parts=parts))]
        )
        self.models = SimpleNamespace(generate_content=self._gen)
        self._response = response
        self._errors = list(errors)
        self.attempts = 0

    def _gen(self, **kwargs):
        self.attempts += 1
        self.kwargs = kwargs
        if self._errors:
            raise self._errors.pop(0)
        return self._response


def _history():
    return [
        Msg("user", [TextPart("Де моє бронювання?")]),
        Msg("model", [CallPart("get_booking", {"booking_id": "b-olena-1"})]),
        Msg("tool", [ResultPart("get_booking", {"status": "ok"})]),
    ]


def test_fake_client_returns_script_in_order():
    a, b = Msg("model", [TextPart("a")]), Msg("model", [TextPart("b")])
    fake = FakeClient([a, b])
    hist = [Msg("user", [TextPart("hi")])]
    assert fake.generate("sys", hist, []) is a
    hist.append(b)
    assert fake.generate("sys2", hist, TOOLS) is b
    assert fake.calls[0]["system"] == "sys"
    assert len(fake.calls[0]["history"]) == 1
    assert fake.calls[1]["tools"] == TOOLS
    assert fake.generate("s", [], []).parts[0].text == "…"


def test_gemini_converts_history_and_parses_function_call(monkeypatch):
    monkeypatch.delenv("AGENT_SYSTEM_AS_PREFIX", raising=False)
    sdk = FakeSDK(
        [
            SimpleNamespace(text="думаю", function_call=None),
            SimpleNamespace(
                text=None,
                function_call=SimpleNamespace(
                    name="get_booking", args={"booking_id": "b-olena-1"}
                ),
            ),
        ]
    )
    client = GeminiClient("gemma-4-31b-it", "k", client=sdk)
    out = client.generate("SYS", _history(), TOOLS)
    kw = sdk.kwargs
    assert kw["model"] == "gemma-4-31b-it"
    cfg = kw["config"]
    assert cfg.automatic_function_calling.disable is True
    assert cfg.system_instruction == "SYS"
    assert cfg.temperature == 0.3
    assert cfg.tools[0].function_declarations[0].name == "get_booking"
    roles = [c.role for c in kw["contents"]]
    assert roles == ["user", "model", "user"]
    assert kw["contents"][1].parts[0].function_call.name == "get_booking"
    fr = kw["contents"][-1].parts[0].function_response
    assert fr.name == "get_booking" and fr.response == {"status": "ok"}
    assert out == Msg(
        "model",
        [TextPart("думаю"), CallPart("get_booking", {"booking_id": "b-olena-1"})],
    )


def test_system_as_prefix_env(monkeypatch):
    monkeypatch.setenv("AGENT_SYSTEM_AS_PREFIX", "1")
    sdk = FakeSDK([SimpleNamespace(text="ok", function_call=None)])
    GeminiClient("m", "k", client=sdk).generate("SYS", _history(), TOOLS)
    assert sdk.kwargs["config"].system_instruction is None
    first = sdk.kwargs["contents"][0].parts[0].text
    assert first == "[Інструкції]\nSYS\n\n[Повідомлення клієнта]\nДе моє бронювання?"


def test_thought_parts_are_skipped_and_signature_carried(monkeypatch):
    monkeypatch.delenv("AGENT_SYSTEM_AS_PREFIX", raising=False)
    sdk = FakeSDK([
        SimpleNamespace(text="внутрішнє міркування", thought=True, function_call=None),
        SimpleNamespace(text=None, thought=None, thought_signature=b"sig-1",
                        function_call=SimpleNamespace(name="get_booking", args={"booking_id": "b-1"})),
    ])
    client = GeminiClient("m", "k", client=sdk)
    out = client.generate("s", _history(), TOOLS)
    assert out == Msg("model", [CallPart("get_booking", {"booking_id": "b-1"}, signature=b"sig-1")])
    client.generate("s", [Msg("user", [TextPart("x")]), out], TOOLS)
    part = sdk.kwargs["contents"][1].parts[0]
    assert part.function_call.name == "get_booking" and part.thought_signature == b"sig-1"


def test_no_parameters_key_for_argless_tool(monkeypatch):
    monkeypatch.delenv("AGENT_SYSTEM_AS_PREFIX", raising=False)
    sdk = FakeSDK([SimpleNamespace(text="ok", function_call=None)])
    GeminiClient("m", "k", client=sdk).generate("s", _history(), [{"name": "get_client_profile", "description": "d"}])
    decl = sdk.kwargs["config"].tools[0].function_declarations[0]
    assert decl.name == "get_client_profile" and decl.parameters is None


def _api_error(code):
    from google.genai import errors

    return errors.APIError(code, {"error": {"code": code, "message": "x", "status": "S"}})


def test_retries_on_429_and_5xx_with_backoff():
    sleeps = []
    sdk = FakeSDK([SimpleNamespace(text="ok", function_call=None)], errors=[_api_error(429), _api_error(503)])
    out = GeminiClient("m", "k", client=sdk, sleep=sleeps.append).generate("s", _history(), [])
    assert out == Msg("model", [TextPart("ok")]) and sdk.attempts == 3 and sleeps == [0.5, 1.0]


def test_retries_exhausted_reraises():
    from google.genai import errors

    sleeps = []
    sdk = FakeSDK([], errors=[_api_error(500)] * 4)
    with pytest.raises(errors.APIError):
        GeminiClient("m", "k", client=sdk, sleep=sleeps.append).generate("s", _history(), [])
    assert sdk.attempts == 4 and sleeps == [0.5, 1.0, 2.0]


def test_client_error_is_not_retried():
    from google.genai import errors

    sleeps = []
    sdk = FakeSDK([], errors=[_api_error(400)])
    with pytest.raises(errors.APIError):
        GeminiClient("m", "k", client=sdk, sleep=sleeps.append).generate("s", _history(), [])
    assert sdk.attempts == 1 and sleeps == []


def test_empty_response_gives_empty_text():
    sdk = SimpleNamespace(
        models=SimpleNamespace(generate_content=lambda **kw: SimpleNamespace(candidates=[]))
    )
    out = GeminiClient("m", "k", client=sdk).generate("s", _history(), [])
    assert out == Msg("model", [TextPart("")])


def test_make_client(monkeypatch):
    monkeypatch.setattr("agent.llm.load_dotenv", lambda: None)
    monkeypatch.setenv("AGENT_PROVIDER", "fake")
    fake = make_client()
    assert isinstance(fake, FakeClient)
    for _ in range(3):
        assert fake.generate("s", [], []).parts == [TextPart("Тестова відповідь")]
    monkeypatch.setenv("AGENT_PROVIDER", "nope")
    with pytest.raises(ValueError):
        make_client()
    monkeypatch.setenv("AGENT_PROVIDER", "gemini")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        make_client()


# ---- OpenAI-compatible provider (Ollama) ----
import json as _json

import httpx

from agent.llm import OpenAICompatClient

GEMINI_TOOLS = [
    {
        "name": "get_booking",
        "description": "Get a booking",
        "parameters": {
            "type": "OBJECT",
            "properties": {"booking_id": {"type": "STRING"}, "tags": {"type": "ARRAY", "items": {"type": "STRING"}}},
            "required": ["booking_id"],
        },
    },
    {"name": "ping", "description": "No args"},
]


def _oa_client(handler, sleep=lambda s: None):
    http = httpx.Client(base_url="http://x/v1", transport=httpx.MockTransport(handler))
    return OpenAICompatClient("gemma4", "http://x/v1", http=http, sleep=sleep)


def _ok(message):
    return httpx.Response(200, json={"choices": [{"message": message}]})


def test_openai_request_shape(monkeypatch):
    monkeypatch.delenv("AGENT_SYSTEM_AS_PREFIX", raising=False)
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["body"] = _json.loads(request.content)
        return _ok({"content": "ok"})

    history = [
        Msg("user", [TextPart("привіт")]),
        Msg("model", [TextPart("шукаю"), CallPart("get_booking", {"booking_id": "b1"}, b"abc"), CallPart("ping", {})]),
        Msg("tool", [ResultPart("get_booking", {"ok": True}), ResultPart("ping", {"pong": 1})]),
    ]
    _oa_client(handler).generate("SYS", history, GEMINI_TOOLS)
    body = seen["body"]
    assert seen["url"] == "http://x/v1/chat/completions"
    assert body["model"] == "gemma4" and body["temperature"] == 0.3 and body["stream"] is False
    m = body["messages"]
    assert m[0] == {"role": "system", "content": "SYS"}
    assert m[1] == {"role": "user", "content": "привіт"}
    calls = m[2]["tool_calls"]
    assert m[2]["content"] == "шукаю"
    assert calls[0]["id"] == "abc" and calls[0]["type"] == "function"
    assert calls[0]["function"] == {"name": "get_booking", "arguments": '{"booking_id": "b1"}'}
    assert calls[1]["id"] == "call_1"
    assert m[3] == {"role": "tool", "tool_call_id": "abc", "content": '{"ok": true}'}
    assert m[4]["tool_call_id"] == "call_1"
    t0, t1 = body["tools"]
    assert t0["type"] == "function" and t0["function"]["parameters"]["type"] == "object"
    assert t0["function"]["parameters"]["properties"]["tags"]["items"]["type"] == "string"
    assert t1["function"]["parameters"] == {"type": "object", "properties": {}}


def test_openai_system_as_prefix(monkeypatch):
    monkeypatch.setenv("AGENT_SYSTEM_AS_PREFIX", "1")
    seen = {}

    def handler(request):
        seen["body"] = _json.loads(request.content)
        return _ok({"content": "ok"})

    _oa_client(handler).generate("SYS", [Msg("user", [TextPart("hi")])], [])
    m = seen["body"]["messages"]
    assert [x["role"] for x in m] == ["user"]
    assert m[0]["content"] == "[Інструкції]\nSYS\n\n[Повідомлення клієнта]\nhi"


def test_openai_parses_content_and_tool_calls():
    def handler(request):
        return _ok({
            "content": "роблю",
            "tool_calls": [
                {"id": "c1", "type": "function", "function": {"name": "a", "arguments": '{"x": 1}'}},
                {"id": "c2", "type": "function", "function": {"name": "b", "arguments": "not json"}},
            ],
        })

    out = _oa_client(handler).generate("s", [Msg("user", [TextPart("q")])], [])
    assert out.role == "model"
    assert out.parts == [
        TextPart("роблю"),
        CallPart("a", {"x": 1}, b"c1"),
        CallPart("b", {}, b"c2"),
    ]


def test_openai_empty_message_gives_empty_text():
    out = _oa_client(lambda r: _ok({"content": None})).generate("s", [], [])
    assert out.parts == [TextPart("")]


def test_openai_retries_503_then_succeeds():
    n = {"i": 0}
    slept = []

    def handler(request):
        n["i"] += 1
        return httpx.Response(503) if n["i"] <= 2 else _ok({"content": "ok"})

    out = _oa_client(handler, sleep=slept.append).generate("s", [], [])
    assert out.parts == [TextPart("ok")] and slept == [0.5, 1.0]


def test_openai_retries_exhausted_raises():
    n = {"i": 0}

    def handler(request):
        n["i"] += 1
        return httpx.Response(503)

    with pytest.raises(httpx.HTTPStatusError):
        _oa_client(handler).generate("s", [], [])
    assert n["i"] == 4


def test_openai_client_error_not_retried():
    n = {"i": 0}

    def handler(request):
        n["i"] += 1
        return httpx.Response(400)

    with pytest.raises(httpx.HTTPStatusError):
        _oa_client(handler).generate("s", [], [])
    assert n["i"] == 1


def test_make_client_ollama_defaults(monkeypatch):
    monkeypatch.setattr("agent.llm.load_dotenv", lambda: None)
    for k in ("AGENT_MODEL", "OPENAI_BASE_URL", "OPENAI_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    for provider in ("ollama", "openai_compat"):
        monkeypatch.setenv("AGENT_PROVIDER", provider)
        c = make_client()
        assert isinstance(c, OpenAICompatClient)
        assert c.model == "gemma4" and c.base_url == "http://localhost:11434/v1" and c.api_key == "ollama"
