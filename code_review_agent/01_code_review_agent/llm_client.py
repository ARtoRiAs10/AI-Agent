"""
llm_client.py
Shared LLM wrapper used across all agent projects — backed by OpenRouter
(https://openrouter.ai), which gives free access to several open models
through a single OpenAI-compatible API. No code in the individual projects
needs to change: they still call llm.complete(...) and
llm.run_tool_loop(...) with Anthropic-style tool schemas
({"name", "description", "input_schema"}); this file converts those to
OpenAI's `tools` format under the hood before calling OpenRouter.

Setup:
    1. Create a free account at https://openrouter.ai and generate an API key
       at https://openrouter.ai/keys
    2. export OPENROUTER_API_KEY=sk-or-v1-...
    3. (optional) export OPENROUTER_MODEL=... to override the default free model

If OPENROUTER_API_KEY is not set, this falls back to a deterministic MOCK
mode so every project still runs end-to-end with zero setup.

Install: pip install requests

Notes on free models & tool calling:
  OpenRouter's free tier includes models like:
    - meta-llama/llama-3.3-70b-instruct:free   (default — solid tool-calling support)
    - qwen/qwen-2.5-72b-instruct:free
    - google/gemini-2.0-flash-exp:free
    - mistralai/mistral-small-3.1-24b-instruct:free
  Free-tier models are rate-limited and availability changes over time; if a
  model errors out or its tool-calling is unreliable, set OPENROUTER_MODEL to
  try another one from https://openrouter.ai/models?max_price=0
"""

import os
import json
import requests

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = os.environ.get("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct:free")


class LLMClient:
    def __init__(self, model: str = None):
        self.model = model or DEFAULT_MODEL
        self.api_key = os.environ.get("OPENROUTER_API_KEY")
        self.mock = self.api_key is None

    def _headers(self):
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/anthropic-agent-examples",
            "X-Title": "Agentic System Examples",
        }

    @staticmethod
    def _to_openai_tools(tools: list) -> list:
        """Convert Anthropic-style tool schemas to OpenAI/OpenRouter's `tools` format."""
        return [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "parameters": t.get("input_schema", {"type": "object", "properties": {}}),
                },
            }
            for t in tools
        ]

    def _post(self, payload: dict) -> dict:
        resp = requests.post(OPENROUTER_URL, headers=self._headers(), json=payload, timeout=90)
        if resp.status_code >= 400:
            raise RuntimeError(f"OpenRouter API error {resp.status_code}: {resp.text[:500]}")
        return resp.json()

    # ---------- simple, no-tool call ----------
    def complete(self, system: str, user: str, max_tokens: int = 1500) -> str:
        if self.mock:
            return self._mock_text(system, user)
        data = self._post({
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "max_tokens": max_tokens,
        })
        try:
            return data["choices"][0]["message"].get("content") or ""
        except (KeyError, IndexError):
            return ""

    # ---------- full tool-use agent loop ----------
    def run_tool_loop(self, system: str, user: str, tools: list, tool_executor,
                       max_turns: int = 8, max_tokens: int = 2000):
        """
        tools: list of Anthropic-style tool schemas (dicts with name/description/input_schema)
        tool_executor: callable(name:str, input:dict) -> str (tool result)
        Returns (final_text:str, transcript:list[dict]) logging every tool call
        made and its result, for auditing/display.
        """
        if self.mock:
            return self._mock_tool_loop(system, user, tools, tool_executor)

        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        openai_tools = self._to_openai_tools(tools)
        transcript = []

        for _ in range(max_turns):
            data = self._post({
                "model": self.model,
                "messages": messages,
                "tools": openai_tools,
                "max_tokens": max_tokens,
            })
            choice = data["choices"][0]
            msg = choice["message"]
            tool_calls = msg.get("tool_calls")

            if not tool_calls:
                return msg.get("content") or "", transcript

            messages.append(msg)
            for tc in tool_calls:
                fn = tc.get("function", {})
                name = fn.get("name", "")
                try:
                    args = json.loads(fn.get("arguments") or "{}")
                except Exception:
                    args = {}
                result = tool_executor(name, args)
                transcript.append({"tool": name, "input": args, "result": result})
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.get("id", ""),
                    "content": str(result),
                })

        return "[max_turns reached without final answer]", transcript

    # ---------- offline mock fallbacks (no API key needed) ----------
    def _mock_text(self, system, user):
        return (f"[MOCK LLM RESPONSE — set OPENROUTER_API_KEY for real output]\n"
                f"System focus: {system[:120]}...\n"
                f"Given input, a reasonable placeholder analysis/decision was generated.")

    def _mock_tool_loop(self, system, user, tools, tool_executor):
        transcript = []
        for t in tools:
            props = t.get("input_schema", {}).get("properties", {})
            fake_input = {}
            for k, v in props.items():
                if v.get("type") == "string":
                    fake_input[k] = "example"
                elif v.get("type") == "integer":
                    fake_input[k] = 1
                elif v.get("type") == "array":
                    fake_input[k] = []
                else:
                    fake_input[k] = None
            try:
                result = tool_executor(t["name"], fake_input)
            except Exception as e:
                result = f"[mock tool call error: {e}]"
            transcript.append({"tool": t["name"], "input": fake_input, "result": result})

        final_text = ("[MOCK MODE] Ran available tools once each for demonstration. "
                       "Set OPENROUTER_API_KEY (get one free at https://openrouter.ai/keys) to get "
                       "real multi-step reasoning and properly-targeted tool calls instead of this placeholder.")
        return final_text, transcript
