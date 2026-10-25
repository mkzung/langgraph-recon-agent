"""Pair broker fills with ledger bookings and list every disagreement.

Pairing is by trade id. A pair whose fields all agree is matched; anything
else, including a trade present on one side only, becomes a break.
"""

from __future__ import annotations

from typing import Any

Trade = dict[str, Any]
Break = dict[str, Any]

FIELDS = ("symbol", "side", "qty", "price", "ccy")


def find_breaks(broker: list[Trade], ledger: list[Trade]) -> tuple[list[str], list[Break]]:
    """Return the ids that match exactly and the breaks, in trade-id order."""
    by_id_broker = {t["id"]: t for t in broker}
    by_id_ledger = {t["id"]: t for t in ledger}
    matched, breaks = [], []
    for trade_id in sorted(by_id_broker.keys() | by_id_ledger.keys()):
        b, led = by_id_broker.get(trade_id), by_id_ledger.get(trade_id)
        if b is None or led is None:
            breaks.append({"id": trade_id, "broker": b, "ledger": led, "fields": []})
            continue
        diff = [f for f in FIELDS if b.get(f) != led.get(f)]
        if diff:
            breaks.append({"id": trade_id, "broker": b, "ledger": led, "fields": diff})
        else:
            matched.append(trade_id)
    return matched, breaks
