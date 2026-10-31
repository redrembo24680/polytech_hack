import pytest

from agent.policy import Allow, Forbidden, NeedsApproval, PolicyContext, decide, is_late_change
from tests.conftest import NOW, booking, ctx, policy


def test_mode_forbidden_wins():
    assert isinstance(decide("waive_no_show_fee", ctx("denta", "anna", "b-anna-1")), Forbidden)


def test_mode_approval():
    assert isinstance(decide("cancel", ctx("denta", "petro", "b-petro-1")), NeedsApproval)


def test_refund_under_limit_allowed():
    assert isinstance(decide("refund", ctx("lumen", "olena", "b-olena-1", amount=500)), Allow)


def test_refund_over_limit_needs_approval():
    assert isinstance(decide("refund", ctx("lumen", "olena", "b-olena-1", amount=501)), NeedsApproval)


def test_goodwill_allowed_for_loyal_client():
    assert isinstance(decide("goodwill_exception", ctx("lumen", "olena", "b-olena-1")), Allow)


def test_goodwill_with_no_shows_needs_approval():
    d = decide("goodwill_exception", ctx("lumen", "max", "b-max-1"))
    assert isinstance(d, NeedsApproval) and "неявк" in d.reason


def test_goodwill_limit_reached_needs_approval():
    assert isinstance(decide("goodwill_exception", ctx("lumen", "ira", "b-ira-1")), NeedsApproval)


def test_reschedule_auto_allowed():
    assert isinstance(decide("reschedule", ctx("lumen", "olena", "b-olena-1")), Allow)


def test_escalate_always_allowed():
    assert isinstance(decide("escalate", ctx("denta", "anna", None)), Allow)


def test_is_late_change_true_within_window():
    assert is_late_change(policy("lumen"), booking("lumen", "b-olena-1"), NOW) is True


def test_is_late_change_false_outside_window():
    assert is_late_change(policy("lumen"), booking("lumen", "b-ira-1"), NOW) is False


@pytest.mark.parametrize(
    "action", ["reschedule", "cancel", "refund", "goodwill_exception", "waive_no_show_fee", "escalate"]
)
def test_every_decision_has_reason(action):
    assert decide(action, ctx("lumen", "olena", "b-olena-1", amount=100)).reason


def test_refund_without_amount_needs_approval():
    for amount in (None, 0, -5):
        d = decide("refund", ctx("lumen", "olena", "b-olena-1", amount=amount))
        assert isinstance(d, NeedsApproval) and "суму" in d.reason.lower()


@pytest.mark.parametrize(
    "action,field,value",
    [
        ("cancel", "cancel", "weird"),
        ("refund", "refund", "auto"),
        ("goodwill_exception", "goodwill_exception", "auto_under_limit"),
    ],
)
def test_unknown_mode_raises(action, field, value):
    c = ctx("lumen", "olena", "b-olena-1", amount=100)
    perms = c.policy.agent_permissions.model_copy(update={field: value})
    c = PolicyContext(
        policy=c.policy.model_copy(update={"agent_permissions": perms}),
        client=c.client, booking=c.booking, now=c.now, amount=c.amount,
    )
    with pytest.raises(ValueError, match="unknown permission mode"):
        decide(action, c)
