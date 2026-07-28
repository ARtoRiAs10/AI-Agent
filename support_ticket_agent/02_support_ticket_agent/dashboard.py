"""
Streamlit dashboard for the Support Ticket Resolution Agent.

Run:
    python agent.py              # generates tickets_result.json
    streamlit run dashboard.py
"""

import json
import os
import subprocess
import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Support Ticket Agent", layout="wide")
st.title("🎫 Support Ticket Resolution Dashboard")

RESULT_PATH = "tickets_result.json"

with st.sidebar:
    st.header("Run")
    if st.button("Run agent on sample tickets"):
        with st.spinner("Resolving tickets..."):
            proc = subprocess.run(["python3", "agent.py"], capture_output=True, text=True)
        if proc.returncode != 0:
            st.error(proc.stderr[-2000:])
        else:
            st.success("Done.")

if not os.path.exists(RESULT_PATH):
    st.info("No tickets_result.json yet — click **Run agent on sample tickets**, "
            "or run `python agent.py` from the command line first.")
    st.stop()

with open(RESULT_PATH) as f:
    results = json.load(f)

actions = [r["resolution"].get("action", "unknown") for r in results]
col1, col2, col3 = st.columns(3)
col1.metric("Total tickets", len(results))
col2.metric("Resolved directly", actions.count("resolve"))
col3.metric("Escalated", actions.count("escalate"))

c1, c2 = st.columns([1, 2])
with c1:
    action_counts = pd.Series(actions).value_counts().reset_index()
    action_counts.columns = ["action", "count"]
    fig = px.pie(action_counts, names="action", values="count",
                 color="action", color_discrete_map={"resolve": "#2ca02c", "escalate": "#d62728"},
                 title="Resolve vs Escalate")
    st.plotly_chart(fig, use_container_width=True)

with c2:
    priorities = [r["resolution"].get("escalation_summary", {}).get("priority", "n/a")
                  for r in results if r["resolution"].get("action") == "escalate"]
    if priorities:
        pr_counts = pd.Series(priorities).value_counts().reset_index()
        pr_counts.columns = ["priority", "count"]
        fig2 = px.bar(pr_counts, x="priority", y="count", title="Escalation priority breakdown")
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.write("No escalations to break down by priority.")

st.subheader("Ticket detail")
for r in results:
    action = r["resolution"].get("action", "unknown")
    badge = "🟢 RESOLVED" if action == "resolve" else "🔴 ESCALATED"
    with st.expander(f"{badge} — {r['ticket_id']}: {r['subject']}"):
        st.write(f"**Customer:** {r['customer_id']} | **Order:** {r['order_id']}")
        st.write(f"**Body:** {r['body']}")
        st.write(f"**Tools called:** {', '.join(r['tool_calls'])}")
        if action == "resolve":
            st.success(r["resolution"].get("customer_message", ""))
        else:
            esc = r["resolution"].get("escalation_summary", {})
            st.error(json.dumps(esc, indent=2))
