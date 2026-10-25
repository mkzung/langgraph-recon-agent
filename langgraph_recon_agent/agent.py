"""A supervisor graph that reconciles broker fills against a trade ledger.

``match`` pairs trades by id and queues every break. ``triage`` takes the next
break and asks a router (rules or a chat model) which specialist should try to
explain it, then hands over with ``Command(goto=...)``. Each specialist either
resolves the break with a reason or escalates it, and hands back to ``triage``.
A break that no specialist can explain is escalated, never cleared.

The ``fx`` node calls a rate source that can fail; it runs under a
``RetryPolicy`` so a dropped connection is retried by the graph.
"""

from __future__ import annotations

from collections.abc import Callable
from operator import add
from typing import Annotated, Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, RetryPolicy

from .matching import Break, Trade, find_breaks
from .specialists import RateSource, SplitSource, check_fx, check_price, check_split

SPECIALISTS = ("price", "fx", "split")
Router = Callable[[Break], str]


class ReconState(TypedDict, total=False):
    broker: list[Trade]
    ledger: list[Trade]
    matched: list[str]
    queue: list[Break]
    current: Break
    resolved: Annotated[list[dict[str, Any]], add]
    escalated: Annotated[list[dict[str, Any]], add]


def rule_router(brk: Break) -> str:
    """Route on which fields differ. The baseline any model has to beat."""
    fields = set(brk["fields"])
    if "ccy" in fields:
        return "fx"
    if "qty" in fields:
        return "split"
    if fields == {"price"}:
        return "price"
    return "escalate"


def build_recon(
    router: Router,
    rates: RateSource,
    splits: SplitSource,
    price_tol_bps: float = 1.0,
    fx_tol_bps: float = 5.0,
    fx_attempts: int = 3,
):
    """Compile the reconciliation graph.

    Args:
        router: ``break -> "price" | "fx" | "split" | "escalate"``. Any other
            answer escalates the break.
        rates: ``(base, quote, date) -> rate``; may raise ``ConnectionError``.
        splits: ``(symbol, date) -> ratio or None``.
        fx_attempts: how many times the graph runs ``fx`` before giving up.
    """

    def match(state: ReconState) -> dict:
        matched, breaks = find_breaks(state["broker"], state["ledger"])
        return {"matched": matched, "queue": breaks}

    def triage(state: ReconState) -> Command[Literal["price", "fx", "split", "triage", "__end__"]]:
        queue = state.get("queue", [])
        if not queue:
            return Command(goto=END)
        brk, rest = queue[0], queue[1:]
        if brk["broker"] is None or brk["ledger"] is None:
            side = "broker" if brk["ledger"] is None else "ledger"
            reason = f"on the {side} side only"
            return Command(
                goto="triage", update={"queue": rest, "escalated": [_entry(brk, reason)]}
            )
        choice = router(brk)
        if choice not in SPECIALISTS:
            reason = f"router chose {choice!r}"
            return Command(
                goto="triage", update={"queue": rest, "escalated": [_entry(brk, reason)]}
            )
        return Command(goto=choice, update={"queue": rest, "current": brk})

    def specialist(name: str, check: Callable[[Break], str | None]):
        def node(state: ReconState) -> Command[Literal["triage"]]:
            brk = state["current"]
            reason = check(brk)
            if reason is None:
                update = {"escalated": [_entry(brk, f"{name} check did not explain it")]}
            else:
                update = {"resolved": [_entry(brk, reason, by=name)]}
            return Command(goto="triage", update=update)

        return node

    graph = StateGraph(ReconState)
    graph.add_node("match", match)
    graph.add_node("triage", triage)
    graph.add_node("price", specialist("price", lambda b: check_price(b, price_tol_bps)))
    graph.add_node(
        "fx",
        specialist("fx", lambda b: check_fx(b, rates, fx_tol_bps)),
        retry_policy=RetryPolicy(
            max_attempts=fx_attempts, initial_interval=0.0, jitter=False, retry_on=ConnectionError
        ),
    )
    graph.add_node("split", specialist("split", lambda b: check_split(b, splits)))
    graph.add_edge(START, "match")
    graph.add_edge("match", "triage")
    return graph.compile()


def _entry(brk: Break, reason: str, by: str | None = None) -> dict[str, Any]:
    entry = {"id": brk["id"], "fields": brk["fields"], "reason": reason}
    if by:
        entry["by"] = by
    return entry


def reconcile(recon, broker: list[Trade], ledger: list[Trade]) -> ReconState:
    """Run the graph; the step limit grows with the number of trades."""
    limit = 4 * (len(broker) + len(ledger)) + 10
    return recon.invoke(
        {"broker": broker, "ledger": ledger, "resolved": [], "escalated": []},
        config={"recursion_limit": limit},
    )
