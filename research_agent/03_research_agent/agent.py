"""
Research Agent (Plan -> Execute -> Reflect loop)
=================================================
Takes an open-ended business question, generates a research plan of
sub-questions, iteratively searches the web + fetches sources, tracks what's
answered vs missing, revises the plan if gaps remain, and compiles a cited
markdown report.

Run:
    export OPENROUTER_API_KEY=sk-or-v1-...   # optional, omit for mock mode (free key: https://openrouter.ai/keys)
    python agent.py "Should we enter the Southeast Asian food delivery market?"
"""

import sys
import json
import re
from dataclasses import dataclass, field
from llm_client import LLMClient
import mock_web


TOOLS = [
    {
        "name": "search_web",
        "description": "Search the web for a query, returns a list of {title, url, snippet}.",
        "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
    },
    {
        "name": "fetch",
        "description": "Fetch and return the readable text content of a URL (e.g. one returned by search_web).",
        "input_schema": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]},
    },
]


@dataclass
class SubQuestion:
    text: str
    status: str = "missing"          # missing | answered
    answer: str = ""
    sources: list = field(default_factory=list)   # list of {title, url}


def llm_json(llm: LLMClient, system: str, user: str):
    text = llm.complete(system, user)
    m = re.search(r"\[.*\]|\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


def make_plan(llm: LLMClient, question: str) -> list:
    system = ("You are a research planner. Break the business question into 4-7 concrete, "
              "independently-answerable sub-questions that together would let someone give "
              "a well-supported recommendation. Respond with ONLY a JSON array of strings.")
    result = llm_json(llm, system, question)
    if not result:
        result = [
            f"What is the market size and growth rate relevant to: {question}",
            f"Who are the key competitors relevant to: {question}",
            f"What regulatory/operational risks apply to: {question}",
            f"What is the likely cost/investment required for: {question}",
        ]
    return [SubQuestion(text=q) for q in result]


def answer_subquestion(llm: LLMClient, sq: SubQuestion):
    """Use the search_web + fetch tools to research a single sub-question,
    then extract a concrete answer with citations."""
    system = ("You are a research analyst answering ONE specific sub-question. Use search_web "
              "to find candidate sources, then fetch the most promising 1-3 URLs to read them. "
              "Then answer the sub-question in 3-6 sentences based ONLY on what you found. "
              "End your answer with a line 'SOURCES:' followed by a JSON array of "
              "{\"title\":..., \"url\":...} for every source you actually used. If you cannot find "
              "a good answer, say so explicitly instead of guessing.")

    collected_sources = []

    def executor(name, tool_input):
        if name == "search_web":
            results = mock_web.search_web(tool_input.get("query", sq.text))
            return json.dumps(results)
        if name == "fetch":
            url = tool_input.get("url", "")
            content = mock_web.fetch(url)
            return content
        return f"unknown tool {name}"

    final_text, transcript = llm.run_tool_loop(system, sq.text, TOOLS, executor)

    # pull sources block back out of final_text
    sources = []
    m = re.search(r"SOURCES:\s*(\[.*\])", final_text, re.DOTALL)
    if m:
        try:
            sources = json.loads(m.group(1))
        except Exception:
            sources = []
    if not sources:
        # fall back to whatever URLs the tools actually touched
        for t in transcript:
            if t["tool"] == "search_web":
                try:
                    for r in json.loads(t["result"]):
                        sources.append({"title": r["title"], "url": r["url"]})
                except Exception:
                    pass

    answer_text = final_text.split("SOURCES:")[0].strip()
    is_answered = bool(answer_text) and "cannot find" not in answer_text.lower()

    sq.answer = answer_text
    sq.sources = sources[:3]
    sq.status = "answered" if is_answered else "missing"
    return sq


def revise_plan(llm: LLMClient, question: str, sub_questions: list) -> list:
    missing = [sq.text for sq in sub_questions if sq.status == "missing"]
    if not missing:
        return sub_questions
    system = ("Some sub-questions in this research plan could not be answered well. "
              "Propose replacement sub-questions (same count) that approach the same "
              "information need from a different, more answerable angle. "
              "Respond with ONLY a JSON array of strings, same length as the input list.")
    user = f"Original question: {question}\nUnanswered sub-questions: {json.dumps(missing)}"
    replacements = llm_json(llm, system, user) or missing
    replacement_iter = iter(replacements)
    for sq in sub_questions:
        if sq.status == "missing":
            try:
                sq.text = next(replacement_iter)
            except StopIteration:
                pass
    return sub_questions


def compile_report(llm: LLMClient, question: str, sub_questions: list) -> str:
    findings = "\n\n".join(
        f"### {sq.text}\nStatus: {sq.status}\nAnswer: {sq.answer}\nSources: {json.dumps(sq.sources)}"
        for sq in sub_questions
    )
    system = ("You are a research analyst writing a final report. Given the business question and "
              "the researched findings for each sub-question below, write a structured markdown "
              "report with: a one-paragraph executive summary, a section per sub-question "
              "(with citations as [Source Title](url) inline), and a final 'Recommendation' section. "
              "Only use the findings given — do not invent facts or sources.")
    user = f"Business question: {question}\n\nFindings:\n{findings}"
    return llm.complete(system, user, max_tokens=3000)


def run_research(question: str, max_replan_cycles: int = 2):
    llm = LLMClient()
    print(f"[plan] Generating research plan for: {question}")
    sub_questions = make_plan(llm, question)
    for sq in sub_questions:
        print(f"  - {sq.text}")

    for cycle in range(max_replan_cycles + 1):
        print(f"\n[execute] Research cycle {cycle + 1}")
        for sq in sub_questions:
            if sq.status == "answered":
                continue
            print(f"  researching: {sq.text}")
            answer_subquestion(llm, sq)
            print(f"    -> {sq.status}")

        missing = [sq for sq in sub_questions if sq.status == "missing"]
        print(f"[reflect] {len(sub_questions) - len(missing)}/{len(sub_questions)} answered, {len(missing)} missing")
        if not missing or cycle == max_replan_cycles:
            break
        print("[reflect] gaps remain -> revising plan for missing sub-questions")
        sub_questions = revise_plan(llm, question, sub_questions)

    print("\n[compile] Writing final report...")
    report = compile_report(llm, question, sub_questions)
    return report, sub_questions


if __name__ == "__main__":
    question = sys.argv[1] if len(sys.argv) > 1 else \
        "Should we enter the Southeast Asian food delivery market?"
    report, sqs = run_research(question)

    print("\n" + "=" * 70)
    print(report)

    with open("report.md", "w") as f:
        f.write(report)

    with open("research_result.json", "w") as f:
        json.dump({
            "question": question,
            "report": report,
            "sub_questions": [
                {"text": sq.text, "status": sq.status, "answer": sq.answer, "sources": sq.sources}
                for sq in sqs
            ],
        }, f, indent=2)

    print("\n[saved] report.md, research_result.json (used by dashboard.py)")
