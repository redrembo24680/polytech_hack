"""Картки, які модель показує через show_card: pydantic-схеми, валідація і JSON-схема для Gemini."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, ValidationError


class SlotOption(BaseModel):
    id: str = Field(description="Номер варіанта: 1, 2, 3")
    start: str = Field(description="Початок слоту, ISO 8601 з часовим поясом, як у find_slots")
    staff_id: str = Field(description="Ідентифікатор майстра з find_slots")
    staff_name: str = Field(description="Ім'я майстра")
    label: str = Field(description="Підпис кнопки, напр. «пн, 2 лист., 14:00 — Марія»")


class SlotsCard(BaseModel):
    type: Literal["slots"]
    title: str = Field(description="Заголовок картки")
    options: list[SlotOption] = Field(description="Слоти (лише для slots)")


class PrepaymentInfo(BaseModel):
    amount: int = Field(description="Сума передоплати, грн")
    status: str = Field(description="held, refunded, forfeited або none")


class TimelineItem(BaseModel):
    ts: str = Field(description="Час події, ISO 8601")
    event: str = Field(description="Що сталося")


class BookingSummaryCard(BaseModel):
    type: Literal["booking_summary"]
    booking_id: str = Field(description="Ідентифікатор бронювання (лише для booking_summary)")
    service: str = Field(description="Назва послуги")
    staff: str = Field(description="Ім'я майстра")
    start: str = Field(description="Початок візиту, ISO 8601 з часовим поясом")
    prepayment: PrepaymentInfo = Field(description="Передоплата")
    status: str = Field(description="Статус бронювання: scheduled, cancelled, completed або no_show")
    timeline: list[TimelineItem] = Field(default_factory=list, description="Історія змін бронювання")


class DecisionCard(BaseModel):
    type: Literal["decision"]
    title: str = Field(description="Заголовок картки")
    outcome: str = Field(description="Підсумок рішення одним реченням (лише для decision)")
    reasoning: list[str] = Field(description="Чому так вирішено, по пунктах")
    actions_taken: list[str] = Field(description="Що вже зроблено, по пунктах")


CARD_MODELS: dict[str, type[BaseModel]] = {
    "slots": SlotsCard, "booking_summary": BookingSummaryCard, "decision": DecisionCard,
}


def parse_card(card: dict) -> BaseModel:
    """Валідує картку моделі; ValueError з українським повідомленням, якщо вона некоректна."""
    if not isinstance(card, dict):
        raise ValueError("Картка має бути об'єктом із полем type.")
    kind = card.get("type")
    model = CARD_MODELS.get(kind) if isinstance(kind, str) else None
    if model is None:
        raise ValueError(f"Невідомий тип картки {kind!r}: очікується slots, booking_summary або decision.")
    try:
        return model.model_validate(card)
    except ValidationError as e:
        fields = ", ".join(".".join(str(x) for x in err["loc"]) for err in e.errors())
        raise ValueError(f"Картка {kind} некоректна, перевірте поля: {fields}.") from None


_GEMINI_KEYS = {"type", "properties", "required", "items", "enum", "description", "nullable"}


def _clean(node: dict, defs: dict) -> dict:
    """Inline $ref and keep only the keys Gemini's Schema accepts."""
    if "$ref" in node:
        node = defs[node["$ref"].rsplit("/", 1)[-1]]
    out: dict = {}
    for key, value in node.items():
        if key == "properties":
            out[key] = {name: _clean(sub, defs) for name, sub in value.items()}
        elif key == "items":
            out[key] = _clean(value, defs)
        elif key in _GEMINI_KEYS:
            out[key] = value
    return out


def card_json_schema() -> dict:
    """One OBJECT schema for the `card` argument: the union of the three card models' fields."""
    props: dict = {}
    for model in CARD_MODELS.values():
        raw = model.model_json_schema()
        cleaned = _clean(raw, raw.get("$defs", {}))
        for name, sub in cleaned["properties"].items():
            if name != "type":
                props.setdefault(name, sub)
    props = {"type": {"type": "string", "enum": list(CARD_MODELS), "description": "Тип картки"}, **props}
    return {
        "type": "object",
        "description": (
            "Картка. slots: type, title, options[{id, start, staff_id, staff_name, label}]. "
            "booking_summary: type, booking_id, service, staff, start, prepayment{amount, status}, status, "
            "timeline[{ts, event}]. decision: type, title, outcome, reasoning[], actions_taken[]."
        ),
        "properties": props,
        "required": ["type"],
    }


def _when(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso).strftime("%d.%m %H:%M")
    except ValueError:
        return iso


def card_to_text(card: dict) -> str:
    kind = card.get("type")
    if kind == "slots":
        lines = ["Вільні варіанти:"]
        for i, o in enumerate(card.get("options") or [], 1):
            lines.append(f'{o.get("id") or i}) {_when(o["start"])} — {o["staff_name"]}')
        lines.append("Напишіть номер варіанта.")
        return "\n".join(lines)
    if kind == "booking_summary":
        p = card["prepayment"]
        return (f'{card["service"]}, {card["staff"]}, {_when(card["start"])}, '
                f'передоплата {p["amount"]} грн ({p["status"]})')
    return f'✅ {card["title"]}\n{card["outcome"]}'
