"""Streamlit experiment console for persisted evaluation runs."""

import json
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
    .provider-status {
        display:inline-flex; align-items:center; gap:.35rem; margin:.1rem 0 .8rem;
        padding:.22rem .62rem; border-radius:999px; font-size:.75rem; font-weight:700;
    }
    .provider-success { color:#6ee7b7; background:rgba(16,185,129,.12); }
    .provider-error { color:#fca5a5; background:rgba(239,68,68,.12); }
    div[data-testid="stDataFrame"] { border:1px solid rgba(148,163,184,.16); border-radius:16px; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="lab-kicker">PROMPT QUALITY ENGINEERING</div>', unsafe_allow_html=True)
st.markdown('<div class="lab-title">Prompt Laboratory</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="lab-subtitle">Version, evaluate, compare and ship better prompts.</div>',
    unsafe_allow_html=True,
)


def fetch_json(path: str) -> list[dict[str, object]]:
    response = httpx.get(f"{API_URL}{path}", timeout=10)
    response.raise_for_status()
    return response.json()


st.subheader("Interactive prompt workbench")
st.caption(
    "Run one Git-versioned prompt against a single model or compare providers side by side."
)

try:
    prompt_catalog = fetch_json("/api/v1/prompts")
    provider_catalog = fetch_json("/api/v1/providers")
except httpx.HTTPError as exc:
    st.error(f"Workbench API unavailable: {exc}")
    prompt_catalog = []
    provider_catalog = []

if prompt_catalog:
    prompt_by_label = {
        f"{item['name']} · {item['version']} · {item['industry']}": item
        for item in prompt_catalog
    }
    selected_label = st.selectbox("Prompt contract", list(prompt_by_label))
    selected_prompt = prompt_by_label[selected_label]
    available_providers = [item for item in provider_catalog if item["configured"]]
    provider_by_label = {str(item["label"]): item for item in available_providers}

    workbench_mode = st.radio(
        "Experiment mode",
        ["Single run", "Compare models"],
        horizontal=True,
        label_visibility="collapsed",
    )

    with st.form("workbench-form"):
        left, right = st.columns([1.2, 1])
        values: dict[str, object] = {}
        with left:
            st.markdown(f"**{selected_prompt['description']}**")
            for name, definition in selected_prompt["variables"].items():
                label = f"{name} — {definition['description']}"
                kind = definition["type"]
                default = definition.get("default")
                if kind == "boolean":
                    values[name] = st.checkbox(label, value=bool(default))
                elif kind == "integer":
                    values[name] = st.number_input(label, value=int(default or 0), step=1)
                elif kind == "number":
                    values[name] = st.number_input(label, value=float(default or 0.0))
                elif kind in {"object", "array"}:
                    initial = default if default is not None else ({} if kind == "object" else [])
                    values[name] = st.text_area(label, value=json.dumps(initial, indent=2))
                else:
                    values[name] = st.text_area(label, value=str(default or ""))
        with right:
            if workbench_mode == "Single run":
                selected_provider_labels = [
                    st.selectbox("Model provider", list(provider_by_label))
                ]
            else:
                defaults = list(provider_by_label)[: min(2, len(provider_by_label))]
                selected_provider_labels = st.multiselect(
                    "Models to compare",
                    list(provider_by_label),
                    default=defaults,
                    help="Each selected provider receives exactly the same rendered prompt.",
                )
            st.code(selected_prompt["template"], language="jinja2")
        button_label = "Compare models" if workbench_mode == "Compare models" else "Run experiment"
        submitted = st.form_submit_button(button_label, type="primary", use_container_width=True)

    if submitted:
        try:
            for name, definition in selected_prompt["variables"].items():
                if definition["type"] in {"object", "array"}:
                    values[name] = json.loads(str(values[name]))
            provider_ids = [provider_by_label[label]["id"] for label in selected_provider_labels]
            if workbench_mode == "Compare models":
                if len(provider_ids) < 2:
                    raise ValueError("Select at least two models to compare")
                path = "/api/v1/workbench/compare"
                payload = {
                    "prompt_id": selected_prompt["id"],
                    "variables": values,
                    "providers": provider_ids,
                }
            else:
                path = "/api/v1/workbench/execute"
                payload = {
                    "prompt_id": selected_prompt["id"],
                    "variables": values,
                    "provider": provider_ids[0],
                }
            result = httpx.post(f"{API_URL}{path}", json=payload, timeout=120)
            result.raise_for_status()
            st.session_state["workbench_result"] = {
                "mode": workbench_mode,
                "payload": result.json(),
            }
        except json.JSONDecodeError as exc:
            st.error(f"A structured variable contains invalid JSON: {exc}")
        except (ValueError, httpx.HTTPStatusError) as exc:
            if isinstance(exc, ValueError):
                detail = str(exc)
            else:
                try:
                    detail = exc.response.json().get("detail", str(exc))
                    if isinstance(detail, dict):
                        detail = detail.get("message", str(detail))
                except ValueError:
                    detail = str(exc)
            st.error(f"Experiment failed: {detail}")
        except httpx.HTTPError as exc:
            st.error(f"Experiment API unavailable: {exc}")

    if stored := st.session_state.get("workbench_result"):
        result = stored["payload"]
        st.markdown("#### Rendered prompt")
        st.code(result["rendered_prompt"])
        if stored["mode"] == "Single run":
            st.markdown("#### Model output")
            st.write(result["output"])
            st.caption(
                f"{result['provider']}/{result['model']} · {result['latency_ms']:.0f} ms · "
                f"{result['input_tokens']} input tokens · "
                f"{result['output_tokens']} output tokens"
            )
        else:
            st.markdown("#### Comparison results")
            comparisons = result["comparisons"]
            labels_by_id = {
                str(item["id"]): str(item["label"]) for item in provider_catalog
            }
            summary_rows = []
            for comparison in comparisons:
                model_result = comparison["result"]
                error = comparison["error"]
                summary_rows.append(
                    {
                        "Model": labels_by_id.get(
                            comparison["provider_id"], comparison["provider_id"]
                        ),
                        "Status": "Failed" if error else "Success",
                        "Latency": "—" if error else f"{model_result['latency_ms']:,.0f} ms",
                        "Tokens": "—"
                        if error
                        else f"{model_result['input_tokens'] + model_result['output_tokens']:,}",
                        "Estimated cost": "—"
                        if error
                        else f"${model_result['estimated_cost_usd']:.6f}",
                    }
                )
            st.dataframe(
                pd.DataFrame(summary_rows),
                hide_index=True,
                use_container_width=True,
                column_config={
                    "Model": st.column_config.TextColumn(width="large"),
                    "Status": st.column_config.TextColumn(width="small"),
                },
            )

            for offset in range(0, len(comparisons), 2):
                columns = st.columns(2)
                row = comparisons[offset : offset + 2]
                for column, comparison in zip(columns, row, strict=False):
                    with column, st.container(border=True):
                        provider_label = labels_by_id.get(
                            comparison["provider_id"], comparison["provider_id"]
                        )
                        st.markdown(f"##### {provider_label}")
                        if comparison["error"]:
                            st.markdown(
                                '<span class="provider-status provider-error">● Failed</span>',
                                unsafe_allow_html=True,
                            )
                            st.error(comparison["error"]["message"])
                        else:
                            st.markdown(
                                '<span class="provider-status provider-success">● Success</span>',
                                unsafe_allow_html=True,
                            )
                            model_result = comparison["result"]
                            m1, m2, m3 = st.columns(3)
                            m1.metric("Latency", f"{model_result['latency_ms']:,.0f} ms")
                            m2.metric(
                                "Tokens",
                                f"{model_result['input_tokens'] + model_result['output_tokens']:,}",
                            )
                            cost = model_result["estimated_cost_usd"]
                            cost_label = (
                                f"${cost:.6f}"
                                if cost > 0 or comparison["provider_id"] == "mock/echo"
                                else "Unavailable"
                            )
                            m3.metric("Cost", cost_label)
                            st.markdown("**Output**")
                            st.write(model_result["text"])

st.divider()

try:
    runs = fetch_json("/api/v1/runs")
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
