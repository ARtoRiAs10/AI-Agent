# Support Ticket Resolution Agent

Given a ticket, the agent uses `search_kb`, `get_order_status`, and
`get_customer_account` tools to gather facts, reasons about whether it can
resolve directly per policy or must escalate to a human, then calls
`issue_resolution` exactly once with a structured decision.

## Files
- `agent.py` — tool schemas, system prompt, resolution loop, 2 sample tickets
- `mock_backend.py` — mock KB / order / CRM lookups (swap for real integrations)
- `llm_client.py` — shared OpenRouter (OpenAI-compatible) tool-use loop wrapper, defaults to a free model (mock fallback if no API key)

## Setup & run
```bash
pip install -r requirements.txt
export OPENROUTER_API_KEY=sk-or-v1-...   # optional — omit for offline mock mode; get a free key at https://openrouter.ai/keys
python agent.py
```

## Sample tickets included
1. Simple shipping delay -> resolvable directly against KB policy
2. Repeat damaged-item complaint from a customer with 3 prior tickets in 90
   days -> escalates per the "repeat claims" policy

## Output shape
```json
{
  "action": "resolve",
  "customer_message": "..."
}
```
or
```json
{
  "action": "escalate",
  "escalation_summary": {
    "reason": "...", "priority": "high",
    "facts_gathered": "...", "suggested_next_step": "..."
  }
}
```

## Visual dashboard (Streamlit)
A dashboard is included (`dashboard.py`) with charts built from plotly/pandas.
It reads the same result file the CLI agent writes, and also has a button to
re-run the agent for you.

```bash
python agent.py        # generates tickets_result.json (or use the sidebar button)
streamlit run dashboard.py
```
Then open the URL streamlit prints (usually http://localhost:8501).
