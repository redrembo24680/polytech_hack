"""Provider boundary: neutral messages <-> Gemini API, plus a scripted fake."""
import os
from dataclasses import dataclass, field
from typing import Literal, Protocol

from dotenv import load_dotenv


@dataclass(frozen=True)
class TextPart:
    text: str


@dataclass(frozen=True)
class CallPart:
    name: str
    args: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ResultPart:
    name: str
    response: dict = field(default_factory=dict)


Part = TextPart | CallPart | ResultPart


@dataclass(frozen=True)
class Msg:
    role: Literal["user", "model", "tool"]
    parts: list


class LLMClient(Protocol):
    def generate(self, system: str, history: list[Msg], tools: list[dict]) -> Msg: ...


class FakeClient:
    def __init__(self, script: list[Msg]):
        self._script = list(script)
        self.calls: list[dict] = []

    def generate(self, system: str, history: list[Msg], tools: list[dict]) -> Msg:
        self.calls.append({"system": system, "history": list(history), "tools": tools})
        if self._script:
            return self._script.pop(0)
        return Msg("model", [TextPart("…")])


class GeminiClient:
    def __init__(self, model: str, api_key: str, client=None):
        self.model = model
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
                            function_call=types.FunctionCall(name=p.name, args=dict(p.args))
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
                name=t["name"], description=t["description"], parameters=t["parameters"]
            )
            for t in tools
        ]
        config = types.GenerateContentConfig(
            system_instruction=None if as_prefix else system,
            tools=[types.Tool(function_declarations=declarations)] if declarations else None,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            temperature=0.3,
        )
        response = self._client.models.generate_content(
            model=self.model, contents=contents, config=config
        )

        out: list = []
        candidates = getattr(response, "candidates", None) or []
        content = getattr(candidates[0], "content", None) if candidates else None
        for part in (getattr(content, "parts", None) or []):
            fc = getattr(part, "function_call", None)
            if fc is not None:
                out.append(CallPart(fc.name, dict(fc.args or {})))
            elif getattr(part, "text", None):
                out.append(TextPart(part.text))
        return Msg("model", out or [TextPart("")])


def make_client() -> LLMClient:
    load_dotenv()
    provider = os.environ.get("AGENT_PROVIDER", "gemini")
    if provider == "fake":
        return FakeClient([Msg("model", [TextPart("Тестова відповідь")])])
    if provider != "gemini":
        raise ValueError(f"Невідомий провайдер: {provider}")
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("Не задано GEMINI_API_KEY: додайте ключ у .env або середовище.")
    return GeminiClient(os.environ.get("AGENT_MODEL", "gemma-4-31b-it"), api_key)
