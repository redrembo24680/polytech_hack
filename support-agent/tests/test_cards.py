import pytest

from agent.cards import BookingSummaryCard, DecisionCard, SlotsCard, card_json_schema, parse_card

SLOTS = {"type": "slots", "title": "Вільні слоти", "options": [
    {"id": "1", "start": "2026-11-02T14:00:00+02:00", "staff_id": "st-maria", "staff_name": "Марія",
     "label": "Пн, 14:00 — Марія"}]}
SUMMARY = {"type": "booking_summary", "booking_id": "b-1", "service": "Стрижка", "staff": "Марія",
           "start": "2026-11-02T14:00:00+02:00", "prepayment": {"amount": 500, "status": "held"},
           "status": "scheduled", "timeline": [{"ts": "2026-10-31T12:00:00+02:00", "event": "rescheduled"}]}
DECISION = {"type": "decision", "title": "Запис перенесено", "outcome": "Передоплата збережена",
            "reasoning": ["Постійна клієнтка без неявок"], "actions_taken": ["Перенесено на пн 14:00"]}


@pytest.mark.parametrize("raw,model", [(SLOTS, SlotsCard), (SUMMARY, BookingSummaryCard), (DECISION, DecisionCard)])
def test_parse_card_valid(raw, model):
    card = parse_card(raw)
    assert isinstance(card, model) and card.model_dump(mode="json") == raw


def test_parse_card_unknown_type_is_ukrainian_value_error():
    with pytest.raises(ValueError, match="Невідомий тип картки"):
        parse_card({"type": "poster"})
    with pytest.raises(ValueError, match="об'єктом"):
        parse_card(["slots"])


def test_parse_card_missing_field_names_it():
    bad = {**SLOTS, "options": [{"id": "1", "start": "x", "staff_id": "s", "staff_name": "n"}]}
    with pytest.raises(ValueError, match=r"options\.0\.label"):
        parse_card(bad)
    with pytest.raises(ValueError, match="reasoning"):
        parse_card({**DECISION, "reasoning": "не список"})


def test_parse_card_drops_unknown_keys():
    assert "extra" not in parse_card({**DECISION, "extra": 1}).model_dump()


ALLOWED = {"type", "properties", "required", "items", "enum", "description", "nullable"}


def _walk(schema):
    assert set(schema) <= ALLOWED, set(schema) - ALLOWED
    for sub in schema.get("properties", {}).values():
        _walk(sub)
    if "items" in schema:
        _walk(schema["items"])


def test_card_json_schema_is_gemini_compatible():
    s = card_json_schema()
    _walk(s)
    assert s["type"] == "object" and s["required"] == ["type"]
    assert s["properties"]["type"]["enum"] == ["slots", "booking_summary", "decision"]
    opt = s["properties"]["options"]["items"]
    assert set(opt["required"]) == {"id", "start", "staff_id", "staff_name", "label"}
    assert s["properties"]["prepayment"]["properties"]["amount"]["type"] == "integer"
    assert s["properties"]["reasoning"] == {"type": "array", "items": {"type": "string"},
                                            "description": s["properties"]["reasoning"]["description"]}
