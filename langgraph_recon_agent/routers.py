"""A router backed by a chat model, for comparison with ``rule_router``."""

from __future__ import annotations

import json
from collections.abc import Callable

from .matching import Break

SYSTEM = (
    "You triage breaks in a trade reconciliation. You see one trade as the broker "
    "reported it and as the ledger booked it, and the fields that differ. Answer "
    "with one word: price (small price difference, likely rounding), fx (the two "
    "sides use different currencies), split (quantity and price moved together, "
    "likely a stock split), or escalate (anything else)."
)

CHOICES = ("price", "fx", "split", "escalate")


def parse_choice(text: str) -> str:
    """The first known choice word in the reply, else ``"escalate"``."""
    words = [w.strip(".,:;\"'`*").lower() for w in (text or "").split()]
    return next((w for w in words if w in CHOICES), "escalate")


def llm_router(model, system: str = SYSTEM) -> Callable[[Break], str]:
    def router(brk: Break) -> str:
        human = json.dumps(
            {"broker": brk["broker"], "ledger": brk["ledger"], "differs": brk["fields"]},
            sort_keys=True,
        )
        response = model.invoke([("system", system), ("human", human)])
        content = getattr(response, "content", response)
        return parse_choice(content if isinstance(content, str) else str(content))

    return router
