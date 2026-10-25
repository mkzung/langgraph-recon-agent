"""Checks that try to explain one break each.

Every check returns an explanation string when the break is explained and
``None`` when it is not. A check never clears a break it cannot prove, so an
unexplained break always reaches a person.
"""

from __future__ import annotations

import math
from collections.abc import Callable

from .matching import Break

RateSource = Callable[[str, str, str], float]
SplitSource = Callable[[str, str], float | None]


def check_price(brk: Break, tol_bps: float = 1.0) -> str | None:
    """Explained when the only difference is a price within ``tol_bps``."""
    if brk["fields"] != ["price"]:
        return None
    b, led = brk["broker"]["price"], brk["ledger"]["price"]
    if not led:
        return None
    gap_bps = abs(b - led) / abs(led) * 1e4
    if gap_bps <= tol_bps:
        return f"price rounding, {gap_bps:.2f} bp"
    return None


def check_fx(brk: Break, rates: RateSource, tol_bps: float = 5.0) -> str | None:
    """Explained when the broker priced in another currency at the day's rate.

    ``rates(base, quote, date)`` gives units of quote per unit of base. It may
    raise ``ConnectionError``; the graph retries the node, not this function.
    """
    if not set(brk["fields"]) <= {"price", "ccy"} or "ccy" not in brk["fields"]:
        return None
    b, led = brk["broker"], brk["ledger"]
    if not led["price"]:
        return None
    rate = rates(b["ccy"], led["ccy"], b["date"])
    converted = b["price"] * rate
    gap_bps = abs(converted - led["price"]) / abs(led["price"]) * 1e4
    if gap_bps <= tol_bps:
        return f"broker priced in {b['ccy']}, {b['ccy']}{led['ccy']} {rate:g}"
    return None


def check_split(brk: Break, splits: SplitSource) -> str | None:
    """Explained when quantity and price both moved by a known split ratio."""
    if set(brk["fields"]) != {"qty", "price"}:
        return None
    b, led = brk["broker"], brk["ledger"]
    ratio = splits(b["symbol"], b["date"])
    if not ratio:
        return None
    qty_ok = math.isclose(b["qty"], led["qty"] * ratio, rel_tol=1e-9)
    notional_ok = math.isclose(b["qty"] * b["price"], led["qty"] * led["price"], rel_tol=1e-6)
    if qty_ok and notional_ok:
        return f"{ratio:g}-for-1 split on {b['symbol']} not applied to the ledger"
    return None
