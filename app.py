"""AML Copilot — Streamlit UI."""
import streamlit as st
from src.db import get_conn
from src.triage import run_triage
from src.audit import verify_chain

st.set_page_config(
    page_title="AML Copilot",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Styles ───────────────────────────────────────────────────────────────────
TIER_COLORS = {
    "low": "#28a745",
    "medium": "#fd7e14",
    "high": "#dc3545",
    "critical": "#6f0000",
}
SEVERITY_COLORS = {
    "low": "#28a745",
    "medium": "#fd7e14",
    "high": "#dc3545",
    "critical": "#6f0000",
}
ACTION_LABELS = {
    "close": "✅ Close",
    "monitor": "👁 Monitor",
    "escalate": "⚠️ Escalate",
    "file_sar": "🚨 File SAR",
}


def _badge(label: str, color: str, text_color: str = "white") -> str:
    return (
        f'<span style="background:{color};color:{text_color};padding:3px 10px;'
        f'border-radius:4px;font-weight:600;font-size:0.85rem;">{label}</span>'
    )


@st.cache_resource
def _conn():
    return get_conn()


def _load_alerts(conn):
    with conn.cursor() as cur:
        cur.execute(
            """SELECT a.id, a.typology, a.status, a.created_at,
                      e.name AS sender_name, e.country
               FROM alerts a
               JOIN transactions t ON t.id = a.transaction_id
               JOIN entities e ON e.id = t.sender_id
               ORDER BY a.id""",
        )
        return cur.fetchall()


# ── Sidebar — alert selector ─────────────────────────────────────────────────
st.sidebar.title("AML Copilot")
st.sidebar.caption("Compliance-first agentic triage")

conn = _conn()
alerts = _load_alerts(conn)

if not alerts:
    st.sidebar.warning("No alerts found. Run the seed script first:\n`python -c \"from src.db import get_conn; from src.synthetic import seed_database; seed_database(get_conn())\"`")
    st.stop()

alert_options = {
    f"#{row[0]} — {row[1] or 'unknown'} ({row[2]})": row[0]
    for row in alerts
}
selected_label = st.sidebar.selectbox("Select Alert", list(alert_options.keys()))
alert_id = alert_options[selected_label]

# Metadata card
selected_row = next(r for r in alerts if r[0] == alert_id)
_, typology, status, created_at, sender_name, country = selected_row

st.sidebar.markdown("---")
st.sidebar.markdown("**Alert Metadata**")
st.sidebar.markdown(f"- **ID:** {alert_id}")
st.sidebar.markdown(f"- **Typology:** {typology or 'Unknown'}")
st.sidebar.markdown(f"- **Status:** {status}")
st.sidebar.markdown(f"- **Date:** {created_at.strftime('%Y-%m-%d') if created_at else 'N/A'}")
st.sidebar.markdown(f"- **Sender:** {sender_name}")
st.sidebar.markdown(f"- **Jurisdiction:** {country or 'Unknown'}")

st.sidebar.markdown("---")
run_clicked = st.sidebar.button("▶ Run Triage", type="primary", use_container_width=True)

# ── Main area ────────────────────────────────────────────────────────────────
st.title("AML Triage Brief")

if "results" not in st.session_state:
    st.session_state.results = {}

if run_clicked:
    with st.spinner("Running triage pipeline…"):
        try:
            result = run_triage(conn, alert_id)
            st.session_state.results[alert_id] = result
        except Exception as e:
            st.error(f"Triage failed: {e}")

result = st.session_state.results.get(alert_id)

if result is None:
    st.info("Select an alert from the sidebar and click **▶ Run Triage** to begin.")
    st.stop()

brief = result.brief

# ── Risk tier + recommended action header ────────────────────────────────────
col1, col2, col3 = st.columns([2, 2, 4])
with col1:
    tier_color = TIER_COLORS.get(brief.risk_tier, "#6c757d")
    st.markdown(
        f"**Risk Tier**<br>{_badge(brief.risk_tier.upper(), tier_color)}",
        unsafe_allow_html=True,
    )
with col2:
    action_color = TIER_COLORS.get(
        {"close": "low", "monitor": "medium", "escalate": "high", "file_sar": "critical"}.get(
            brief.recommended_action, "low"
        ),
        "#6c757d",
    )
    st.markdown(
        f"**Recommended Action**<br>{_badge(ACTION_LABELS[brief.recommended_action], action_color)}",
        unsafe_allow_html=True,
    )
with col3:
    st.markdown(f"**Typology Match:** {brief.typology_match}")

st.markdown("---")

# ── Red flags ────────────────────────────────────────────────────────────────
st.subheader(f"Red Flags ({len(brief.red_flags)})")
for flag in brief.red_flags:
    sev_color = SEVERITY_COLORS.get(flag.severity, "#6c757d")
    with st.container():
        st.markdown(
            f"{_badge(flag.severity.upper(), sev_color)} &nbsp; {flag.description}",
            unsafe_allow_html=True,
        )
        citation_strs = [f"`{c.source_id}` ({c.source_type})" for c in flag.citations]
        st.caption("Citations: " + " · ".join(citation_strs))
    st.markdown("")

st.markdown("---")

# ── Reasoning summary ────────────────────────────────────────────────────────
st.subheader("Reasoning Summary")
st.write(brief.reasoning_summary)
reasoning_citation_strs = [f"`{c.source_id}` ({c.source_type})" for c in brief.reasoning_citations]
st.caption("Reasoning citations: " + " · ".join(reasoning_citation_strs))

st.markdown("---")

# ── SAR narrative draft ──────────────────────────────────────────────────────
if brief.sar_narrative_draft:
    st.subheader("SAR Narrative Draft")
    st.text_area(
        label="",
        value=brief.sar_narrative_draft,
        height=200,
        disabled=False,
        label_visibility="collapsed",
    )
    st.caption("Edit before submission. All PII tokens have been rehydrated to real identifiers.")

# ── Expandable panels ────────────────────────────────────────────────────────
with st.expander("Raw vs Redacted Narrative"):
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Raw (with PII)**")
        st.text_area("raw", result.raw_narrative, height=300, disabled=True, label_visibility="collapsed")
    with c2:
        st.markdown("**Tokenized (sent to LLM)**")
        st.text_area("tok", result.tokenized_narrative, height=300, disabled=True, label_visibility="collapsed")
    if result.token_map:
        st.markdown("**Token Map**")
        st.json(result.token_map)

with st.expander("Audit Trail"):
    chain_valid = verify_chain(conn, alert_id)
    if chain_valid:
        st.success("Hash chain intact — no tampering detected.")
    else:
        st.error("Hash chain INVALID — potential tampering detected.")

    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, step, prev_hash, curr_hash, created_at FROM audit_log WHERE alert_id=%s ORDER BY id",
            (alert_id,),
        )
        audit_rows = cur.fetchall()

    import pandas as pd
    df = pd.DataFrame(
        audit_rows,
        columns=["Log ID", "Step", "Prev Hash", "Curr Hash", "Timestamp"],
    )
    df["Prev Hash"] = df["Prev Hash"].apply(lambda h: h[:12] + "…" if h else "GENESIS")
    df["Curr Hash"] = df["Curr Hash"].apply(lambda h: h[:12] + "…" if h else "")
    st.dataframe(df, use_container_width=True)

with st.expander("SQL Executed"):
    st.code(result.sql_executed, language="sql")

# ── Analyst feedback ─────────────────────────────────────────────────────────
st.markdown("---")
st.subheader("Analyst Feedback")
feedback_col1, feedback_col2 = st.columns([3, 1])
with feedback_col1:
    ground_truth = st.selectbox(
        "Final Disposition",
        options=["— select —", "true_positive", "false_positive"],
        key=f"gt_{alert_id}",
    )
with feedback_col2:
    submit_feedback = st.button("Save Feedback", key=f"fb_{alert_id}")

if submit_feedback and ground_truth != "— select —":
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE alerts SET ground_truth=%s, status='reviewed' WHERE id=%s",
            (ground_truth, alert_id),
        )
    conn.commit()
    st.success(f"Feedback saved: {ground_truth}")
