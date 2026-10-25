# langgraph-recon-agent

A LangGraph supervisor that reconciles broker fills against a trade ledger. Each break goes to a specialist that tries to explain it, and a break nobody can explain goes to a person.

The router, rules or a chat model, only picks who looks at a break. Clearing it takes a deterministic check. So a router that answers wrong every time still clears no real break, and the tests hold it to that.

```
START -> match -> triage <-> price
                    |  <---> fx      (RetryPolicy)
                    |  <---> split
                    v
                   END
```

- `match` pairs trades by id and queues every break, including trades on one side only.
- `triage` escalates one-sided breaks, asks the router about the rest, and hands over with `Command(goto=...)`.
- `price` clears a gap of at most 1 bp. `fx` clears a broker price in another currency at the day's rate. `split` clears quantity and price moved by a known split ratio.
- `fx` calls a rate source that can drop; the node runs under a `RetryPolicy`.

```python
from langgraph_recon_agent import build_recon, reconcile, rule_router, score
from langgraph_recon_agent.sample import BROKER, LABELS, LEDGER, rates, splits

final = reconcile(build_recon(rule_router, rates, splits), BROKER, LEDGER)
print(score(final, LABELS))
# ReconScore(correct=8, total=8, false_clears=0, missed_clears=0)
```

The sample day is invented: one exact match and eight breaks. A false clear is a real break the graph resolved. `llm_router(model)` puts a chat model in place of `rule_router`.

```bash
pip install -e ".[dev,llm]"
pytest -q   # offline, no API key
```

Apache-2.0.
