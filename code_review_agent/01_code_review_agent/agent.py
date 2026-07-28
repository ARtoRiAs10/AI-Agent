"""
Code Review Agent
==================
Takes a GitHub PR diff, autonomously decides which changed files need a deep
investigation (with tool calls to fetch extra file context) vs a quick pass,
reasons step by step about bugs / security / style, and outputs structured
inline review comments with severity levels.

Run:
    export OPENROUTER_API_KEY=sk-or-v1-...   # optional, omit to run in mock mode (free key: https://openrouter.ai/keys)
    python agent.py sample_pr.diff
"""

import sys
import json
import re
from dataclasses import dataclass, field
from llm_client import LLMClient
import mock_repo


# ---------------------------------------------------------------------------
# 1. Diff parsing
# ---------------------------------------------------------------------------

@dataclass
class FileDiff:
    path: str
    hunks: list = field(default_factory=list)   # raw hunk text blocks
    added_lines: int = 0
    removed_lines: int = 0
    raw: str = ""


def parse_unified_diff(diff_text: str):
    """Very small unified-diff parser: splits into per-file diffs and counts
    added/removed lines (used for the triage heuristic)."""
    files = []
    current = None
    for line in diff_text.splitlines():
        if line.startswith("diff --git"):
            if current:
                files.append(current)
            m = re.search(r"b/(\S+)$", line)
            path = m.group(1) if m else "unknown"
            current = FileDiff(path=path)
        if current is None:
            continue
        current.raw += line + "\n"
        if line.startswith("+") and not line.startswith("+++"):
            current.added_lines += 1
        elif line.startswith("-") and not line.startswith("---"):
            current.removed_lines += 1
    if current:
        files.append(current)
    return files


# ---------------------------------------------------------------------------
# 2. Triage heuristic — decide quick pass vs deep investigation
# ---------------------------------------------------------------------------

SENSITIVE_PATTERNS = [
    r"auth", r"login", r"password", r"token", r"secret", r"crypto",
    r"payment", r"sql", r"query", r"exec\(", r"eval\(", r"pickle",
    r"deserialize", r"admin", r"permission", r"session",
]


def needs_deep_investigation(fd: FileDiff) -> bool:
    size_signal = (fd.added_lines + fd.removed_lines) > 40
    sensitive_signal = any(re.search(p, fd.raw, re.IGNORECASE) for p in SENSITIVE_PATTERNS)
    extension_signal = fd.path.endswith((".py", ".js", ".ts", ".go", ".java", ".rb"))
    return extension_signal and (size_signal or sensitive_signal)


# ---------------------------------------------------------------------------
# 3. Tools available to the deep-investigation agent
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "name": "get_file_content",
        "description": "Fetch the full current content of a file in the repository, for context beyond the diff hunk.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Repo-relative file path"}},
            "required": ["path"],
        },
    },
    {
        "name": "get_file_blame_summary",
        "description": "Get a short history summary (recent authors/commits) for a file, useful to judge risk of touching shared/critical code.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
    {
        "name": "search_repo",
        "description": "Search the repository for a symbol/string (e.g. to find all callers of a changed function).",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
    {
        "name": "submit_review_comments",
        "description": "Submit the final structured list of inline review comments for this file. Call this exactly once when your analysis is complete.",
        "input_schema": {
            "type": "object",
            "properties": {
                "comments": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "line_hint": {"type": "string", "description": "line number or nearby code snippet"},
                            "severity": {"type": "string", "enum": ["blocker", "high", "medium", "low", "nit"]},
                            "category": {"type": "string", "enum": ["bug", "security", "style", "performance", "maintainability"]},
                            "comment": {"type": "string"},
                        },
                        "required": ["line_hint", "severity", "category", "comment"],
                    },
                }
            },
            "required": ["comments"],
        },
    },
]


def make_tool_executor(path: str, collected: list):
    def executor(name, tool_input):
        if name == "get_file_content":
            return mock_repo.get_file_content(tool_input.get("path", path))
        if name == "get_file_blame_summary":
            return mock_repo.get_blame_summary(tool_input.get("path", path))
        if name == "search_repo":
            return mock_repo.search_repo(tool_input.get("query", ""))
        if name == "submit_review_comments":
            collected.extend(tool_input.get("comments", []))
            return "ok, comments recorded"
        return f"unknown tool {name}"
    return executor


DEEP_SYSTEM_PROMPT = """You are a senior code reviewer AI. You have been given the diff for ONE file
from a pull request. Investigate as deeply as needed using the available tools
(fetch full file content, check blame/history, search the repo for callers)
before forming an opinion — don't guess about code you haven't looked at.

Reason step by step about:
1. Correctness bugs (off-by-one, null/None handling, race conditions, wrong logic)
2. Security vulnerabilities (injection, auth bypass, unsafe deserialization,
   secrets in code, missing input validation)
3. Style / maintainability violations relative to the rest of the codebase

When you are done, call submit_review_comments exactly once with the full
structured list of findings (can be empty if the file is clean). Only flag
real, specific issues tied to lines in the diff — do not pad with generic
advice."""

QUICK_SYSTEM_PROMPT = """You are a code reviewer AI doing a QUICK PASS over a small, low-risk diff hunk.
Do not use tools. Just read the diff and flag anything clearly wrong (bugs,
obvious style issues). Respond with ONLY a JSON array of objects with keys:
line_hint, severity (blocker/high/medium/low/nit), category
(bug/security/style/performance/maintainability), comment. If nothing is
wrong, respond with []."""


def review_file_deep(llm: LLMClient, fd: FileDiff):
    collected = []
    executor = make_tool_executor(fd.path, collected)
    user_msg = f"File: {fd.path}\n\nDiff:\n{fd.raw}"
    final_text, transcript = llm.run_tool_loop(DEEP_SYSTEM_PROMPT, user_msg, TOOLS, executor)
    return collected, transcript


def review_file_quick(llm: LLMClient, fd: FileDiff):
    user_msg = f"File: {fd.path}\n\nDiff:\n{fd.raw}"
    text = llm.complete(QUICK_SYSTEM_PROMPT, user_msg)
    try:
        start = text.index("[")
        end = text.rindex("]") + 1
        return json.loads(text[start:end])
    except Exception:
        return []


# ---------------------------------------------------------------------------
# 4. Orchestration
# ---------------------------------------------------------------------------

def review_pr(diff_text: str):
    llm = LLMClient()
    files = parse_unified_diff(diff_text)
    report = {"files": []}

    for fd in files:
        deep = needs_deep_investigation(fd)
        mode = "deep_investigation" if deep else "quick_pass"
        print(f"[triage] {fd.path}: +{fd.added_lines}/-{fd.removed_lines} lines -> {mode}")

        if deep:
            comments, transcript = review_file_deep(llm, fd)
            tool_calls = [t["tool"] for t in transcript]
        else:
            comments = review_file_quick(llm, fd)
            tool_calls = []

        report["files"].append({
            "path": fd.path,
            "review_mode": mode,
            "tool_calls_made": tool_calls,
            "comments": comments,
        })

    return report


if __name__ == "__main__":
    diff_path = sys.argv[1] if len(sys.argv) > 1 else "sample_pr.diff"
    with open(diff_path) as f:
        diff_text = f.read()

    result = review_pr(diff_text)
    print("\n" + "=" * 70)
    print(json.dumps(result, indent=2))

    with open("review_result.json", "w") as f:
        json.dump(result, f, indent=2)
    print("\n[saved] review_result.json (used by dashboard.py)")
