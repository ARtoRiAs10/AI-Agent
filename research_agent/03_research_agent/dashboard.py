"""
Streamlit dashboard for the Research Agent (Plan -> Execute -> Reflect).

Run:
    python agent.py "your business question"    # generates research_result.json
    streamlit run dashboard.py
"""

import json
import os
import subprocess
import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Research Agent", layout="wide")
st.title("📊 Research Agent Dashboard")

RESULT_PATH = "research_result.json"

with st.sidebar:
    st.header("Run")
    question = st.text_area("Business question",
                             value="Should we enter the Southeast Asian food delivery market?")
    if st.button("Run research"):
        with st.spinner("Researching... (plan -> execute -> reflect loop)"):
            proc = subprocess.run(["python3", "agent.py", question], capture_output=True, text=True)
        if proc.returncode != 0:
            st.error(proc.stderr[-2000:])
        else:
            st.success("Report generated.")

if not os.path.exists(RESULT_PATH):
    st.info("No research_result.json yet — click **Run research** in the sidebar, "
            "or run `python agent.py \"<question>\"` from the command line first.")
    st.stop()

with open(RESULT_PATH) as f:
    data = json.load(f)

sqs = data["sub_questions"]
answered = sum(1 for s in sqs if s["status"] == "answered")

st.subheader(f"Question: {data['question']}")

col1, col2, col3 = st.columns(3)
col1.metric("Sub-questions", len(sqs))
col2.metric("Answered", answered)
col3.metric("Coverage", f"{answered/len(sqs):.0%}" if sqs else "n/a")

c1, c2 = st.columns([1, 2])
with c1:
    status_counts = pd.Series([s["status"] for s in sqs]).value_counts().reset_index()
    status_counts.columns = ["status", "count"]
    fig = px.pie(status_counts, names="status", values="count",
                 color="status", color_discrete_map={"answered": "#2ca02c", "missing": "#d62728"},
                 title="Sub-question coverage")
    st.plotly_chart(fig, use_container_width=True)

with c2:
    df = pd.DataFrame([{"sub_question": s["text"][:60] + ("..." if len(s["text"]) > 60 else ""),
                         "status": s["status"], "sources": len(s["sources"])} for s in sqs])
    fig2 = px.bar(df, x="sub_question", y="sources", color="status",
                   color_discrete_map={"answered": "#2ca02c", "missing": "#d62728"},
                   title="Sources found per sub-question")
    fig2.update_xaxes(tickangle=30)
    st.plotly_chart(fig2, use_container_width=True)

st.subheader("Sub-question detail")
for s in sqs:
    icon = "✅" if s["status"] == "answered" else "⚠️"
    with st.expander(f"{icon} {s['text']}"):
        st.write(s["answer"] or "_(no answer found)_")
        if s["sources"]:
            st.write("**Sources:**")
            for src in s["sources"]:
                st.write(f"- [{src.get('title', src.get('url'))}]({src.get('url')})")

st.subheader("Final report")
st.markdown(data["report"])
