"""An invented day of trades with one break of each kind, and their labels."""

DATE = "2026-10-23"


def _t(id, symbol, side, qty, price, ccy="USD"):
    return {
        "id": id,
        "symbol": symbol,
        "side": side,
        "qty": qty,
        "price": price,
        "ccy": ccy,
        "date": DATE,
    }


LEDGER = [
    _t("T001", "NWR", "buy", 500, 42.10),
    _t("T002", "NWR", "sell", 300, 101.23),
    _t("T003", "LYN", "buy", 150, 99.36),
    _t("T004", "KST", "buy", 100, 100.00),
    _t("T005", "KST", "sell", 80, 51.10),
    _t("T007", "NWR", "buy", 60, 42.20),
    _t("T008", "LYN", "sell", 100, 98.00),
    _t("T009", "LYN", "buy", 40, 105.00),
]

BROKER = [
    _t("T001", "NWR", "buy", 500, 42.10),
    _t("T002", "NWR", "sell", 300, 101.2345),  # rounding
    _t("T003", "LYN", "buy", 150, 92.00, "EUR"),  # priced in EUR at 1.08
    _t("T004", "KST", "buy", 200, 50.00),  # 2-for-1 split
    _t("T005", "KST", "sell", 80, 55.10),  # wrong price
    _t("T006", "NWR", "buy", 25, 42.15),  # never booked
    _t("T007", "NWR", "sell", 60, 42.20),  # wrong side
    _t("T008", "LYN", "sell", 1000, 98.00),  # extra zero
    _t("T009", "LYN", "buy", 40, 92.00, "EUR"),  # EUR, but the ledger price is wrong
]

LABELS = {
    "T002": "price",
    "T003": "fx",
    "T004": "split",
    "T005": "escalate",
    "T006": "escalate",
    "T007": "escalate",
    "T008": "escalate",
    "T009": "escalate",
}

RATES = {("EUR", "USD", DATE): 1.08}
SPLITS = {("KST", DATE): 2.0}


def rates(base: str, quote: str, date: str) -> float:
    return RATES[(base, quote, date)]


def splits(symbol: str, date: str) -> float | None:
    return SPLITS.get((symbol, date))
