"""Live smoke: прогін демо-сценарію через реальний (або fake) LLM-провайдер без HTTP-шару."""
import argparse
import json
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
from agent.tools import default_registry  # noqa: E402

CHILD = "Вибачте, в мене дитина захворіла, я не зможу завтра на 10, можна щось зробити?"
SCENARIOS = {
    "A": ("lumen", "olena", CHILD),
    "B": ("lumen", "max", CHILD),
    "C": ("denta", "petro", "Хочу скасувати запис і повернути гроші."),
}


def short(value, limit: int = 160) -> str:
    text = json.dumps(value, ensure_ascii=False, default=str)
    return text if len(text) <= limit else text[: limit - 1] + "…"


def describe(event) -> str:
    p = event.payload
    t = event.type
    if t in ("user_message", "assistant_message", "thinking"):
        detail = short(p.get("text", ""), 300)
    elif t == "tool_call":
        detail = f"{p.get('name')} [{p.get('decision')}] {short(p.get('args'))}"
    elif t == "tool_result":
        detail = f"{p.get('name')} -> {short(p.get('result'))}"
    elif t == "card":
        detail = f"{p.get('type')}: {short(p.get('title', ''))}"
    elif t in ("approval_created", "approval_decided"):
        detail = f"{p.get('id')} {p.get('tool')} status={p.get('status')} {short(p.get('args'))}"
    else:
        detail = short(p)
    return f"#{event.id:<3} {t:<17} {detail}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--scenario", choices=sorted(SCENARIOS), default="A")
    args = ap.parse_args()
    tenant_id, client_id, text = SCENARIOS[args.scenario]

    now_fn = lambda: datetime.now(ZoneInfo("Europe/Kyiv"))  # noqa: E731
    ds = MemoryDataSource.from_file(ROOT / "agent" / "seed.json", now_fn())
    events, approvals = EventLog(now_fn), ApprovalStore(now_fn)
    session = Session(f"smoke-{args.scenario}", tenant_id, client_id, "chat", ds, events, approvals,
                      make_client(), default_registry(), now_fn)

    print(f"== Сценарій {args.scenario}: {tenant_id}/{client_id}\n> {text}")
    reply = session.send(text)

    if args.scenario == "B":
        pending = approvals.pending(tenant_id)
        print(f"\n== Pending approvals: {len(pending)}")
        for a in pending:
            print(f"   {a.id} {a.tool} {short(a.args)} | {a.reason}")
            decided = approvals.decide(a.id, True, "Адміністратор", "smoke")
            result = execute_approved(decided, session.ctx)
            print(f"   approved -> {short(result)}")
            reply = session.resume_after_approval(decided, result)

    print("\n== Події")
    all_events = events.since(session.id)
    for e in all_events:
        print(describe(e))
    print(f"\n== Фінальна відповідь\n{reply}")
    return 1 if any(e.type == "error" for e in all_events) else 0


if __name__ == "__main__":
    raise SystemExit(main())
