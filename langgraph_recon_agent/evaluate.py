"""Score a reconciliation against labelled breaks.

The label for each break id is the specialist that should explain it, or
``"escalate"`` for a break a person has to fix. A false clear (a break labelled
``"escalate"`` that the graph resolved) is counted on its own, because in a
back office it is the expensive mistake.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReconScore:
    correct: int
    total: int
    false_clears: int
    missed_clears: int

    @property
    def accuracy(self) -> float:
        return self.correct / self.total if self.total else 0.0


def score(final: dict, labels: dict[str, str]) -> ReconScore:
    outcome = {e["id"]: e.get("by", "escalate") for e in final.get("resolved", [])}
    outcome.update({e["id"]: "escalate" for e in final.get("escalated", [])})
    correct = sum(outcome.get(i) == want for i, want in labels.items())
    false_clears = sum(
        want == "escalate" and outcome.get(i) != "escalate" for i, want in labels.items()
    )
    missed = sum(want != "escalate" and outcome.get(i) == "escalate" for i, want in labels.items())
    return ReconScore(correct, len(labels), false_clears, missed)
