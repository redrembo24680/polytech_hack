"""Live smoke: прогін демо-сценарію через реальний (або fake) LLM-провайдер без HTTP-шару."""
import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agent.agent import Session, execute_approved  # noqa: E402
from agent.datasource import MemoryDataSource  # noqa: E402
from agent.events import ApprovalStore, EventLog  # noqa: E402
from agent.llm import make_client  # noqa: E402
from agent.orchestrator import make_orchestrator  # noqa: E402
from agent.tools import default_registry  # noqa: E402

CHILD = "Вибачте, в мене дитина захворіла, я не зможу {when}, можна щось зробити?"
SCENARIOS = {
    "A": ("lumen", "olena", "b-olena-1", CHILD),
    "B": ("lumen", "max", "b-max-1", CHILD),
    "C": ("denta", "petro", "b-petro-1", "Хочу скасувати запис і повернути гроші."),
}


def when(booking, now: datetime) -> str:
    """Demo bookings are relative to start time (hours_ahead), so phrase the visit time from data."""
    start = booking.start.astimezone(now.tzinfo)
    day = "сьогодні" if start.date() == now.date() else "завтра"
    return f"{day} на {start.hour}:{start.minute:02d}"


def short(value, limit: int = 160) -> str:
    text = json.dumps(value, ensure_ascii=False, default=str)
    return text if len(text) <= limit else text[: limit - 1] + "…"


def describe(event) -> str:
    p = event.payload
    t = event.type
    if t in ("user_message", "assistant_message", "thinking"):
        detail = short(p.get("text", ""), 300) + (f" [model={p['model']}]" if p.get("model") else "")
    elif t == "tool_call":
        detail = f"{p.get('name')} [{p.get('decision')}] {short(p.get('args'))}"
    elif t == "tool_result":
        detail = f"{p.get('name')} -> {short(p.get('result'))}"
    elif t == "card":
        detail = f"{p.get('type')}: {short(p.get('title', ''))}"
    elif t in ("approval_created", "approval_decided"):
        detail = f"{p.get('id')} {p.get('tool')} status={p.get('status')} {short(p.get('args'))}"
    elif t == "triage":
        detail = f"{p.get('intent')}/{p.get('urgency')}/{p.get('tone')} -> {p.get('route')} model={p.get('model')} {short(p.get('hint', ''))}"
    else:
        detail = short(p)
    return f"#{event.id:<3} {t:<17} {detail}"


def choose_first_slot(session, events, reply: str) -> str:
    """If the agent showed a slots card, answer like a client clicking the first option."""
    cards = [e.payload for e in events.since(session.id) if e.type == "card" and e.payload.get("type") == "slots"]
    options = cards[-1].get("options") if cards else None
    if not options:
        return reply
    first = options[0]
    choice = f"Обираю слот {first['start']} ({first['staff_name']})"
    print(f"> {choice}")
    return session.send(choice)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--scenario", choices=sorted(SCENARIOS), default="A")
    ap.add_argument("--text", help="власне повідомлення клієнта замість шаблону сценарію")
    args = ap.parse_args()
    tenant_id, client_id, booking_id, template = SCENARIOS[args.scenario]

    try:
        llm = make_client()
    except RuntimeError:
        print("Немає GEMINI_API_KEY: додайте ключ у .env або запустіть з AGENT_PROVIDER=fake.")
        return 2

    now_fn = lambda: datetime.now(ZoneInfo("Europe/Kyiv"))  # noqa: E731
    ds = MemoryDataSource.from_file(ROOT / "agent" / "seed.json", now_fn(), now_fn=now_fn)
    events, approvals = EventLog(now_fn), ApprovalStore(now_fn)
    text = args.text or template.format(when=when(ds.get_booking(tenant_id, booking_id), now_fn()))
    session = Session(f"smoke-{args.scenario}", tenant_id, client_id, "chat", ds, events, approvals,
                      llm, default_registry(), now_fn, make_orchestrator(),
                      os.environ.get("AGENT_MODEL") or getattr(llm, "model", None))

    print(f"== Сценарій {args.scenario}: {tenant_id}/{client_id}\n> {text}")
    reply = session.send(text)

    # B and C: the administrator approves everything, in creation order (refund before cancel for C)
    for _ in range(3 if args.scenario in ("B", "C") else 0):
        pending = approvals.pending(tenant_id)
        if not pending:
            break
        print(f"\n== Pending approvals: {len(pending)}")
        for a in pending:
            print(f"   {a.id} {a.tool} {short(a.args)} | {a.reason}")
            decided = approvals.decide(a.id, True, "Адміністратор", "smoke")
            result = execute_approved(decided, session.ctx)
            print(f"   approved -> {short(result)}")
            reply = session.resume_after_approval(decided, result)

    reply = choose_first_slot(session, events, reply)

    print("\n== Події")
    all_events = events.since(session.id)
    for e in all_events:
        print(describe(e))
    print(f"\n== Фінальна відповідь\n{reply}")
    return 1 if any(e.type == "error" for e in all_events) else 0


if __name__ == "__main__":
    raise SystemExit(main())
