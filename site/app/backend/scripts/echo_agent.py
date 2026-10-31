"""Test agent: echoes the last client message.

Run: cd app/backend && uv run uvicorn scripts.echo_agent:app --host 0.0.0.0 --port 9000
(or: uv run python scripts/echo_agent.py)
"""
from fastapi import FastAPI

app = FastAPI(title="echo-agent")


@app.post("/chat")
def chat(payload: dict) -> dict:
    texts = [m.get("text", "") for m in payload.get("messages", []) if m.get("role") == "client"]
    return {"reply": f"echo: {texts[-1] if texts else ''}"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=9000)
