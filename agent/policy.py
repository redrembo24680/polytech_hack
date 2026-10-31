from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

from agent.models import Booking, Client, Policy

Action = Literal[
    "reschedule", "cancel", "refund", "goodwill_exception", "waive_no_show_fee", "escalate"
]


@dataclass(frozen=True)
class Allow:
    reason: str


@dataclass(frozen=True)
class NeedsApproval:
    reason: str


@dataclass(frozen=True)
class Forbidden:
    reason: str


Decision = Allow | NeedsApproval | Forbidden


@dataclass(frozen=True)
class PolicyContext:
    policy: Policy
    client: Client
    booking: Booking | None
    now: datetime
    amount: int | None = None


def goodwill_used_in_window(client: Client, now: datetime, days: int = 180) -> int:
    since = now - timedelta(days=days)
    return sum(1 for e in client.goodwill_exceptions if since <= e.date <= now)


def is_late_change(policy: Policy, booking: Booking, now: datetime) -> bool:
    within_window = booking.start - now < timedelta(hours=policy.cancellation_window_hours)
    return within_window and policy.late_change_forfeits_prepayment


def decide(action: Action, ctx: PolicyContext) -> Decision:
    if action == "escalate":
        return Allow("Передати питання людині можна завжди.")

    perms = ctx.policy.agent_permissions
    mode = getattr(perms, action)
    if mode == "forbidden":
        return Forbidden("Політика закладу забороняє агенту виконувати цю дію.")
    if mode == "approval":
        return NeedsApproval("Політика закладу вимагає підтвердження людини для цієї дії.")

    if action == "refund":
        if mode != "auto_under_limit":
            raise ValueError(f"unknown permission mode {mode!r} for {action}")
        amount = ctx.amount
        if amount is None or amount <= 0:
            return NeedsApproval("Суму повернення не вказано або вона недійсна, тому потрібне підтвердження людини.")
        limit = perms.refund_auto_limit
        if amount <= limit:
            return Allow(f"Сума повернення {amount} грн не перевищує автоматичний ліміт {limit} грн.")
        return NeedsApproval(f"Сума повернення {amount} грн перевищує автоматичний ліміт {limit} грн.")

    if mode != "auto":
        raise ValueError(f"unknown permission mode {mode!r} for {action}")

    if action == "goodwill_exception":
        no_shows = ctx.client.no_show_count
        if perms.goodwill_requires_zero_no_shows and no_shows > 0:
            return NeedsApproval(
                f"У клієнта є неявки ({no_shows}), тому виняток з доброї волі потребує підтвердження людини."
            )
        used = goodwill_used_in_window(ctx.client, ctx.now)
        limit = perms.goodwill_per_client_per_180d
        if used >= limit:
            return NeedsApproval(
                f"Клієнт уже використав винятків за 180 днів: {used} з {limit}, тому потрібне підтвердження людини."
            )
        return Allow(f"Неявок немає, використано винятків за 180 днів {used} з {limit}, тож виняток дозволено.")

    return Allow("Дію дозволено політикою закладу без підтвердження.")
