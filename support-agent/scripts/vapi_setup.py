"""Створює/оновлює асистента Vapi з наших tools і (з --number) підключає безкоштовний номер.

Запуск: uv run python scripts/vapi_setup.py [--number]
Потрібні VAPI_API_KEY і PUBLIC_URL (env або .env). VAPI_ASSISTANT_ID -> PATCH замість POST.
"""
import argparse
import os
import sys
from pathlib import Path

API = "https://api.vapi.ai"

SYSTEM_PROMPT = """Ти голосовий асистент підтримки салону. Говори українською, коротко й ввічливо.
- Привітайся. Клієнта вже ідентифіковано за номером, з якого він телефонує: не питай номер чи ідентифікатори.
- Для даних і дій користуйся інструментами; не вигадуй фактів. Спершу виклич get_client_profile.
- Дотримуйся політики закладу; не обіцяй винятків, яких не підтвердив інструмент.
- Якщо інструмент повернув pending_approval, скажи, що перевіриш це з адміністратором і зв'яжешся з клієнтом згодом.
- Не читай вголос довгі списки: називай до трьох варіантів. Картки надсилай через show_card (прийдуть SMS)."""


def to_vapi_tool(decl: dict, server_url: str) -> dict:
    params = decl.get("parameters") or {"type": "object", "properties": {}}
    return {"type": "function", "async": False,
            "function": {"name": decl["name"], "description": decl["description"], "parameters": params},
            "server": {"url": server_url}}


def build_assistant_payload(declarations: list[dict], public_url: str, tenant_id: str = "lumen") -> dict:
    server_url = public_url.rstrip("/") + "/voice/tools"
    return {
        "name": "Support agent (voice)",
        "firstMessage": "Вітаю! Чим можу допомогти?",
        "model": {"provider": "openai", "model": "gpt-4o",
                  "messages": [{"role": "system", "content": SYSTEM_PROMPT}],
                  "tools": [to_vapi_tool(d, server_url) for d in declarations]},
        "transcriber": {"provider": "deepgram", "model": "nova-3", "language": "uk"},
        "voice": {"provider": "azure", "voiceId": "uk-UA-PolinaNeural"},
        "server": {"url": server_url},
        "metadata": {"tenant_id": tenant_id},
    }


def build_number_payload(assistant_id: str) -> dict:
    return {"provider": "vapi", "assistantId": assistant_id}


def _load_env() -> None:
    env = Path(__file__).resolve().parent.parent / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def main() -> int:
    import httpx
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from agent.tools import default_registry

    ap = argparse.ArgumentParser()
    ap.add_argument("--number", action="store_true", help="купити/підключити безкоштовний номер Vapi")
    args = ap.parse_args()
    _load_env()
    key, public = os.environ.get("VAPI_API_KEY"), os.environ.get("PUBLIC_URL")
    if not key or not public:
        print("Потрібні VAPI_API_KEY і PUBLIC_URL", file=sys.stderr)
        return 1
    headers = {"Authorization": f"Bearer {key}"}
    payload = build_assistant_payload(default_registry().declarations(), public,
                                      os.environ.get("VOICE_TENANT_ID", "lumen"))
    aid = os.environ.get("VAPI_ASSISTANT_ID")
    with httpx.Client(base_url=API, headers=headers, timeout=30) as c:
        r = c.patch(f"/assistant/{aid}", json=payload) if aid else c.post("/assistant", json=payload)
        r.raise_for_status()
        aid = r.json()["id"]
        print(f"VAPI_ASSISTANT_ID={aid}")
        if args.number:
            r = c.post("/phone-number", json=build_number_payload(aid))
            r.raise_for_status()
            d = r.json()
            print("Номер:", d.get("number") or d.get("id"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
