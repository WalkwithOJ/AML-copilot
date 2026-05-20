"""AML Copilot — Nasdaq Verafin-branded Streamlit UI."""
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from src.db import get_conn
from src.triage import run_triage
from src.audit import verify_chain

# ─── Favicon: shield with N in Nasdaq blue ───────────────────────────────────
FAVICON_SVG = (
    "data:image/svg+xml,"
    "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E"
    "%3Crect width='32' height='32' rx='6' fill='%230297C8'/%3E"
    "%3Cpath d='M16 4 L26 8.5 V17 C26 22.5 21.5 27 16 29 C10.5 27 6 22.5 6 17 V8.5 Z' fill='white'/%3E"
    "%3Cpath d='M11 20 L11 12 L16 19 L21 12 L21 20' stroke='%230297C8' stroke-width='2.2' fill='none'"
    " stroke-linecap='round' stroke-linejoin='round'/%3E"
    "%3C/svg%3E"
)

st.set_page_config(
    page_title="AML Copilot · Nasdaq Verafin",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Inline SVG icon library (Lucide-compatible, 16×16) ──────────────────────
def icon(name: str, size: int = 16, color: str = "currentColor") -> str:
    paths = {
        "shield":   "M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z",
        "flag":     "M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z M4 22v-7",
        "file":     "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z M14 2v6h6",
        "check":    "M20 6L9 17l-5-5",
        "lock":     "M19 11H5a2 2 0 0 0-2 2v7a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7a2 2 0 0 0-2-2z M7 11V7a5 5 0 0 1 10 0v4",
        "database": "M12 2C7.03 2 3 3.79 3 6s4.03 4 9 4 9-1.79 9-4-4.03-4-9-4z M3 6v6c0 2.21 4.03 4 9 4s9-1.79 9-4V6 M3 12v6c0 2.21 4.03 4 9 4s9-1.79 9-4v-6",
        "clock":    "M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20z M12 6v6l4 2",
        "activity": "M22 12h-4l-3 9L9 3l-3 9H2",
        "user":     "M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2 M12 3a4 4 0 1 0 0 8 4 4 0 0 0 0-8z",
        "alert":    "M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z M12 9v4 M12 17h.01",
        "link":     "M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71 M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71",
        "eye":      "M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6z",
        "code":     "M16 18l6-6-6-6 M8 6l-6 6 6 6",
        "x":        "M18 6L6 18 M6 6l12 12",
        "chevron":  "M9 18l6-6-6-6",
        "hash":     "M4 9h16 M4 15h16 M10 3L8 21 M16 3l-2 18",
    }
    d = paths.get(name, "")
    return (
        f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" '
        f'stroke="{color}" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">'
        f'<path d="{d}"/></svg>'
    )


# ─── Design tokens ───────────────────────────────────────────────────────────
TIER = {
    "low":      {"color": "#059669", "bg": "#ECFDF5", "border": "#A7F3D0", "label": "LOW"},
    "medium":   {"color": "#D97706", "bg": "#FFFBEB", "border": "#FDE68A", "label": "MEDIUM"},
    "high":     {"color": "#DC2626", "bg": "#FEF2F2", "border": "#FECACA", "label": "HIGH"},
    "critical": {"color": "#7F1D1D", "bg": "#FFF1F1", "border": "#FCA5A5", "label": "CRITICAL"},
}
ACTION = {
    "close":    {"label": "Close",    "tier": "low",      "icon": "check"},
    "monitor":  {"label": "Monitor",  "tier": "medium",   "icon": "eye"},
    "escalate": {"label": "Escalate", "tier": "high",     "icon": "alert"},
    "file_sar": {"label": "File SAR", "tier": "critical", "icon": "file"},
}
SOURCE = {"regulation": "REG", "similar_case": "CASE", "entity_history": "HIST"}


# ─── CSS ─────────────────────────────────────────────────────────────────────
CSS = """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<link rel="icon" href="{favicon}" type="image/svg+xml">

<style>
/* Reset & base */
html, body, [class*="css"], .stApp {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
  font-feature-settings: 'cv02','cv03','cv04','cv11';
  -webkit-font-smoothing: antialiased;
}
code, pre, .mono { font-family: 'JetBrains Mono', 'SF Mono', Menlo, monospace !important; }

/* Hide only chrome we don't want — keep stToolbar visible (it contains the expand-sidebar button) */
#MainMenu, footer { display: none !important; }
[data-testid="stDecoration"] { display: none !important; }
.stDeployButton, .stAppDeployButton { display: none !important; }
[data-testid="stMainMenu"], [data-testid="stMainMenuButton"] { display: none !important; }
[data-testid="stStatusWidget"] { display: none !important; }
header[data-testid="stHeader"] {
  background: transparent !important;
  height: auto !important;
  z-index: 100 !important;
}
[data-testid="stToolbar"] {
  background: transparent !important;
  padding-top: 0.5rem !important;
}

[data-testid="stAppViewContainer"] > .main { padding-top: 0 !important; }
.block-container { max-width: 1200px !important; padding: 2.5rem 2rem 4rem !important; }

/* ── Expand-sidebar button (when collapsed) — IS the button itself ── */
button[data-testid="stExpandSidebarButton"] {
  display: flex !important;
  visibility: visible !important;
  align-items: center !important;
  justify-content: center !important;
  width: 40px !important;
  height: 40px !important;
  background: white !important;
  border: 1px solid #E2E8F0 !important;
  border-radius: 8px !important;
  color: #4A5568 !important;
  box-shadow: 0 2px 6px rgba(0,0,0,0.08) !important;
  cursor: pointer !important;
  transition: all 0.15s ease !important;
  pointer-events: auto !important;
  margin: 0 !important;
  padding: 0 !important;
}
button[data-testid="stExpandSidebarButton"]:hover {
  color: #0297C8 !important;
  border-color: #0297C8 !important;
  box-shadow: 0 4px 12px rgba(2,151,200,0.18) !important;
  background: white !important;
}
button[data-testid="stExpandSidebarButton"] svg,
button[data-testid="stExpandSidebarButton"] [data-testid="stIconMaterial"] {
  fill: currentColor !important;
  color: currentColor !important;
  font-size: 22px !important;
  width: 22px !important;
  height: 22px !important;
}

[data-testid="stHeaderActionElements"],
[data-testid="stToolbarActions"] {
  display: flex !important;
  visibility: visible !important;
  pointer-events: auto !important;
  padding: 8px !important;
  gap: 4px !important;
  align-items: center !important;
}

/* Sidebar header (where collapse X lives in Streamlit 1.39) */
[data-testid="stSidebarHeader"] {
  padding: 0.5rem 0.75rem 0 !important;
  display: flex !important; justify-content: flex-end !important;
}

/* Close button inside sidebar (X) */
[data-testid="stSidebarCollapseButton"] button {
  color: #6B8AB0 !important;
  background: transparent !important;
  border: none !important;
  border-radius: 6px !important;
  width: 32px !important; height: 32px !important;
  transition: all 0.15s ease !important;
}
[data-testid="stSidebarCollapseButton"] button:hover {
  background: rgba(255,255,255,0.06) !important;
  color: #E2EAF4 !important;
}
[data-testid="stSidebarCollapseButton"] svg { fill: currentColor !important; }

/* ── Sidebar ── */
[data-testid="stSidebar"] {
  background: #132038 !important;
  border-right: 1px solid #1E3354 !important;
  min-width: 260px !important;
}
[data-testid="stSidebar"] * { color: #E2EAF4 !important; }
[data-testid="stSidebarUserContent"] { padding: 0 !important; }

/* ── Sidebar selectbox (dark) ── */
[data-testid="stSidebar"] [data-baseweb="select"] > div {
  background: #1A2E4A !important;
  border: 1px solid #2A4066 !important;
  border-radius: 6px !important;
  color: #E2EAF4 !important;
  font-size: 0.85rem !important;
  min-height: 38px !important;
  transition: border-color 0.15s ease, box-shadow 0.15s ease !important;
}
[data-testid="stSidebar"] [data-baseweb="select"] > div:hover {
  border-color: #3A5478 !important;
}
[data-testid="stSidebar"] [data-baseweb="select"][data-focus] > div,
[data-testid="stSidebar"] [data-baseweb="select"]:focus-within > div {
  border-color: #0297C8 !important;
  box-shadow: 0 0 0 3px rgba(2,151,200,0.18) !important;
}
[data-testid="stSidebar"] [data-baseweb="select"] input { color: #E2EAF4 !important; }
[data-testid="stSidebar"] [data-baseweb="select"] svg { fill: #6B8AB0 !important; }

/* Selected value shown in the box (sidebar) */
[data-testid="stSidebar"] [data-baseweb="select"] [data-baseweb="tag"],
[data-testid="stSidebar"] [data-baseweb="select"] div[class*="ValueContainer"] > div {
  color: #E2EAF4 !important;
}

/* Sidebar button */
[data-testid="stSidebar"] .stButton > button {
  background: #0297C8 !important;
  color: white !important;
  border: none !important;
  border-radius: 6px !important;
  font-weight: 600 !important;
  font-size: 0.875rem !important;
  padding: 0.625rem 1rem !important;
  letter-spacing: 0.01em !important;
  width: 100% !important;
  transition: background 0.15s ease, box-shadow 0.15s ease !important;
}
[data-testid="stSidebar"] .stButton > button:hover {
  background: #017BA8 !important;
  box-shadow: 0 4px 12px rgba(2,151,200,0.35) !important;
}

/* Main area buttons */
.stButton > button {
  background: #0297C8 !important;
  color: white !important;
  border: none !important;
  border-radius: 6px !important;
  font-weight: 600 !important;
  font-size: 0.875rem !important;
  padding: 0.6rem 1.25rem !important;
  transition: background 0.15s ease, box-shadow 0.15s ease !important;
}
.stButton > button:hover {
  background: #017BA8 !important;
  box-shadow: 0 4px 12px rgba(2,151,200,0.3) !important;
}
.stButton > button[kind="secondary"] {
  background: white !important;
  border: 1px solid #CBD5E0 !important;
  color: #0A1628 !important;
}
.stButton > button[kind="secondary"]:hover {
  border-color: #0297C8 !important;
  color: #0297C8 !important;
  box-shadow: none !important;
  background: white !important;
}

/* Expanders */
[data-testid="stExpander"] {
  background: white !important;
  border: 1px solid #E2E8F0 !important;
  border-radius: 8px !important;
  margin-bottom: 0.75rem !important;
  box-shadow: 0 1px 3px rgba(0,0,0,0.06) !important;
}
[data-testid="stExpander"] summary {
  font-weight: 500 !important;
  color: #0A1628 !important;
  font-size: 0.875rem !important;
  padding: 0.85rem 1.1rem !important;
}
[data-testid="stExpander"] summary:hover { background: #F7F8FA !important; }

/* ── Main-area selectbox (light) ── */
.main [data-baseweb="select"] > div, .block-container [data-baseweb="select"] > div {
  background: white !important;
  border: 1px solid #CBD5E0 !important;
  border-radius: 6px !important;
  font-size: 0.875rem !important;
  min-height: 38px !important;
  color: #0A1628 !important;
  cursor: pointer !important;
  transition: border-color 0.15s ease, box-shadow 0.15s ease !important;
}
.main [data-baseweb="select"] > div:hover { border-color: #94A3B8 !important; }
.main [data-baseweb="select"]:focus-within > div {
  border-color: #0297C8 !important;
  box-shadow: 0 0 0 3px rgba(2,151,200,0.15) !important;
}

/* Force pointer on ALL select internals — input inside BaseWeb select defaults to text cursor */
[data-baseweb="select"],
[data-baseweb="select"] > div,
[data-baseweb="select"] > div *,
[data-baseweb="select"] input,
[data-baseweb="select"] [data-baseweb="icon"],
[data-baseweb="select"] svg {
  cursor: pointer !important;
}
/* Sidebar select */
[data-testid="stSidebar"] [data-baseweb="select"],
[data-testid="stSidebar"] [data-baseweb="select"] > div,
[data-testid="stSidebar"] [data-baseweb="select"] > div *,
[data-testid="stSidebar"] [data-baseweb="select"] input {
  cursor: pointer !important;
}

/* ── Dropdown popover (portaled to <body>) ── */
body [data-baseweb="popover"] {
  font-family: 'Inter', -apple-system, sans-serif !important;
}
body [data-baseweb="popover"] > div,
body [data-baseweb="popover"] [data-baseweb="menu"] {
  background: white !important;
  border: 1px solid #E2E8F0 !important;
  border-radius: 8px !important;
  box-shadow: 0 8px 24px rgba(15,23,42,0.12), 0 2px 6px rgba(15,23,42,0.06) !important;
  padding: 4px !important;
  margin-top: 4px !important;
  overflow: hidden !important;
}

body [data-testid="stSelectboxVirtualDropdown"] {
  background: white !important;
  border-radius: 6px !important;
  padding: 2px !important;
}
body [data-testid="stSelectboxVirtualDropdown"]::-webkit-scrollbar { width: 6px; }
body [data-testid="stSelectboxVirtualDropdown"]::-webkit-scrollbar-thumb { background: #CBD5E0; border-radius: 6px; }

/* Every option — list element + role=option + dropdown items.
   BaseWeb sets inline styles via emotion; we use very high specificity + !important. */
body [data-testid="stSelectboxVirtualDropdown"] li,
body [data-testid="stSelectboxVirtualDropdown"] [role="option"],
body [data-baseweb="menu"] [role="option"],
body [data-baseweb="menu"] li {
  font-family: 'Inter', -apple-system, sans-serif !important;
  font-size: 0.875rem !important;
  font-weight: 400 !important;
  color: #1A202C !important;
  background: white !important;
  background-color: white !important;
  padding: 0.55rem 0.75rem !important;
  border-radius: 5px !important;
  border: none !important;
  cursor: pointer !important;
  line-height: 1.45 !important;
  transition: background-color 0.1s ease, color 0.1s ease !important;
  list-style: none !important;
}

/* Hover (mouse) */
body [data-testid="stSelectboxVirtualDropdown"] li:hover,
body [data-testid="stSelectboxVirtualDropdown"] [role="option"]:hover,
body [data-baseweb="menu"] [role="option"]:hover,
body [data-baseweb="menu"] li:hover {
  background: #F0F9FD !important;
  background-color: #F0F9FD !important;
  color: #0177A0 !important;
}

/* Highlighted via keyboard ($isHighlighted prop sets aria-selected) */
body [data-testid="stSelectboxVirtualDropdown"] li[aria-selected="true"],
body [data-testid="stSelectboxVirtualDropdown"] [role="option"][aria-selected="true"],
body [data-baseweb="menu"] [role="option"][aria-selected="true"],
body [data-baseweb="menu"] li[aria-selected="true"] {
  background: #EBF8FF !important;
  background-color: #EBF8FF !important;
  color: #0177A0 !important;
  font-weight: 600 !important;
}

/* Disabled options */
body [data-baseweb="menu"] [role="option"][aria-disabled="true"],
body [data-testid="stSelectboxVirtualDropdown"] li[aria-disabled="true"] {
  color: #A0AEC0 !important;
  cursor: not-allowed !important;
  background: white !important;
}

/* Textareas */
.stTextArea textarea {
  background: #FAFAFA !important;
  border: 1px solid #E2E8F0 !important;
  border-radius: 6px !important;
  font-family: 'JetBrains Mono', monospace !important;
  font-size: 0.82rem !important;
  color: #0A1628 !important;
  line-height: 1.65 !important;
}
.stTextArea textarea:focus {
  border-color: #0297C8 !important;
  box-shadow: 0 0 0 3px rgba(2,151,200,0.12) !important;
}

/* Code blocks */
[data-testid="stCodeBlock"] pre {
  background: #F7F8FA !important;
  border: 1px solid #E2E8F0 !important;
  border-radius: 6px !important;
  font-size: 0.82rem !important;
}

/* Labels */
[data-testid="stSidebar"] label, label { font-size: 0.8rem !important; font-weight: 500 !important; }

/* Success/error/info */
[data-testid="stAlert"] { border-radius: 8px !important; border-left-width: 3px !important; }

/* ── Custom components ── */

/* Sidebar header */
.sb-header {
  background: #0A1628;
  padding: 1.25rem 1.4rem 1rem;
  border-bottom: 1px solid #1E3354;
  margin-bottom: 0.25rem;
}
.sb-brand {
  display: flex; align-items: center; gap: 0.6rem; margin-bottom: 0.2rem;
}
.sb-logo {
  width: 30px; height: 30px; border-radius: 7px;
  background: #0297C8;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.sb-brand-name { font-size: 1rem; font-weight: 700; color: white; letter-spacing: -0.01em; }
.sb-brand-sub { font-size: 0.72rem; color: #6B8AB0; letter-spacing: 0.01em; margin-top: 0.05rem; }

/* Sidebar sections */
.sb-section {
  padding: 0.75rem 1.25rem;
  border-bottom: 1px solid #1E3354;
}
.sb-label {
  font-size: 0.65rem; font-weight: 600; letter-spacing: 0.09em;
  text-transform: uppercase; color: #4A6A8C; margin-bottom: 0.6rem;
}
.sb-meta-row {
  display: flex; justify-content: space-between; align-items: baseline;
  padding: 0.28rem 0; font-size: 0.8rem;
}
.sb-meta-key { color: #6B8AB0; }
.sb-meta-val { color: #C8D8EC; font-weight: 500; font-family: 'JetBrains Mono', monospace; font-size: 0.75rem; }
.sb-status-open { color: #34D399; }
.sb-status-reviewed { color: #93C5FD; }

/* Pipeline steps */
.sb-pipeline { padding: 0.75rem 1.25rem 1rem; }
.sb-step {
  display: flex; align-items: flex-start; gap: 0.6rem;
  padding: 0.22rem 0; font-size: 0.78rem; color: #6B8AB0;
}
.sb-step-num {
  width: 18px; height: 18px; border-radius: 50%;
  background: #1A2E4A; border: 1px solid #2A4066;
  display: flex; align-items: center; justify-content: center;
  font-size: 0.62rem; font-weight: 700; color: #4A6A8C;
  flex-shrink: 0; margin-top: 0.05rem;
}

/* Page header */
.page-header {
  display: flex; align-items: flex-start; justify-content: space-between;
  margin-bottom: 1.5rem; padding-bottom: 1.1rem;
  border-bottom: 1px solid #E2E8F0;
}
.page-title { font-size: 1.5rem; font-weight: 700; color: #0A1628; letter-spacing: -0.02em; margin: 0; }
.page-meta { font-size: 0.8rem; color: #718096; margin-top: 0.25rem; font-family: 'JetBrains Mono', monospace; }
.nasdaq-badge {
  display: flex; align-items: center; gap: 0.45rem;
  background: #F0F9FD; border: 1px solid #BAE6F7;
  border-radius: 6px; padding: 0.35rem 0.7rem;
  font-size: 0.72rem; font-weight: 600; color: #0297C8; letter-spacing: 0.02em;
}

/* Metric cards (hero) */
.metrics-row {
  display: grid; grid-template-columns: repeat(3, 1fr);
  gap: 0.75rem; margin-bottom: 1.5rem;
}
.metric-card {
  background: white; border: 1px solid #E2E8F0; border-radius: 10px;
  padding: 1.2rem 1.4rem;
  box-shadow: 0 1px 4px rgba(0,0,0,0.05);
  transition: box-shadow 0.15s ease;
}
.metric-card:hover { box-shadow: 0 4px 12px rgba(0,0,0,0.08); }
.metric-card-label {
  font-size: 0.68rem; font-weight: 600; letter-spacing: 0.08em;
  text-transform: uppercase; color: #718096; margin-bottom: 0.65rem;
  display: flex; align-items: center; gap: 0.4rem;
}
.metric-card-value { font-size: 1.4rem; font-weight: 700; letter-spacing: -0.02em; line-height: 1.1; }
.metric-card-sub { font-size: 0.78rem; color: #718096; margin-top: 0.4rem; }

/* Tier badge */
.tier-badge {
  display: inline-flex; align-items: center; gap: 0.4rem;
  padding: 0.3rem 0.75rem; border-radius: 999px;
  font-size: 0.72rem; font-weight: 700; letter-spacing: 0.05em;
  border: 1px solid;
}

/* Action badge */
.action-badge {
  display: inline-flex; align-items: center; gap: 0.45rem;
  padding: 0.35rem 0.8rem; border-radius: 6px;
  font-size: 0.8rem; font-weight: 600;
  border: 1px solid;
}

/* Section header */
.section-hdr {
  display: flex; align-items: center; gap: 0.5rem;
  font-size: 0.78rem; font-weight: 600; letter-spacing: 0.06em;
  text-transform: uppercase; color: #4A5568;
  margin: 1.5rem 0 0.75rem;
}
.section-hdr-line {
  flex: 1; height: 1px; background: #E2E8F0;
}

/* Red flag cards */
.flag-list { display: flex; flex-direction: column; gap: 0.6rem; margin-bottom: 0.5rem; }
.flag-card {
  background: white; border: 1px solid #E2E8F0; border-radius: 8px;
  display: flex; overflow: hidden;
  box-shadow: 0 1px 3px rgba(0,0,0,0.04);
  transition: border-color 0.12s ease, box-shadow 0.12s ease;
}
.flag-card:hover { border-color: #CBD5E0; box-shadow: 0 3px 10px rgba(0,0,0,0.07); }
.flag-rail { width: 4px; flex-shrink: 0; }
.flag-body { padding: 0.9rem 1.1rem; flex: 1; }
.flag-row-top {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 0.45rem;
}
.sev-badge {
  font-size: 0.62rem; font-weight: 700; letter-spacing: 0.08em;
  text-transform: uppercase; padding: 0.18rem 0.55rem; border-radius: 4px; border: 1px solid;
}
.flag-desc { font-size: 0.9rem; line-height: 1.55; color: #2D3748; margin-bottom: 0.55rem; }
.cite-row { display: flex; flex-wrap: wrap; gap: 0.3rem; }

/* Citation chips */
.cite-chip {
  display: inline-flex; align-items: center; gap: 0.3rem;
  font-family: 'JetBrains Mono', monospace; font-size: 0.69rem; font-weight: 500;
  background: #F0F9FD; color: #0177A0; border: 1px solid #BAE6F7;
  padding: 0.18rem 0.5rem; border-radius: 4px;
}
.cite-type {
  font-size: 0.58rem; font-weight: 700; letter-spacing: 0.04em;
  background: #BAE6F7; color: #0177A0; padding: 0.08rem 0.3rem; border-radius: 3px;
}

/* Reasoning card */
.reasoning-card {
  background: white; border: 1px solid #E2E8F0; border-radius: 8px;
  padding: 1.2rem 1.4rem;
  box-shadow: 0 1px 3px rgba(0,0,0,0.04);
  margin-bottom: 0.5rem;
}
.reasoning-text { font-size: 0.9rem; line-height: 1.65; color: #2D3748; margin-bottom: 0.8rem; }

/* SAR draft */
.sar-card {
  background: white; border: 1px solid #E2E8F0; border-radius: 8px;
  overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.04);
  margin-bottom: 0.5rem;
}
.sar-toolbar {
  background: #F7F8FA; border-bottom: 1px solid #E2E8F0;
  padding: 0.6rem 1.1rem;
  display: flex; justify-content: space-between; align-items: center;
}
.sar-toolbar-left { display: flex; align-items: center; gap: 0.5rem; font-size: 0.75rem; font-weight: 600; color: #4A5568; }
.sar-toolbar-right { font-size: 0.72rem; font-weight: 600; color: #059669; display: flex; align-items: center; gap: 0.3rem; }
.sar-body {
  padding: 1.1rem 1.3rem;
  font-family: 'JetBrains Mono', monospace; font-size: 0.82rem;
  line-height: 1.7; color: #1A202C; white-space: pre-wrap;
}

/* Audit timeline */
.audit-header {
  display: flex; align-items: center; gap: 0.6rem;
  padding: 0.6rem 0.9rem; border-radius: 6px;
  font-size: 0.82rem; font-weight: 500; margin-bottom: 1rem;
}
.audit-ok { background: #ECFDF5; border: 1px solid #A7F3D0; color: #047857; }
.audit-bad { background: #FEF2F2; border: 1px solid #FECACA; color: #B91C1C; }
.timeline { position: relative; padding-left: 1.5rem; }
.timeline::before {
  content: ''; position: absolute; left: 6px; top: 14px; bottom: 14px;
  width: 1.5px; background: #E2E8F0;
}
.tl-row {
  position: relative; margin-bottom: 0.65rem;
  background: white; border: 1px solid #E2E8F0; border-radius: 6px;
  padding: 0.65rem 0.9rem;
  box-shadow: 0 1px 2px rgba(0,0,0,0.04);
}
.tl-row::before {
  content: ''; position: absolute; left: -1.5rem; top: 50%; transform: translateY(-50%);
  width: 11px; height: 11px; border-radius: 50%;
  background: #0297C8; border: 2.5px solid white;
  box-shadow: 0 0 0 1.5px #0297C8;
}
.tl-row-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.25rem; }
.tl-step { font-size: 0.82rem; font-weight: 600; color: #0A1628; }
.tl-ts { font-size: 0.7rem; color: #718096; font-family: 'JetBrains Mono', monospace; }
.tl-hashes { display: flex; gap: 1.5rem; font-family: 'JetBrains Mono', monospace; font-size: 0.69rem; color: #718096; }
.tl-hash-val { color: #0177A0; }

/* Diff panes */
.diff-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem; }
.diff-pane { border: 1px solid #E2E8F0; border-radius: 8px; overflow: hidden; }
.diff-head {
  background: #F7F8FA; border-bottom: 1px solid #E2E8F0;
  padding: 0.55rem 0.9rem;
  display: flex; justify-content: space-between; align-items: center;
  font-size: 0.7rem; font-weight: 600; color: #4A5568; letter-spacing: 0.05em; text-transform: uppercase;
}
.diff-sensitive { color: #DC2626; }
.diff-safe { color: #059669; }
.diff-body {
  padding: 0.9rem 1rem; font-family: 'JetBrains Mono', monospace;
  font-size: 0.79rem; line-height: 1.65; color: #1A202C;
  white-space: pre-wrap; max-height: 340px; overflow-y: auto; background: white;
}
.tok-span {
  background: #EBF8FF; color: #0177A0; padding: 0.06rem 0.35rem;
  border-radius: 3px; border: 1px solid #BAE6F7;
  font-weight: 500;
}

/* Empty state */
.empty-state {
  background: white; border: 1.5px dashed #CBD5E0; border-radius: 10px;
  padding: 4rem 2rem; text-align: center;
}
.empty-icon { color: #CBD5E0; margin-bottom: 0.85rem; }
.empty-title { font-size: 1rem; font-weight: 600; color: #4A5568; margin-bottom: 0.35rem; }
.empty-body { font-size: 0.875rem; color: #718096; }
.empty-cta { color: #0297C8; font-weight: 600; }

/* Feedback row */
.feedback-note { font-size: 0.78rem; color: #718096; padding-top: 0.5rem; }

/* Scrollbars */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: #CBD5E0; border-radius: 10px; }
::-webkit-scrollbar-thumb:hover { background: #A0AEC0; }
</style>
"""


# ─── Helpers ─────────────────────────────────────────────────────────────────
def tier_badge(tier: str) -> str:
    t = TIER.get(tier, TIER["low"])
    return (f'<span class="tier-badge" style="color:{t["color"]};background:{t["bg"]};border-color:{t["border"]}">'
            f'<span style="display:inline-block;width:7px;height:7px;border-radius:50%;background:{t["color"]};'
            f'box-shadow:0 0 6px {t["color"]}55;"></span>{t["label"]}</span>')


def action_badge(action: str) -> str:
    a = ACTION.get(action, ACTION["monitor"])
    t = TIER.get(a["tier"], TIER["low"])
    return (f'<span class="action-badge" style="color:{t["color"]};background:{t["bg"]};border-color:{t["border"]}">'
            f'{icon(a["icon"], 14, t["color"])}&nbsp;{a["label"]}</span>')


def sev_badge(severity: str) -> str:
    t = TIER.get(severity, TIER["low"])
    return (f'<span class="sev-badge" style="color:{t["color"]};background:{t["bg"]};border-color:{t["border"]}">'
            f'{t["label"]}</span>')


def cite_chip(c) -> str:
    label = SOURCE.get(c.source_type, "REF")
    return (f'<span class="cite-chip"><span class="cite-type">{label}</span>{c.source_id}</span>')


def highlight_tokens(text: str) -> str:
    import re
    return re.sub(r'(\[[A-Z_]+_[A-Z0-9]{3,}\])', r'<span class="tok-span">\1</span>', text)


def typology_label(t: str) -> str:
    return {"structuring": "Structuring", "trade_based_ml": "Trade-Based ML",
            "shell_company_layering": "Shell Company Layering", "rapid_movement": "Rapid Movement"}.get(t, t or "—")


@st.cache_resource
def _conn_cache():
    return get_conn()


def _conn():
    conn = _conn_cache()
    if getattr(conn, "closed", 1):
        _conn_cache.clear()
        conn = _conn_cache()
    return conn


@st.cache_data(ttl=60)
def load_alerts():
    with _conn().cursor() as cur:
        cur.execute(
            """SELECT a.id, a.typology, a.status, a.created_at,
                      e.name, e.country, a.ground_truth
               FROM alerts a
               JOIN transactions t ON t.id = a.transaction_id
               JOIN entities e ON e.id = t.sender_id
               ORDER BY a.id""",
        )
        return cur.fetchall()


# ─── Boot ────────────────────────────────────────────────────────────────────
st.markdown(CSS.replace("{favicon}", FAVICON_SVG), unsafe_allow_html=True)

# JS: ensure the sidebar expand-button is always accessible from the parent frame.
# Streamlit strips <script> tags from st.markdown, so we use an invisible iframe
# that posts a message up to window.parent, which CAN access stExpandSidebarButton.
components.html(
    """
    <script>
    (function() {
      function fix() {
        try {
          var doc = window.parent.document;
          // Ensure toolbar container is visible
          ['stToolbar','stHeaderActionElements','stToolbarActions'].forEach(function(id) {
            var el = doc.querySelector('[data-testid="' + id + '"]');
            if (el) {
              el.style.setProperty('display','flex','important');
              el.style.setProperty('visibility','visible','important');
              el.style.setProperty('opacity','1','important');
            }
          });
          // Ensure expand button itself is visible
          var btn = doc.querySelector('button[data-testid="stExpandSidebarButton"]');
          if (btn) {
            btn.style.setProperty('display','flex','important');
            btn.style.setProperty('visibility','visible','important');
            btn.style.setProperty('opacity','1','important');
            btn.style.setProperty('pointer-events','auto','important');
          }
        } catch(e) {}
      }
      fix();
      // Re-run on every DOM mutation (React re-renders)
      var obs = new MutationObserver(fix);
      obs.observe(window.parent.document.body, {childList:true, subtree:true, attributes:true});
    })();
    </script>
    """,
    height=0,
)

conn = _conn()
alerts = load_alerts()

# ─── Sidebar ─────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        '<div class="sb-header">'
        '<div class="sb-brand">'
        '<div class="sb-logo">'
        '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>'
        '</div>'
        '<div><div class="sb-brand-name">AML Copilot</div></div>'
        '</div>'
        '<div class="sb-brand-sub">Nasdaq Verafin · Financial Crime Management</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    if not alerts:
        st.warning("No alerts. Run the seed script first.")
        st.stop()

    st.markdown('<div class="sb-section">', unsafe_allow_html=True)
    st.markdown('<div class="sb-label">Alert Queue</div>', unsafe_allow_html=True)
    options = {f"#{r[0]}  ·  {typology_label(r[1])}": r[0] for r in alerts}
    selected_label = st.selectbox("alert", list(options.keys()), label_visibility="collapsed")
    alert_id = options[selected_label]
    st.markdown("</div>", unsafe_allow_html=True)

    row = next(r for r in alerts if r[0] == alert_id)
    _, typology, status, created_at, sender_name, country, ground_truth = row

    status_class = "sb-status-open" if status == "open" else "sb-status-reviewed"
    st.markdown(
        f'<div class="sb-section">'
        f'<div class="sb-label">Case Details</div>'
        f'<div class="sb-meta-row"><span class="sb-meta-key">Alert ID</span><span class="sb-meta-val">#{alert_id}</span></div>'
        f'<div class="sb-meta-row"><span class="sb-meta-key">Typology</span><span class="sb-meta-val">{typology_label(typology)}</span></div>'
        f'<div class="sb-meta-row"><span class="sb-meta-key">Status</span><span class="sb-meta-val {status_class}">{status}</span></div>'
        f'<div class="sb-meta-row"><span class="sb-meta-key">Generated</span><span class="sb-meta-val">{created_at.strftime("%Y-%m-%d") if created_at else "—"}</span></div>'
        f'<div class="sb-meta-row"><span class="sb-meta-key">Subject</span><span class="sb-meta-val">{sender_name[:20]}</span></div>'
        f'<div class="sb-meta-row"><span class="sb-meta-key">Jurisdiction</span><span class="sb-meta-val">{country or "—"}</span></div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    st.markdown('<div class="sb-section" style="padding-bottom:1rem">', unsafe_allow_html=True)
    run_clicked = st.button("▶  Run Triage", type="primary")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown(
        '<div class="sb-pipeline">'
        '<div class="sb-label">Pipeline</div>'
        '<div class="sb-step"><div class="sb-step-num">1</div><span>Fetch raw alert</span></div>'
        '<div class="sb-step"><div class="sb-step-num">2</div><span>PII redaction · Presidio</span></div>'
        '<div class="sb-step"><div class="sb-step-num">3</div><span>Embed tokenized narrative</span></div>'
        '<div class="sb-step"><div class="sb-step-num">4</div><span>Retrieve regs / cases / history</span></div>'
        '<div class="sb-step"><div class="sb-step-num">5</div><span>Claude Sonnet 4.6 · tool_use</span></div>'
        '<div class="sb-step"><div class="sb-step-num">6</div><span>Validate · rehydrate PII</span></div>'
        '<div class="sb-step"><div class="sb-step-num">7</div><span>SHA-256 hash-chain audit</span></div>'
        '</div>',
        unsafe_allow_html=True,
    )

# ─── Run triage ──────────────────────────────────────────────────────────────
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

# ─── Page header ─────────────────────────────────────────────────────────────
ts_str = created_at.strftime("%Y-%m-%d %H:%M UTC") if created_at else "—"
st.markdown(
    f'<div class="page-header">'
    f'<div>'
    f'<div class="page-title">AML Triage Brief</div>'
    f'<div class="page-meta">Alert #{alert_id} · {typology_label(typology)} · {ts_str}</div>'
    f'</div>'
    f'<div class="nasdaq-badge">'
    f'<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#0297C8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>'
    f'NASDAQ VERAFIN'
    f'</div>'
    f'</div>',
    unsafe_allow_html=True,
)

# ─── Empty state ─────────────────────────────────────────────────────────────
if result is None:
    st.markdown(
        '<div class="empty-state">'
        '<div class="empty-icon">'
        '<svg width="44" height="44" viewBox="0 0 24 24" fill="none" stroke="#CBD5E0" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>'
        '</div>'
        '<div class="empty-title">No triage executed for this alert</div>'
        '<div class="empty-body">Select an alert from the queue and click '
        '<span class="empty-cta">▶ Run Triage</span> to generate a compliance-grade brief.</div>'
        '</div>',
        unsafe_allow_html=True,
    )
    st.stop()

brief = result.brief
t_tier = TIER.get(brief.risk_tier, TIER["low"])
t_action = TIER.get(ACTION[brief.recommended_action]["tier"], TIER["low"])

# ─── Metric cards ─────────────────────────────────────────────────────────────
st.markdown(
    f'''
<div class="metrics-row">
  <div class="metric-card" style="border-top: 3px solid {t_tier["color"]}">
    <div class="metric-card-label">
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#718096" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
      Risk Tier
    </div>
    <div class="metric-card-value" style="color:{t_tier["color"]}">{tier_badge(brief.risk_tier)}</div>
    <div class="metric-card-sub">Calibrated against ~95% FP base rate</div>
  </div>
  <div class="metric-card" style="border-top: 3px solid {t_action["color"]}">
    <div class="metric-card-label">
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#718096" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z M12 9v4 M12 17h.01"/></svg>
      Recommended Action
    </div>
    <div class="metric-card-value">{action_badge(brief.recommended_action)}</div>
    <div class="metric-card-sub">Analyst confirmation required</div>
  </div>
  <div class="metric-card" style="border-top: 3px solid #0297C8">
    <div class="metric-card-label">
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#718096" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><polyline points="22,12 18,12 15,21 9,3 6,12 2,12"/></svg>
      Typology Match
    </div>
    <div class="metric-card-value" style="font-size:1.1rem;color:#0A1628;line-height:1.3">{brief.typology_match}</div>
    <div class="metric-card-sub">{len(brief.red_flags)} red flag{"s" if len(brief.red_flags)!=1 else ""} · {len(brief.reasoning_citations)} citation{"s" if len(brief.reasoning_citations)!=1 else ""}</div>
  </div>
</div>
''',
    unsafe_allow_html=True,
)

# ─── Red flags ────────────────────────────────────────────────────────────────
st.markdown(
    '<div class="section-hdr">'
    '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#4A5568" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z M4 22v-7"/></svg>'
    f'Red Flags <span style="font-weight:400;color:#718096;letter-spacing:0">({len(brief.red_flags)})</span>'
    '<div class="section-hdr-line"></div></div>',
    unsafe_allow_html=True,
)

flags_html = '<div class="flag-list">'
for flag in brief.red_flags:
    rail_color = TIER.get(flag.severity, TIER["low"])["border"]
    cites_html = "".join(cite_chip(c) for c in flag.citations)
    flags_html += (
        f'<div class="flag-card">'
        f'<div class="flag-rail" style="background:{rail_color}"></div>'
        f'<div class="flag-body">'
        f'<div class="flag-row-top">{sev_badge(flag.severity)}</div>'
        f'<div class="flag-desc">{flag.description}</div>'
        f'<div class="cite-row">{cites_html}</div>'
        f'</div></div>'
    )
flags_html += "</div>"
st.markdown(flags_html, unsafe_allow_html=True)

# ─── Reasoning ───────────────────────────────────────────────────────────────
cites_html = "".join(cite_chip(c) for c in brief.reasoning_citations)
st.markdown(
    '<div class="section-hdr">'
    '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#4A5568" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>'
    'Reasoning Summary<div class="section-hdr-line"></div></div>',
    unsafe_allow_html=True,
)
st.markdown(
    f'<div class="reasoning-card">'
    f'<div class="reasoning-text">{brief.reasoning_summary}</div>'
    f'<div class="cite-row">{cites_html}</div>'
    f'</div>',
    unsafe_allow_html=True,
)

# ─── SAR draft ───────────────────────────────────────────────────────────────
if brief.sar_narrative_draft and brief.sar_narrative_draft.strip():
    st.markdown(
        '<div class="section-hdr">'
        '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#4A5568" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z M14 2v6h6"/></svg>'
        'SAR Narrative Draft<div class="section-hdr-line"></div></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="sar-card">'
        f'<div class="sar-toolbar">'
        f'<div class="sar-toolbar-left">'
        f'<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#4A5568" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z M14 2v6h6"/></svg>'
        f'FinCEN Form 111 · Who / What / When / Where / Why / How'
        f'</div>'
        f'<div class="sar-toolbar-right">'
        f'<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#059669" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6L9 17l-5-5"/></svg>'
        f'PII rehydrated</div>'
        f'</div>'
        f'<div class="sar-body">{brief.sar_narrative_draft}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

# ─── Expanders ───────────────────────────────────────────────────────────────
with st.expander("Raw vs Tokenized Narrative"):
    raw_esc = result.raw_narrative.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    tok_esc = result.tokenized_narrative.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    tok_highlighted = highlight_tokens(tok_esc)
    st.markdown(
        f'<div class="diff-grid">'
        f'<div class="diff-pane">'
        f'<div class="diff-head"><span>Raw · With PII</span><span class="diff-sensitive">SENSITIVE</span></div>'
        f'<div class="diff-body">{raw_esc}</div>'
        f'</div>'
        f'<div class="diff-pane">'
        f'<div class="diff-head"><span>Tokenized · Sent to LLM</span><span class="diff-safe">PII-SAFE</span></div>'
        f'<div class="diff-body">{tok_highlighted}</div>'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )
    if result.token_map:
        st.markdown("<br>**Token Map**", unsafe_allow_html=True)
        st.json(result.token_map, expanded=False)

with st.expander("Audit Trail · SHA-256 Hash Chain"):
    chain_valid = verify_chain(conn, alert_id)
    status_cls = "audit-ok" if chain_valid else "audit-bad"
    status_icon = '<path d="M20 6L9 17l-5-5"/>' if chain_valid else '<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>'
    status_color = "#047857" if chain_valid else "#B91C1C"
    status_text = "Hash chain intact — no tampering detected · SR 11-7 compliant" if chain_valid else "Hash chain INVALID — potential tampering detected"
    st.markdown(
        f'<div class="audit-header {status_cls}">'
        f'<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="{status_color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">{status_icon}</svg>'
        f'{status_text}</div>',
        unsafe_allow_html=True,
    )

    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, step, prev_hash, curr_hash, created_at FROM audit_log WHERE alert_id=%s ORDER BY id",
            (alert_id,),
        )
        rows = cur.fetchall()

    tl = '<div class="timeline">'
    for log_id, step, prev_hash, curr_hash, ts in rows:
        prev_d = (prev_hash[:12] + "…") if prev_hash else "GENESIS"
        curr_d = curr_hash[:12] + "…"
        ts_d = ts.strftime("%H:%M:%S") if ts else "—"
        tl += (
            f'<div class="tl-row">'
            f'<div class="tl-row-head">'
            f'<span class="tl-step">{step.replace("_", " ").title()}</span>'
            f'<span class="tl-ts">{ts_d} · log #{log_id}</span>'
            f'</div>'
            f'<div class="tl-hashes">'
            f'<span>prev <span class="tl-hash-val">{prev_d}</span></span>'
            f'<span>curr <span class="tl-hash-val">{curr_d}</span></span>'
            f'</div>'
            f'</div>'
        )
    tl += "</div>"
    st.markdown(tl, unsafe_allow_html=True)

with st.expander("SQL Executed · Entity History Retrieval"):
    st.code(result.sql_executed.strip(), language="sql")

# ─── Analyst disposition ─────────────────────────────────────────────────────
st.markdown(
    '<div class="section-hdr">'
    '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#4A5568" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2 M12 3a4 4 0 1 0 0 8 4 4 0 0 0 0-8z"/></svg>'
    'Analyst Disposition<div class="section-hdr-line"></div></div>',
    unsafe_allow_html=True,
)

fc1, fc2, fc3 = st.columns([2, 3, 1])
with fc1:
    disposition = st.selectbox(
        "disposition",
        ["— pending analyst review —", "true_positive", "false_positive"],
        key=f"gt_{alert_id}",
        label_visibility="collapsed",
    )
with fc2:
    st.markdown(
        '<div class="feedback-note">AI recommendations are advisory only. '
        'A licensed analyst must make the final determination before any regulatory action.</div>',
        unsafe_allow_html=True,
    )
with fc3:
    save_clicked = st.button("Save", key=f"fb_{alert_id}", use_container_width=True)

if save_clicked:
    if "pending" in disposition:
        st.warning("Select a disposition before saving.")
    else:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE alerts SET ground_truth=%s, status='reviewed' WHERE id=%s",
                (disposition, alert_id),
            )
        conn.commit()
        st.toast(f"Disposition saved: {disposition.replace('_', ' ').title()}", icon="✅")
