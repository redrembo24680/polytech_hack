"""Provider boundary: neutral messages <-> Gemini API, plus a scripted fake."""
import json
import os
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal, Protocol

import httpx
from dotenv import load_dotenv


@dataclass(frozen=True)
class TextPart:
    text: str


@dataclass(frozen=True)
class CallPart:
    name: str
    args: dict = field(default_factory=dict)
    # Gemini: thought_signature, must be sent back with the call.
    # OpenAI-compatible: the tool_call id encoded as bytes, so it round-trips to the tool message.
    signature: bytes | None = None


@dataclass(frozen=True)
class ResultPart:
    name: str
    response: dict = field(default_factory=dict)


Part = TextPart | CallPart | ResultPart


@dataclass(frozen=True)
class Msg:
    role: Literal["user", "model", "tool"]
    parts: list
    raw: object = None  # provider-native content (Anthropic: blocks incl. thinking), replayed verbatim


class LLMClient(Protocol):
    def generate(self, system: str, history: list[Msg], tools: list[dict]) -> Msg: ...


class FakeClient:
    def __init__(self, script: list[Msg], fallback: str = "…"):
        self._script = list(script)
        self._fallback = fallback
        self.calls: list[dict] = []

    def generate(self, system: str, history: list[Msg], tools: list[dict]) -> Msg:
        self.calls.append({"system": system, "history": list(history), "tools": tools})
        if self._script:
            return self._script.pop(0)
        return Msg("model", [TextPart(self._fallback)])


RETRY_DELAYS = (0.5, 1.0, 2.0)


def _retryable(exc: Exception) -> bool:
    from google.genai import errors

    code = getattr(exc, "code", None)
    return isinstance(exc, errors.APIError) and isinstance(code, int) and (code == 429 or code >= 500)


class GeminiClient:
    def __init__(self, model: str, api_key: str, client=None, sleep: Callable[[float], None] = time.sleep):
        self.model = model
        self._sleep = sleep
        if client is None:
            from google import genai

            client = genai.Client(api_key=api_key)
        self._client = client

    def generate(self, system: str, history: list[Msg], tools: list[dict]) -> Msg:
        from google.genai import types

        as_prefix = os.environ.get("AGENT_SYSTEM_AS_PREFIX") == "1"
        prefix_pending = as_prefix
        contents = []
        for msg in history:
            parts = []
            for p in msg.parts:
                if isinstance(p, TextPart):
                    text = p.text
                    if prefix_pending and msg.role == "user":
                        text = f"[Інструкції]\n{system}\n\n[Повідомлення клієнта]\n{text}"
                        prefix_pending = False
                    parts.append(types.Part(text=text))
                elif isinstance(p, CallPart):
                    parts.append(
                        types.Part(
                            function_call=types.FunctionCall(name=p.name, args=dict(p.args)),
                            thought_signature=p.signature,
                        )
                    )
                else:
                    parts.append(
                        types.Part.from_function_response(
                            name=p.name, response=dict(p.response)
                        )
                    )
            role = "model" if msg.role == "model" else "user"
            contents.append(types.Content(role=role, parts=parts))

        declarations = [
            types.FunctionDeclaration(
                name=t["name"], description=t["description"],
                **({"parameters": t["parameters"]} if t.get("parameters") else {}),
            )
            for t in tools
        ]
        config = types.GenerateContentConfig(
            system_instruction=None if as_prefix else system,
            tools=[types.Tool(function_declarations=declarations)] if declarations else None,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            temperature=0.3,
        )
        response = self._call_with_retry(contents, config)

        out: list = []
        candidates = getattr(response, "candidates", None) or []
        content = getattr(candidates[0], "content", None) if candidates else None
        for part in (getattr(content, "parts", None) or []):
            if getattr(part, "thought", False):
                continue  # internal reasoning of the model, never shown to the client
            fc = getattr(part, "function_call", None)
            if fc is not None:
                out.append(CallPart(fc.name, dict(fc.args or {}), getattr(part, "thought_signature", None)))
            elif getattr(part, "text", None):
                out.append(TextPart(part.text))
        return Msg("model", out or [TextPart("")])

    def _call_with_retry(self, contents, config):
        """Up to len(RETRY_DELAYS) retries with backoff on 429 / 5xx; other errors are raised at once."""
        for delay in (*RETRY_DELAYS, None):
            try:
                return self._client.models.generate_content(
                    model=self.model, contents=contents, config=config
                )
            except Exception as e:
                if delay is None or not _retryable(e):
                    raise
                self._sleep(delay)


