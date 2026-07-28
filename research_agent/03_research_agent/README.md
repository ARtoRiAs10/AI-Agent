# Research Agent (Plan -> Execute -> Reflect)

Takes an open-ended business question and runs the full loop:

1. **Plan**: LLM generates 4-7 concrete sub-questions
2. **Execute**: for each sub-question, an agent loop calls `search_web` then
   `fetch` on promising URLs, and extracts a cited answer
3. **Reflect**: tracks answered vs missing sub-questions; if gaps remain,
   revises the plan (rephrases unanswered sub-questions from a different
   angle) and re-runs execution, up to `max_replan_cycles`
4. **Compile**: writes a structured, cited markdown report with an executive
   summary and recommendation

## Files
- `agent.py` — the full plan/execute/reflect loop + report compilation
- `mock_web.py` — mock search/fetch backend (swap for real search API / Anthropic web_search+web_fetch)
- `llm_client.py` — shared OpenRouter (OpenAI-compatible) tool-use loop wrapper, defaults to a free model (mock fallback if no API key)

## Setup & run
```bash
pip install -r requirements.txt
export OPENROUTER_API_KEY=sk-or-v1-...   # optional — omit for offline mock mode; get a free key at https://openrouter.ai/keys
python agent.py "Should we enter the Southeast Asian food delivery market?"
```

Output is printed to stdout and also saved to `report.md`.

## Visual dashboard (Streamlit)
A dashboard is included (`dashboard.py`) with charts built from plotly/pandas.
It reads the same result file the CLI agent writes, and also has a button to
re-run the agent for you.

```bash
python agent.py "Should we enter the Southeast Asian food delivery market?"   # generates research_result.json
streamlit run dashboard.py
```
Then open the URL streamlit prints (usually http://localhost:8501).
