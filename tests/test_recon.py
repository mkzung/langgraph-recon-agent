import pytest

from langgraph_recon_agent import (
    build_recon,
    find_breaks,
    llm_router,
    parse_choice,
    reconcile,
    rule_router,
    score,
)
from langgraph_recon_agent.sample import BROKER, LABELS, LEDGER, rates, splits


def test_find_breaks():
    matched, breaks = find_breaks(BROKER, LEDGER)
    assert matched == ["T001"]
    assert [b["id"] for b in breaks] == sorted(LABELS)
    by_id = {b["id"]: b for b in breaks}
    assert by_id["T003"]["fields"] == ["price", "ccy"]
    assert by_id["T004"]["fields"] == ["qty", "price"]
    assert by_id["T006"]["ledger"] is None


def test_rule_router_reconciles_the_sample():
    final = reconcile(build_recon(rule_router, rates, splits), BROKER, LEDGER)
    resolved = {e["id"]: e["by"] for e in final["resolved"]}
    assert resolved == {"T002": "price", "T003": "fx", "T004": "split"}
    reasons = {e["id"]: e["reason"] for e in final["escalated"]}
    assert reasons == {
        "T005": "price check did not explain it",
        "T006": "on the broker side only",
        "T007": "router chose 'escalate'",
        "T008": "split check did not explain it",
        "T009": "fx check did not explain it",
    }
    s = score(final, LABELS)
    assert (s.correct, s.total, s.false_clears, s.missed_clears) == (8, 8, 0, 0)


@pytest.mark.parametrize("answer", ["price", "fx", "split", "escalate", "banana"])
def test_a_bad_router_never_clears_a_real_break(answer):
    final = reconcile(build_recon(lambda b: answer, rates, splits), BROKER, LEDGER)
    s = score(final, LABELS)
    assert s.false_clears == 0
    assert len(final["resolved"]) + len(final["escalated"]) == len(LABELS)


def test_ledger_only_trade_is_escalated():
    final = reconcile(build_recon(rule_router, rates, splits), [], LEDGER[:1])
    assert final["escalated"] == [{"id": "T001", "fields": [], "reason": "on the ledger side only"}]


def test_no_trades():
    final = reconcile(build_recon(rule_router, rates, splits), [], [])
    assert final["resolved"] == [] and final["escalated"] == [] and final["matched"] == []


class FlakyRates:
    def __init__(self, failures):
        self.failures = failures
        self.calls = 0

    def __call__(self, base, quote, date):
        self.calls += 1
        if self.calls <= self.failures:
            raise ConnectionError("rate service unavailable")
        return rates(base, quote, date)


def test_fx_node_is_retried():
    flaky = FlakyRates(failures=2)
    only_fx = [b for b in BROKER if b["id"] == "T003"]
    final = reconcile(build_recon(rule_router, flaky, splits), only_fx, LEDGER[2:3])
    assert flaky.calls == 3
    assert [e["id"] for e in final["resolved"]] == ["T003"]


def test_fx_failure_surfaces_after_the_last_attempt():
    flaky = FlakyRates(failures=5)
    only_fx = [b for b in BROKER if b["id"] == "T003"]
    with pytest.raises(ConnectionError):
        reconcile(build_recon(rule_router, flaky, splits, fx_attempts=2), only_fx, LEDGER[2:3])
    assert flaky.calls == 2


@pytest.mark.parametrize(
    "text, choice",
    [
        ("fx", "fx"),
        ("Split.", "split"),
        ("**price**", "price"),
        ("I think fx here", "fx"),
        ("no idea", "escalate"),
        ("", "escalate"),
    ],
)
def test_parse_choice(text, choice):
    assert parse_choice(text) == choice


class FakeModel:
    """Answers from the differing fields, the way a sensible model would."""

    def __init__(self):
        self.calls = 0

    def invoke(self, messages):
        import json

        self.calls += 1
        payload = json.loads(messages[-1][1])

        class Reply:
            content = f"Answer: {rule_router({'fields': payload['differs']})}"

        return Reply()


def test_llm_router_end_to_end():
    model = FakeModel()
    final = reconcile(build_recon(llm_router(model), rates, splits), BROKER, LEDGER)
    assert model.calls == 7  # every break except the one-sided T006
    assert score(final, LABELS).correct == 8


def test_zero_ledger_price_is_escalated():
    zero = [{**LEDGER[1], "price": 0.0}]
    final = reconcile(build_recon(rule_router, rates, splits), BROKER[1:2], zero)
    assert [e["id"] for e in final["escalated"]] == ["T002"]
