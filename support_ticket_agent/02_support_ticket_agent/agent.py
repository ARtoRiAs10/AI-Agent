"""
Customer Support Ticket Resolution Agent
=========================================
Given a support ticket, uses search_kb + get_order_status tools to gather
facts, reasons about whether it can resolve directly or must escalate, and
produces either a customer-facing resolution message or an escalation
summary for a human agent.

Run:
    export OPENROUTER_API_KEY=sk-or-v1-...   # optional, omit for mock mode (free key: https://openrouter.ai/keys)
    python agent.py
"""

import json
from dataclasses import dataclass
from llm_client import LLMClient
import mock_backend


# ---------------------------------------------------------------------------
# Tool schemas
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "name": "search_kb",
        "description": "Search the customer support knowledge base for relevant documentation/policy articles.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
    {
        "name": "get_order_status",
        "description": "Look up the current status, tracking, and history for a customer's order.",
        "input_schema": {
            "type": "object",
            "properties": {"order_id": {"type": "string"}},
            "required": ["order_id"],
        },
    },
    {
        "name": "get_customer_account",
        "description": "Look up account-level info for a customer: tier, refund history, prior tickets.",
        "input_schema": {
            "type": "object",
            "properties": {"customer_id": {"type": "string"}},
            "required": ["customer_id"],
        },
    },
    {
        "name": "issue_resolution",
        "description": ("Finalize the ticket. Call this exactly once, after gathering the facts you need, "
                         "with EITHER a direct resolution OR an escalation."),
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["resolve", "escalate"]},
                "customer_message": {
                    "type": "string",
                    "description": "Required if action=resolve. Friendly, complete message to send the customer.",
                },
                "escalation_summary": {
                    "type": "object",
                    "description": "Required if action=escalate.",
                    "properties": {
                        "reason": {"type": "string"},
                        "priority": {"type": "string", "enum": ["low", "medium", "high", "urgent"]},
                        "facts_gathered": {"type": "string"},
                        "suggested_next_step": {"type": "string"},
                    },
                },
            },
            "required": ["action"],
        },
    },
]

SYSTEM_PROMPT = """You are a customer support resolution agent for an e-commerce company.
Given a ticket, gather whatever facts you need (search the KB for policy,
look up order status, look up the account) BEFORE deciding.

Resolve directly yourself only if:
- The answer is clearly covered by KB policy, AND
- It doesn't require a refund/exception outside standard policy, AND
- The customer is not already escalated/angry about a repeat unresolved issue.

Escalate to a human agent if:
- It requires a policy exception, large refund, or judgment call
- The customer has multiple prior related tickets (pattern of failure)
- Information is contradictory or you cannot find enough to be confident
- The customer expresses strong dissatisfaction

Think step by step using the tools, then call issue_resolution exactly once
with your final decision. Be concrete: cite the actual order status / policy
you found, don't hand-wave."""


def make_tool_executor(collected: dict):
    def executor(name, tool_input):
        if name == "search_kb":
            return mock_backend.search_kb(tool_input.get("query", ""))
        if name == "get_order_status":
            return mock_backend.get_order_status(tool_input.get("order_id", ""))
        if name == "get_customer_account":
            return mock_backend.get_customer_account(tool_input.get("customer_id", ""))
        if name == "issue_resolution":
            collected["result"] = tool_input
            return "resolution recorded"
        return f"unknown tool {name}"
    return executor


@dataclass
class Ticket:
    ticket_id: str
    customer_id: str
    order_id: str
    subject: str
    body: str


def resolve_ticket(ticket: Ticket, llm: LLMClient):
    collected = {}
    executor = make_tool_executor(collected)
    user_msg = (
        f"Ticket ID: {ticket.ticket_id}\n"
        f"Customer ID: {ticket.customer_id}\n"
        f"Order ID: {ticket.order_id}\n"
        f"Subject: {ticket.subject}\n"
        f"Body: {ticket.body}\n"
    )
    final_text, transcript = llm.run_tool_loop(SYSTEM_PROMPT, user_msg, TOOLS, executor)

    result = collected.get("result")
    if result is None:
        # model finished without calling issue_resolution (can happen in mock mode) — fail safe to escalate
        result = {
            "action": "escalate",
            "escalation_summary": {
                "reason": "Agent did not produce a structured resolution; failing safe.",
                "priority": "medium",
                "facts_gathered": final_text,
                "suggested_next_step": "Human review required.",
            },
        }
    return result, transcript


SAMPLE_TICKETS = [
    Ticket(
        ticket_id="T-1001",
        customer_id="C-500",
        order_id="O-9001",
        subject="Where is my package?",
        body="Hi, I ordered a jacket 10 days ago and it still says 'processing'. Can you tell me what's going on?",
    ),
    Ticket(
        ticket_id="T-1002",
        customer_id="C-777",
        order_id="O-9002",
        subject="Refund for damaged item, 3rd time this month",
        body="This is the THIRD time I've had to contact you about a broken item this month. I want a full refund and I'm considering disputing the charge with my bank.",
    ),
]


if __name__ == "__main__":
    llm = LLMClient()
    all_results = []
    for t in SAMPLE_TICKETS:
        print("=" * 70)
        print(f"Ticket {t.ticket_id}: {t.subject}")
        result, transcript = resolve_ticket(t, llm)
        print("Tool calls:", [x["tool"] for x in transcript])
        print(json.dumps(result, indent=2))
        all_results.append({
            "ticket_id": t.ticket_id, "customer_id": t.customer_id, "order_id": t.order_id,
            "subject": t.subject, "body": t.body,
            "tool_calls": [x["tool"] for x in transcript],
            "resolution": result,
        })

    with open("tickets_result.json", "w") as f:
        json.dump(all_results, f, indent=2)
    print("\n[saved] tickets_result.json (used by dashboard.py)")
