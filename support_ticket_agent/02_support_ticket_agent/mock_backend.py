"""
Mock backend for the support agent's tools. Replace with real integrations:
  - search_kb -> vector search / Zendesk Guide / Confluence API
  - get_order_status -> internal Orders service / Shopify API
  - get_customer_account -> CRM (Salesforce/HubSpot) or internal account service
"""

_KB = {
    "shipping delay": "Policy: Orders show 'processing' for up to 3 business days before shipping. "
                       "If processing >5 business days, offer a $10 credit and expedited shipping.",
    "refund": "Policy: Standard refunds for damaged/defective items are approved automatically for "
              "first-time claims. Repeat claims (2+ in 90 days) must be escalated to a human agent "
              "for fraud/quality review.",
    "return window": "Policy: Items can be returned within 30 days of delivery for a full refund.",
}

_ORDERS = {
    "O-9001": {"status": "processing", "days_in_status": 10, "carrier": "UPS", "expected_ship_by": "was 3 days ago"},
    "O-9002": {"status": "delivered", "days_in_status": 2, "carrier": "FedEx", "note": "customer reports item arrived damaged"},
}

_ACCOUNTS = {
    "C-500": {"tier": "standard", "prior_tickets_90d": 0, "refunds_90d": 0},
    "C-777": {"tier": "standard", "prior_tickets_90d": 3, "refunds_90d": 2, "note": "repeat damaged-item complaints"},
}


def search_kb(query: str) -> str:
    q = query.lower()
    hits = [text for key, text in _KB.items() if any(w in q for w in key.split())]
    if not hits:
        return "[KB] No directly relevant policy article found."
    return "[KB] " + " | ".join(hits)


def get_order_status(order_id: str) -> str:
    o = _ORDERS.get(order_id)
    if not o:
        return f"[Orders] No order found with id {order_id}"
    return f"[Orders] {order_id}: {json_str(o)}"


def get_customer_account(customer_id: str) -> str:
    a = _ACCOUNTS.get(customer_id)
    if not a:
        return f"[CRM] No account found with id {customer_id}"
    return f"[CRM] {customer_id}: {json_str(a)}"


def json_str(d):
    import json
    return json.dumps(d)
