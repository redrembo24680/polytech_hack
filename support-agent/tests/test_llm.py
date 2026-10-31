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
