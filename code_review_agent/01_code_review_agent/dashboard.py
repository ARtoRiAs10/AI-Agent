"""
Streamlit dashboard for the Code Review Agent.

Run:
    python agent.py sample_pr.diff     # generates review_result.json
    streamlit run dashboard.py
"""

import json
import os
import subprocess
import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Code Review Agent", layout="wide")
st.title("🔍 Code Review Agent Dashboard")

RESULT_PATH = "review_result.json"

with st.sidebar:
    st.header("Run")
    diff_file = st.text_input("Diff file", value="sample_pr.diff")
    if st.button("Run agent on this diff"):
        with st.spinner("Reviewing PR..."):
            proc = subprocess.run(["python3", "agent.py", diff_file], capture_output=True, text=True)
        if proc.returncode != 0:
            st.error(proc.stderr[-2000:])
        else:
            st.success("Review complete.")

if not os.path.exists(RESULT_PATH):
    st.info("No review_result.json yet — click **Run agent on this diff** in the sidebar, "
            "or run `python agent.py sample_pr.diff` from the command line first.")
    st.stop()

with open(RESULT_PATH) as f:
    result = json.load(f)

files = result["files"]
rows = []
for f_ in files:
    for c in f_["comments"]:
        rows.append({"file": f_["path"], "review_mode": f_["review_mode"], **c})

col1, col2, col3 = st.columns(3)
col1.metric("Files reviewed", len(files))
col2.metric("Deep investigations", sum(1 for f_ in files if f_["review_mode"] == "deep_investigation"))
col3.metric("Total comments", len(rows))

if rows:
    df = pd.DataFrame(rows)
    severity_order = ["blocker", "high", "medium", "low", "nit"]
    df["severity"] = pd.Categorical(df["severity"], categories=severity_order, ordered=True)

    c1, c2 = st.columns(2)
    with c1:
        sev_counts = df["severity"].value_counts().reindex(severity_order).fillna(0).reset_index()
        sev_counts.columns = ["severity", "count"]
        fig = px.bar(sev_counts, x="severity", y="count", color="severity",
                     color_discrete_map={"blocker": "#8b0000", "high": "#d62728", "medium": "#ff7f0e",
                                          "low": "#1f77b4", "nit": "#7f7f7f"},
                     title="Comments by severity")
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        cat_counts = df["category"].value_counts().reset_index()
        cat_counts.columns = ["category", "count"]
        fig2 = px.pie(cat_counts, names="category", values="count", title="Comments by category")
        st.plotly_chart(fig2, use_container_width=True)

    st.subheader("All review comments")
    st.dataframe(df[["file", "review_mode", "severity", "category", "line_hint", "comment"]],
                 use_container_width=True, hide_index=True)
else:
    st.success("No issues found in this diff.")

st.subheader("Per-file triage")
triage_df = pd.DataFrame([
    {"file": f_["path"], "mode": f_["review_mode"], "tool_calls": len(f_["tool_calls_made"]),
     "comments": len(f_["comments"])}
    for f_ in files
])
st.dataframe(triage_df, use_container_width=True, hide_index=True)
