"""Streamlit experiment console for persisted evaluation runs."""

import json
import os

import httpx
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from prompt_laboratory.dashboard_collaboration import (
    can_manage_members,
    manageable_members,
)

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


def auth_headers(include_workspace: bool = True) -> dict[str, str]:
    token = st.session_state.get("access_token")
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    workspace_id = st.session_state.get("workspace_id")
    if include_workspace and workspace_id:
        headers["X-Workspace-ID"] = workspace_id
    return headers


def fetch_json(path: str, include_workspace: bool = True) -> object:
    response = httpx.get(
        f"{API_URL}{path}",
        headers=auth_headers(include_workspace),
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


def request_json(
    method: str,
    path: str,
    *,
    payload: dict[str, object] | None = None,
    include_workspace: bool = True,
) -> object | None:
    response = httpx.request(
        method,
        f"{API_URL}{path}",
        json=payload,
        headers=auth_headers(include_workspace),
        timeout=20,
    )
    response.raise_for_status()
    if response.status_code == 204:
        return None
    return response.json()


def submit_auth(path: str, payload: dict[str, str]) -> None:
    response = httpx.post(f"{API_URL}{path}", json=payload, timeout=20)
    response.raise_for_status()
    result = response.json()
    st.session_state["access_token"] = result["access_token"]
    st.session_state["user"] = result["user"]
    st.session_state["workspaces"] = result["workspaces"]
    st.session_state["workspace_id"] = result["workspaces"][0]["id"]
    st.rerun()


if "access_token" not in st.session_state:
    st.subheader("Sign in to your laboratory")
    sign_in, register = st.tabs(["Sign in", "Create account"])
    with sign_in:
        with st.form("sign-in-form"):
            email = st.text_input("Email address")
            password = st.text_input("Password", type="password")
            submitted_login = st.form_submit_button("Sign in", type="primary")
        if submitted_login:
            try:
                submit_auth("/api/v1/auth/login", {"email": email, "password": password})
            except httpx.HTTPStatusError as exc:
                st.error(exc.response.json().get("detail", "Sign-in failed"))
            except httpx.HTTPError as exc:
                st.error(f"Authentication service unavailable: {exc}")
    with register:
        with st.form("registration-form"):
            display_name = st.text_input("Your name")
            registration_email = st.text_input("Email address", key="registration-email")
            registration_password = st.text_input(
                "Password (at least 10 characters)", type="password", key="registration-password"
            )
            workspace_name = st.text_input("Workspace name", value="My Prompt Laboratory")
            submitted_registration = st.form_submit_button("Create account", type="primary")
        if submitted_registration:
            try:
                submit_auth(
                    "/api/v1/auth/register",
                    {
                        "email": registration_email,
                        "display_name": display_name,
                        "password": registration_password,
                        "workspace_name": workspace_name,
                    },
                )
            except httpx.HTTPStatusError as exc:
                st.error(exc.response.json().get("detail", "Account creation failed"))
            except httpx.HTTPError as exc:
                st.error(f"Authentication service unavailable: {exc}")
    st.stop()


try:
    identity = fetch_json("/api/v1/auth/me", include_workspace=False)
    st.session_state["user"] = identity["user"]
    st.session_state["workspaces"] = identity["workspaces"]
except httpx.HTTPStatusError as exc:
    if exc.response.status_code == 401:
        for key in ("access_token", "user", "workspaces", "workspace_id", "workbench_result"):
            st.session_state.pop(key, None)
        st.rerun()
    st.error(f"Authentication check failed: {exc}")
    st.stop()
except httpx.HTTPError as exc:
    st.error(f"Authentication service unavailable: {exc}")
    st.stop()


workspaces = st.session_state["workspaces"]
if not workspaces:
    st.error("Your account does not belong to a workspace.")
    st.stop()
workspace_by_name = {f"{item['name']} · {item['role']}": item for item in workspaces}
current_workspace = st.session_state.get("workspace_id")
default_index = next(
    (
        index
        for index, item in enumerate(workspace_by_name.values())
        if item["id"] == current_workspace
    ),
    0,
)
with st.sidebar:
    st.markdown(f"**{st.session_state['user']['display_name']}**")
    workspace_label = st.selectbox("Workspace", list(workspace_by_name), index=default_index)
    selected_workspace_id = workspace_by_name[workspace_label]["id"]
    if selected_workspace_id != st.session_state.get("workspace_id"):
        st.session_state["workspace_id"] = selected_workspace_id
        st.session_state.pop("workbench_result", None)
        st.rerun()
    selected_workspace = workspace_by_name[workspace_label]
    current_role = str(selected_workspace["role"])

    with st.expander("Workspace collaboration"):
        st.caption(f"Your role: {current_role.title()}")
        try:
            members = fetch_json(
                f"/api/v1/workspaces/{selected_workspace_id}/members",
                include_workspace=False,
            )
        except httpx.HTTPError as exc:
            st.error(f"Unable to load workspace members: {exc}")
            members = []

        if members:
            st.dataframe(
                pd.DataFrame(members)[["display_name", "email", "role"]],
                hide_index=True,
                use_container_width=True,
                column_config={
                    "display_name": "Member",
                    "email": "Email",
                    "role": "Role",
                },
            )

        if can_manage_members(current_role):
            with st.form("workspace-invitation-form", clear_on_submit=True):
                invitation_email = st.text_input("Invite by email")
                invitation_role = st.selectbox(
                    "Workspace role",
                    ["viewer", "editor", "admin"],
                )
                send_invitation = st.form_submit_button(
                    "Create invitation",
                    use_container_width=True,
                )
            if send_invitation:
                try:
                    invitation = request_json(
                        "POST",
                        f"/api/v1/workspaces/{selected_workspace_id}/invitations",
                        payload={"email": invitation_email, "role": invitation_role},
                        include_workspace=False,
                    )
                    st.success("Invitation created. Share this token securely with the recipient.")
                    st.code(str(invitation["token"]), language=None)
                except httpx.HTTPStatusError as exc:
                    st.error(exc.response.json().get("detail", "Unable to create invitation"))
                except httpx.HTTPError as exc:
                    st.error(f"Invitation service unavailable: {exc}")

            try:
                pending_invitations = fetch_json(
                    f"/api/v1/workspaces/{selected_workspace_id}/invitations",
                    include_workspace=False,
                )
            except httpx.HTTPError as exc:
                st.error(f"Unable to load invitations: {exc}")
                pending_invitations = []
            if pending_invitations:
                st.caption("Pending invitations")
                invitation_frame = pd.DataFrame(pending_invitations)
                invitation_columns = [
                    column
                    for column in ("invited_email", "role", "status", "expires_at")
                    if column in invitation_frame.columns
                ]
                st.dataframe(
                    invitation_frame[invitation_columns],
                    hide_index=True,
                    use_container_width=True,
                )

            member_targets = manageable_members(
                members,
                actor_user_id=str(st.session_state["user"]["id"]),
                actor_role=current_role,
            )
            if member_targets:
                st.caption("Manage a member")
                member_by_label = {
                    f"{member['display_name']} · {member['email']}": member
                    for member in member_targets
                }
                selected_member_label = st.selectbox(
                    "Member",
                    list(member_by_label),
                    key="workspace-member-selection",
                )
                selected_member = member_by_label[selected_member_label]
                role_options = ["viewer", "editor", "admin"]
                selected_role = st.selectbox(
                    "New role",
                    role_options,
                    index=(
                        role_options.index(str(selected_member["role"]))
                        if selected_member["role"] in role_options
                        else 0
                    ),
                    key="workspace-member-role",
                )
                update_column, remove_column = st.columns(2)
                if update_column.button("Update role", use_container_width=True):
                    try:
                        request_json(
                            "PATCH",
                            f"/api/v1/workspaces/{selected_workspace_id}/members/{selected_member['user_id']}",
                            payload={"role": selected_role},
                            include_workspace=False,
                        )
                        st.success("Member role updated.")
                        st.rerun()
                    except httpx.HTTPStatusError as exc:
                        st.error(exc.response.json().get("detail", "Unable to update member"))
                if remove_column.button("Remove member", use_container_width=True):
                    try:
                        request_json(
                            "DELETE",
                            f"/api/v1/workspaces/{selected_workspace_id}/members/{selected_member['user_id']}",
                            include_workspace=False,
                        )
                        st.success("Member removed.")
                        st.rerun()
                    except httpx.HTTPStatusError as exc:
                        st.error(exc.response.json().get("detail", "Unable to remove member"))

        st.caption("Accept or reject an invitation sent to your account")
        with st.form("invitation-response-form", clear_on_submit=True):
            invitation_token = st.text_input("Invitation token", type="password")
            invitation_action = st.radio(
                "Response",
                ["accept", "reject"],
                horizontal=True,
            )
            respond_to_invitation = st.form_submit_button(
                "Submit response",
                use_container_width=True,
            )
        if respond_to_invitation:
            try:
                request_json(
                    "POST",
                    f"/api/v1/invitations/{invitation_action}",
                    payload={"token": invitation_token},
                    include_workspace=False,
                )
                response_label = "accepted" if invitation_action == "accept" else "rejected"
                st.success(f"Invitation {response_label}.")
                st.session_state["workspaces"] = fetch_json(
                    "/api/v1/workspaces", include_workspace=False
                )
                st.rerun()
            except httpx.HTTPStatusError as exc:
                st.error(exc.response.json().get("detail", "Unable to respond to invitation"))
            except httpx.HTTPError as exc:
                st.error(f"Invitation service unavailable: {exc}")
    with st.expander("Provider API keys"):
        st.caption("Keys are encrypted server-side and are never displayed after saving.")
        try:
            credential_statuses = fetch_json(
                "/api/v1/credentials", include_workspace=False
            )
        except httpx.HTTPError as exc:
            st.error(f"Credential service unavailable: {exc}")
            credential_statuses = []

        if credential_statuses:
            credential_by_label = {
                str(item["label"]): item for item in credential_statuses
            }
            with st.form("provider-credential-form", clear_on_submit=True):
                credential_label = st.selectbox(
                    "Provider",
                    list(credential_by_label),
                )
                provider_api_key = st.text_input(
                    "API key",
                    type="password",
                    help="Saving a new value rotates the existing user key.",
                )
                save_credential = st.form_submit_button(
                    "Save key",
                    use_container_width=True,
                )
            if save_credential:
                try:
                    provider_name = credential_by_label[credential_label]["provider"]
                    response = httpx.put(
                        f"{API_URL}/api/v1/credentials/{provider_name}",
                        json={"api_key": provider_api_key},
                        headers=auth_headers(include_workspace=False),
                        timeout=20,
                    )
                    response.raise_for_status()
                    st.success(f"{credential_label} key saved.")
                    st.rerun()
                except httpx.HTTPStatusError as exc:
                    st.error(exc.response.json().get("detail", "Unable to save key"))
                except httpx.HTTPError as exc:
                    st.error(f"Credential service unavailable: {exc}")

            for item in credential_statuses:
                source_labels = {
                    "user": "Personal key",
                    "deployment": "Deployment key",
                    "unconfigured": "Not configured",
                }
                left, right = st.columns([2.1, 1])
                left.caption(
                    f"{item['label']} · {source_labels.get(item['source'], item['source'])}"
                )
                if item["source"] == "user" and right.button(
                    "Remove",
                    key=f"remove-credential-{item['provider']}",
                    use_container_width=True,
                ):
                    try:
                        response = httpx.delete(
                            f"{API_URL}/api/v1/credentials/{item['provider']}",
                            headers=auth_headers(include_workspace=False),
                            timeout=20,
                        )
                        response.raise_for_status()
                        st.rerun()
                    except httpx.HTTPError as exc:
                        st.error(f"Unable to remove key: {exc}")

    if st.button("Sign out", use_container_width=True):
        for key in ("access_token", "user", "workspaces", "workspace_id", "workbench_result"):
            st.session_state.pop(key, None)
        st.rerun()


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
            result = httpx.post(
                f"{API_URL}{path}",
                json=payload,
                headers=auth_headers(),
                timeout=120,
            )
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