def _lower_types(schema):
    """Gemini JSON schema uses upper-case types (OBJECT); OpenAI-style wants lower-case."""
    if isinstance(schema, dict):
        return {
            k: (v.lower() if k == "type" and isinstance(v, str) else _lower_types(v))
            for k, v in schema.items()
        }
    if isinstance(schema, list):
        return [_lower_types(v) for v in schema]
    return schema


def _openai_retryable(exc: Exception) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        return code == 429 or code >= 500
    return isinstance(exc, httpx.TransportError)


class OpenAICompatClient:
    """Any OpenAI-compatible /chat/completions server (Ollama, vLLM, LM Studio...)."""

    def __init__(self, model: str, base_url: str, api_key: str = "ollama",
                 http: httpx.Client | None = None, sleep: Callable[[float], None] = time.sleep):
        self.model = model
        self.base_url = base_url
        self.api_key = api_key
        self._sleep = sleep
        self._http = http or httpx.Client(base_url=base_url, timeout=120)

    def _messages(self, system: str, history: list[Msg]) -> list[dict]:
        as_prefix = os.environ.get("AGENT_SYSTEM_AS_PREFIX") == "1"
        prefix_pending = as_prefix
        out: list[dict] = [] if as_prefix else [{"role": "system", "content": system}]
        last_ids: list[str] = []
        for msg in history:
            if msg.role == "user":
                texts = []
                for p in msg.parts:
                    if isinstance(p, TextPart):
                        texts.append(p.text)
                text = "".join(texts)
                if prefix_pending:
                    text = f"[Інструкції]\n{system}\n\n[Повідомлення клієнта]\n{text}"
                    prefix_pending = False
                out.append({"role": "user", "content": text})
            elif msg.role == "model":
                text = "".join(p.text for p in msg.parts if isinstance(p, TextPart))
                calls = [p for p in msg.parts if isinstance(p, CallPart)]
                last_ids = [
                    c.signature.decode() if c.signature else f"call_{i}" for i, c in enumerate(calls)
                ]
                entry: dict = {"role": "assistant", "content": text or None}
                if calls:
                    entry["tool_calls"] = [
                        {"id": cid, "type": "function",
                         "function": {"name": c.name, "arguments": json.dumps(dict(c.args), ensure_ascii=False)}}
                        for cid, c in zip(last_ids, calls)
                    ]
                out.append(entry)
            else:
                results = [p for p in msg.parts if isinstance(p, ResultPart)]
                for i, r in enumerate(results):
                    cid = last_ids[i] if len(last_ids) == len(results) else f"call_{i}"
                    out.append({"role": "tool", "tool_call_id": cid,
                                "content": json.dumps(r.response, ensure_ascii=False)})
        return out

    @staticmethod
    def _tools(tools: list[dict]) -> list[dict]:
        return [
            {"type": "function", "function": {
                "name": t["name"], "description": t["description"],
                "parameters": _lower_types(t.get("parameters") or {"type": "object", "properties": {}}),
            }}
            for t in tools
        ]

    def generate(self, system: str, history: list[Msg], tools: list[dict]) -> Msg:
        payload: dict = {
            "model": self.model,
            "messages": self._messages(system, history),
            "temperature": 0.3,
            "stream": False,
        }
        if tools:
            payload["tools"] = self._tools(tools)
        data = self._post(payload)

        message = ((data.get("choices") or [{}])[0].get("message")) or {}
        out: list = []
        if message.get("content"):
            out.append(TextPart(message["content"]))
        for tc in message.get("tool_calls") or []:
            fn = tc.get("function") or {}
            try:
                args = json.loads(fn.get("arguments") or "{}") or {}
            except (ValueError, TypeError):
                args = {}
            if not isinstance(args, dict):
                args = {}
            tid = tc.get("id")
            out.append(CallPart(fn.get("name", ""), args, tid.encode() if tid else None))
        return Msg("model", out or [TextPart("")])

    def _post(self, payload: dict) -> dict:
        """Up to len(RETRY_DELAYS) retries on 429 / 5xx / transport errors; other errors are raised at once."""
        headers = {"Authorization": f"Bearer {self.api_key}"}
        for delay in (*RETRY_DELAYS, None):
            try:
                resp = self._http.post("/chat/completions", json=payload, headers=headers)
                resp.raise_for_status()
                return resp.json()
            except (httpx.HTTPStatusError, httpx.TransportError) as e:
                if delay is None or not _openai_retryable(e):
                    raise
                self._sleep(delay)


