"""Streamlit experiment console for persisted evaluation runs."""

import os

import httpx
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

API_URL = os.getenv("PROMPT_LAB_API_URL", "http://localhost:8000").rstrip("/")

st.set_page_config(page_title="Prompt Laboratory", page_icon="🧪", layout="wide")
st.markdown(
    """
    <style>
    .stApp {
        background:
          radial-gradient(circle at 8% 0%, rgba(124,58,237,.20), transparent 30rem),
          radial-gradient(circle at 92% 8%, rgba(6,182,212,.14), transparent 28rem), #070b14;
    }
    [data-testid="stHeader"] { background: transparent; }
    .block-container { max-width: 1480px; padding-top: 2rem; }
    .lab-kicker { color:#67e8f9; font-size:.78rem; letter-spacing:.18em; font-weight:700; }
    .lab-title {
        font-size:3rem; font-weight:800; margin:.2rem 0; line-height:1.05;
        background:linear-gradient(90deg,#f8fafc,#c4b5fd 48%,#67e8f9);
        -webkit-background-clip:text; -webkit-text-fill-color:transparent;
    }
    .lab-subtitle { color:#94a3b8; font-size:1rem; margin-bottom:1.4rem; }
    .metric-card {
        border:1px solid rgba(148,163,184,.16); border-radius:18px; padding:1.15rem 1.25rem;
        background:linear-gradient(145deg,rgba(30,41,59,.78),rgba(15,23,42,.60));
        box-shadow:0 16px 40px rgba(0,0,0,.22); min-height:128px;
    }
    .metric-label { color:#94a3b8; font-size:.76rem; letter-spacing:.09em; text-transform:uppercase; }
    .metric-value { color:#f8fafc; font-size:2rem; font-weight:750; margin:.35rem 0 .15rem; }
    .metric-note { color:#64748b; font-size:.8rem; }
    .status-pass { color:#34d399; } .status-watch { color:#fbbf24; }
    div[data-testid="stDataFrame"] { border:1px solid rgba(148,163,184,.16); border-radius:16px; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="lab-kicker">PROMPT QUALITY ENGINEERING</div>', unsafe_allow_html=True)
st.markdown('<div class="lab-title">Prompt Laboratory</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="lab-subtitle">Version, evaluate and release prompts with measurable confidence.</div>',
    unsafe_allow_html=True,
)

try:
    response = httpx.get(f"{API_URL}/api/v1/runs", timeout=10)
    response.raise_for_status()
    runs = response.json()
except httpx.HTTPError as exc:
    st.error(f"Experiment API unavailable: {exc}")
    st.stop()

if not runs:
    st.info("The laboratory is ready. POST an EvaluationReport to /api/v1/runs to begin.")
    st.stop()

frame = pd.DataFrame(runs)
frame["created_at"] = pd.to_datetime(frame["created_at"], utc=True, format="mixed")

with st.sidebar:
    st.header("Experiment filters")
    selected_prompts = st.multiselect(
        "Prompt", sorted(frame["prompt_id"].unique()), default=sorted(frame["prompt_id"].unique())
    )
    selected_providers = st.multiselect(
        "Provider", sorted(frame["provider"].unique()), default=sorted(frame["provider"].unique())
    )
    st.caption(f"API · {API_URL}")

filtered = frame[
    frame["prompt_id"].isin(selected_prompts) & frame["provider"].isin(selected_providers)
].sort_values("created_at", ascending=False)
if filtered.empty:
    st.warning("No runs match these filters.")
    st.stop()

latest = filtered.iloc[0]
passed = latest["pass_rate"] >= 0.9
status_label = "RELEASE READY" if passed else "NEEDS REVIEW"
status_class = "status-pass" if passed else "status-watch"


def metric_card(label: str, value: str, note: str, value_class: str = "") -> None:
    st.markdown(
        f"""<div class="metric-card"><div class="metric-label">{label}</div>
        <div class="metric-value {value_class}">{value}</div>
        <div class="metric-note">{note}</div></div>""",
        unsafe_allow_html=True,
    )


c1, c2, c3, c4, c5 = st.columns([1.15, 1, 1, 1, 1])
with c1:
    metric_card("Release signal", status_label, "Based on latest pass rate", status_class)
with c2:
    metric_card("Quality score", f"{latest['average_score']:.1%}", "Latest evaluation")
with c3:
    metric_card("Pass rate", f"{latest['pass_rate']:.1%}", f"{int(latest['total_cases'])} test cases")
with c4:
    metric_card("Latency", f"{latest['total_latency_ms']:,.0f} ms", "Total run latency")
with c5:
    metric_card("Estimated cost", f"${latest['estimated_cost_usd']:.6f}", "Per evaluation run")

overview, history = st.tabs(["◉ Experiment overview", "⌁ Run history"])

with overview:
    left, right = st.columns([1.35, 1])
    chart_frame = filtered.sort_values("created_at")
    with left:
        st.subheader("Quality trajectory")
        if len(chart_frame) > 1:
            quality = chart_frame.melt(
                id_vars=["created_at"],
                value_vars=["average_score", "pass_rate"],
                var_name="Metric",
                value_name="Score",
            )
            fig = px.line(
                quality, x="created_at", y="Score", color="Metric", markers=True,
                color_discrete_map={"average_score": "#8b5cf6", "pass_rate": "#22d3ee"},
            )
        else:
            fig = go.Figure(
                go.Bar(
                    x=["Quality score", "Pass rate"],
                    y=[latest["average_score"], latest["pass_rate"]],
                    marker_color=["#8b5cf6", "#22d3ee"],
                    text=[f"{latest['average_score']:.1%}", f"{latest['pass_rate']:.1%}"],
                    textposition="outside",
                )
            )
        fig.update_layout(
            height=360, yaxis_range=[0, 1.08], yaxis_tickformat=".0%",
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(15,23,42,.35)",
            legend_title_text="", margin={"l": 20, "r": 20, "t": 20, "b": 20},
        )
        st.plotly_chart(fig, use_container_width=True)

    with right:
        st.subheader("Latest run profile")
        gauge = go.Figure(
            go.Indicator(
                mode="gauge+number", value=float(latest["average_score"] * 100),
                number={"suffix": "%"}, title={"text": latest["prompt_id"]},
                gauge={
                    "axis": {"range": [0, 100]}, "bar": {"color": "#22d3ee"},
                    "steps": [
                        {"range": [0, 70], "color": "#331a35"},
                        {"range": [70, 90], "color": "#3b3150"},
                        {"range": [90, 100], "color": "#153b45"},
                    ],
                    "threshold": {"line": {"color": "#fbbf24", "width": 3}, "value": 90},
                },
            )
        )
        gauge.update_layout(
            height=360, paper_bgcolor="rgba(0,0,0,0)", margin={"t": 50, "b": 10}
        )
        st.plotly_chart(gauge, use_container_width=True)

    st.subheader("Efficiency observatory")
    e1, e2 = st.columns(2)
    cost_fig = px.bar(
        chart_frame, x="created_at", y="estimated_cost_usd", color="provider",
        color_discrete_sequence=["#a78bfa", "#22d3ee", "#fb7185"],
    )
    latency_fig = px.bar(
        chart_frame, x="created_at", y="total_latency_ms", color="provider",
        color_discrete_sequence=["#22d3ee", "#a78bfa", "#fb7185"],
    )
    for chart in (cost_fig, latency_fig):
        chart.update_layout(
            height=300, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(15,23,42,.35)",
            legend_title_text="", margin={"l": 20, "r": 20, "t": 20, "b": 20},
        )
    e1.plotly_chart(cost_fig, use_container_width=True)
    e2.plotly_chart(latency_fig, use_container_width=True)

with history:
    st.subheader("Evaluation evidence")
    display = filtered.copy()
    display["created_at"] = display["created_at"].dt.strftime("%Y-%m-%d %H:%M UTC")
    display["average_score"] = display["average_score"].map(lambda value: f"{value:.1%}")
    display["pass_rate"] = display["pass_rate"].map(lambda value: f"{value:.1%}")
    display["estimated_cost_usd"] = display["estimated_cost_usd"].map(
        lambda value: f"${value:.6f}"
    )
    st.dataframe(
        display[[
            "created_at", "prompt_id", "prompt_version", "provider", "average_score",
            "pass_rate", "total_latency_ms", "estimated_cost_usd",
        ]],
        use_container_width=True,
        hide_index=True,
    )
