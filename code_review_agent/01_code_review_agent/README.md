# Code Review Agent

Takes a GitHub PR diff, triages each changed file into **quick pass** or
**deep investigation**, and for deep-investigation files gives the LLM tools
to fetch full file content, blame history, and repo-wide search before it
produces structured, severity-tagged inline review comments.

## How it decides deep vs quick
`needs_deep_investigation()` in `agent.py` flags a file for deep review if it's
a source file (`.py/.js/.ts/.go/.java/.rb`) AND either the diff is large
(>40 changed lines) or it touches security-sensitive keywords (auth, sql,
token, eval, etc). Everything else gets a fast single-shot pass with no tools.

## Files
- `agent.py` — diff parser, triage heuristic, deep/quick review loops, orchestration
- `mock_repo.py` — stand-in for the GitHub API (file content / blame / search).
  Swap for real GitHub REST/GraphQL calls in production.
- `llm_client.py` — shared OpenRouter (OpenAI-compatible) tool-use loop wrapper, defaults to a free model (mock fallback if no API key)
- `sample_pr.diff` — example PR diff to test on (touches auth, SQL, and a style-only file)

## Setup & run
```bash
pip install -r requirements.txt
export OPENROUTER_API_KEY=sk-or-v1-...   # optional — omit to run in offline mock mode; get a free key at https://openrouter.ai/keys
python agent.py sample_pr.diff
```

Try it on your own diff:
```bash
git diff main..feature-branch > my_pr.diff
python agent.py my_pr.diff
```

## Output
JSON report with, per file: which review mode was used, which tools were
called (for deep files), and a list of `{line_hint, severity, category, comment}`
review comments — ready to post as inline PR comments via the GitHub API.

## Visual dashboard (Streamlit)
A dashboard is included (`dashboard.py`) with charts built from plotly/pandas.
It reads the same result file the CLI agent writes, and also has a button to
re-run the agent for you.

```bash
python agent.py sample_pr.diff        # generates review_result.json (or use the sidebar button)
streamlit run dashboard.py
```
Then open the URL streamlit prints (usually http://localhost:8501).
