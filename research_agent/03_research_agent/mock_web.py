"""
Mock web search/fetch backend so the research agent is runnable offline.
Swap for real implementations, e.g.:
  - search_web -> Anthropic's web_search tool, Bing/Google/SerpAPI
  - fetch -> requests + trafilatura/readability extraction, or Anthropic's web_fetch tool
"""

_FAKE_INDEX = [
    {"title": "SEA Food Delivery Market Report 2026", "url": "https://example-research.com/sea-food-delivery-2026",
     "snippet": "The Southeast Asian online food delivery market is projected to grow at 14% CAGR through 2029, "
                "driven by Indonesia and Vietnam.",
     "body": "The Southeast Asian online food delivery market reached roughly $14B GMV in 2025 and is "
             "projected to grow at a 14% CAGR through 2029. Growth is concentrated in Indonesia, Vietnam, "
             "and the Philippines, where smartphone penetration is still rising. Grab and Foodpanda "
             "dominate share in most markets, with GoTo strong in Indonesia specifically."},
    {"title": "Grab vs Foodpanda: Competitive Landscape", "url": "https://example-research.com/grab-foodpanda-competitive",
     "snippet": "Grab holds an estimated 45% share across SEA delivery markets, Foodpanda ~25%, GoTo ~20%.",
     "body": "Grab is the regional leader with roughly 45% combined market share across food delivery in "
             "Southeast Asia, benefiting from its super-app ecosystem (rides, payments, delivery). Foodpanda "
             "(Delivery Hero) holds about 25% and has been retreating from smaller markets due to profitability "
             "pressure. GoTo (Gojek+Tokopedia) is strong specifically in Indonesia with ~20% national share. "
             "New entrants face very high customer acquisition costs and thin unit economics."},
    {"title": "Regulatory Notes: Gig Economy Rules in Vietnam & Indonesia", "url": "https://example-research.com/sea-gig-regulation",
     "snippet": "New driver classification rules in Indonesia (2025) require minimum earnings guarantees.",
     "body": "Indonesia introduced minimum earnings guarantees for gig delivery drivers in 2025, raising "
             "platform operating costs by an estimated 8-12%. Vietnam has proposed but not yet enacted similar "
             "rules. Cross-border data localization requirements also add compliance overhead for new entrants "
             "operating centralized tech stacks."},
]


def search_web(query: str):
    q = query.lower()
    scored = []
    for item in _FAKE_INDEX:
        score = sum(1 for w in q.split() if w in item["title"].lower() or w in item["snippet"].lower())
        scored.append((score, item))
    scored.sort(key=lambda x: -x[0])
    top = [item for score, item in scored if score > 0][:3] or [scored[0][1]]
    return [{"title": r["title"], "url": r["url"], "snippet": r["snippet"]} for r in top]


def fetch(url: str) -> str:
    for item in _FAKE_INDEX:
        if item["url"] == url:
            return item["body"]
    return f"[mock fetch] Could not retrieve content for {url}"