class AnthropicClient:
    """Anthropic Messages API (Claude). Thinking blocks are replayed via Msg.raw."""

    REFUSAL = "Вибачте, я не можу допомогти з цим запитом."

    def __init__(self, model: str, api_key: str, client=None, max_tokens: int = 4096):
        self.model = model
        self.max_tokens = max_tokens
        if client is None:
            import anthropic

            client = anthropic.Anthropic(api_key=api_key)
        self._client = client

    @staticmethod
    def _messages(system: str, history: list[Msg], prefix: bool) -> list[dict]:
        prefix_pending = prefix
        out: list[dict] = []
        last_ids: list[str] = []
        for msg in history:
            if msg.role == "user":
                text = "".join(p.text for p in msg.parts if isinstance(p, TextPart))
                if prefix_pending:
                    text = f"[Інструкції]\n{system}\n\n[Повідомлення клієнта]\n{text}"
                    prefix_pending = False
                out.append({"role": "user", "content": text})
            elif msg.role == "model":
                calls = [p for p in msg.parts if isinstance(p, CallPart)]
                last_ids = [
                    c.signature.decode() if c.signature else f"toolu_{i}" for i, c in enumerate(calls)
                ]
                if msg.raw:
                    content = msg.raw
                else:
                    content = [{"type": "text", "text": p.text} for p in msg.parts
                               if isinstance(p, TextPart) and p.text]
                    content += [{"type": "tool_use", "id": cid, "name": c.name, "input": dict(c.args)}
                                for cid, c in zip(last_ids, calls)]
                out.append({"role": "assistant", "content": content})
            else:
                results = [p for p in msg.parts if isinstance(p, ResultPart)]
                blocks = []
                for i, r in enumerate(results):
                    cid = last_ids[i] if i < len(last_ids) else f"toolu_{i}"
                    blocks.append({"type": "tool_result", "tool_use_id": cid,
                                   "content": json.dumps(r.response, ensure_ascii=False)})
                out.append({"role": "user", "content": blocks})
        return out

    @staticmethod
    def _tools(tools: list[dict]) -> list[dict]:
        return [
            {"name": t["name"], "description": t["description"],
             "input_schema": _lower_types(t.get("parameters") or {"type": "object", "properties": {}})}
            for t in tools
        ]

    def generate(self, system: str, history: list[Msg], tools: list[dict]) -> Msg:
        as_prefix = os.environ.get("AGENT_SYSTEM_AS_PREFIX") == "1"
        kwargs: dict = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": self._messages(system, history, as_prefix),
            "output_config": {"effort": "medium"},
        }
        if not as_prefix:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = self._tools(tools)
        resp = self._client.messages.create(**kwargs)

        if getattr(resp, "stop_reason", None) == "refusal":
            return Msg("model", [TextPart(self.REFUSAL)])
        out: list = []
        raw: list[dict] = []
        for block in resp.content or []:
            raw.append(block.model_dump())
            if block.type == "text" and block.text:
                out.append(TextPart(block.text))
            elif block.type == "tool_use":
                out.append(CallPart(block.name, dict(block.input or {}), block.id.encode()))
        return Msg("model", out or [TextPart("")], raw=raw)


def make_client() -> LLMClient:
    load_dotenv()
    provider = os.environ.get("AGENT_PROVIDER", "gemini")
    if provider == "fake":
        return FakeClient([], fallback="Тестова відповідь")
    if provider in ("openai_compat", "ollama"):
        return OpenAICompatClient(
            model=os.environ.get("AGENT_MODEL", "gemma4"),
            base_url=os.environ.get("OPENAI_BASE_URL", "http://localhost:11434/v1"),
            api_key=os.environ.get("OPENAI_API_KEY", "ollama"),
        )
    if provider == "anthropic":
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("Не задано ANTHROPIC_API_KEY: додайте ключ у .env або середовище.")
        return AnthropicClient(os.environ.get("AGENT_MODEL", "claude-sonnet-5-5"), api_key)
    if provider != "gemini":
        raise ValueError(f"Невідомий провайдер: {provider}")
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("Не задано GEMINI_API_KEY: додайте ключ у .env або середовище.")
    return GeminiClient(os.environ.get("AGENT_MODEL", "gemma-4-31b-it"), api_key)
