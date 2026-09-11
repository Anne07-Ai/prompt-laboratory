"""Streamlit dashboard for persisted evaluation runs."""

import os

import httpx
import pandas as pd
import streamlit as st

API_URL = os.getenv("PROMPT_LAB_API_URL", "http://localhost:8000").rstrip("/")

st.set_page_config(page_title="Prompt Laboratory", page_icon="🧪", layout="wide")
st.title("🧪 Prompt Laboratory")
st.caption("Prompt quality, cost, latency and regression evidence in one experiment console.")

try:
    response = httpx.get(f"{API_URL}/api/v1/runs", timeout=10)
    response.raise_for_status()
    runs = response.json()
except httpx.HTTPError as exc:
    st.error(f"API unavailable: {exc}")
    st.stop()

if not runs:
    st.info("No evaluation runs yet. POST an EvaluationReport to /api/v1/runs.")
    st.stop()

frame = pd.DataFrame(runs)
latest = frame.iloc[0]
c1, c2, c3, c4 = st.columns(4)
c1.metric("Latest score", f"{latest['average_score']:.1%}")
c2.metric("Pass rate", f"{latest['pass_rate']:.1%}")
c3.metric("Latency", f"{latest['total_latency_ms']:.0f} ms")
c4.metric("Estimated cost", f"${latest['estimated_cost_usd']:.6f}")

st.subheader("Evaluation history")
st.dataframe(
    frame[
        [
            "created_at",
            "prompt_id",
            "prompt_version",
            "provider",
            "average_score",
            "pass_rate",
            "total_latency_ms",
            "estimated_cost_usd",
        ]
    ],
    use_container_width=True,
    hide_index=True,
)

st.subheader("Quality trend")
trend = frame.sort_values("created_at").set_index("created_at")
st.line_chart(trend[["average_score", "pass_rate"]])

st.subheader("Cost and latency")
left, right = st.columns(2)
left.bar_chart(trend[["estimated_cost_usd"]])
right.bar_chart(trend[["total_latency_ms"]])
