import streamlit as st
import requests
from datetime import date, timedelta

st.set_page_config(page_title="Voice Expense Tracker", page_icon="🎙️",
                   layout="wide", initial_sidebar_state="expanded")

if "api_url" not in st.session_state:
    st.session_state.api_url = "http://localhost:8000"

API = st.session_state.api_url


def get(endpoint, params=None):
    try:
        r = requests.get(f"{API}{endpoint}", params=params, timeout=6)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def post(endpoint, **kw):
    try:
        r = requests.post(f"{API}{endpoint}", timeout=10, **kw)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🎙️ Expense Tracker")
    st.markdown("---")

    api_url = st.text_input("Backend URL", value=st.session_state.api_url)
    if api_url != st.session_state.api_url:
        st.session_state.api_url = api_url
        API = api_url
        st.rerun()

    health = get("/health")
    if health:
        st.success("Backend online ✅")
        st.caption(f"Whisper: `{health.get('whisper', '?')}`")
    else:
        st.error("Backend offline ⚠️")
        st.caption("Run:\n```\nuvicorn backend.main:app --reload\n```")
        st.stop()

    st.markdown("---")
    st.markdown("**🤖 LLM Model**")
    ollama_info = get("/api/config/ollama-models")

    if not ollama_info or not ollama_info.get("online"):
        err = (ollama_info or {}).get("error", "Ollama unreachable")
        st.warning("Ollama offline ⚠️")
        st.caption(err)
        st.caption("Start with:\n```\nollama serve\n```")
    else:
        models = ollama_info.get("models", [])
        active = ollama_info.get("active", "")
        if not models:
            st.warning("No models found")
            st.caption("Pull one:\n```\nollama pull mistral:7b\n```")
        else:
            idx = models.index(active) if active in models else 0
            selected = st.selectbox("Active model", models, index=idx)
            if selected != active:
                with st.spinner(f"Switching to {selected}..."):
                    result = post("/api/config/model", json={"model_id": selected})
                    if result and result.get("switched"):
                        st.success("Switched ✅")
                        st.rerun()
                    else:
                        st.error("Switch failed")
            st.caption(f"Active: `{active}`  ·  {len(models)} model(s)")

    st.markdown("---")
    st.caption("All data stays on your machine.\nNo cloud. No tracking.")


# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("# 🎙️ Voice Expense Tracker")
st.markdown("Log expenses and income by **voice or text** — fully local, no cloud.")
st.markdown("---")

# ── Summary metrics ───────────────────────────────────────────────────────────
month_summary = get("/api/analytics/summary", {"period": "month"})
week_summary  = get("/api/analytics/summary", {"period": "week"})

c1, c2, c3, c4 = st.columns(4)

if month_summary:
    net = month_summary.get("net", 0)
    c1.metric("Income",   f"₹{month_summary.get('total_income', 0):,.0f}")
    c2.metric("Expenses", f"₹{month_summary.get('total_expense', 0):,.0f}")
    c3.metric("Net",      f"₹{abs(net):,.0f}",
              delta="surplus" if net >= 0 else "deficit",
              delta_color="normal" if net >= 0 else "inverse")
else:
    c1.metric("Income", "—")
    c2.metric("Expenses", "—")
    c3.metric("Net", "—")

if week_summary:
    week_net = week_summary.get("net", 0)
    c4.metric("This Week Net", f"₹{abs(week_net):,.0f}",
              delta="surplus" if week_net >= 0 else "deficit",
              delta_color="normal" if week_net >= 0 else "inverse")
else:
    c4.metric("This Week Net", "—")

st.markdown("---")

# ── Quick actions ─────────────────────────────────────────────────────────────
st.markdown("### Quick Actions")
qa1, qa2, qa3 = st.columns(3)

CARD = """<div style="border:1px solid #e0e0e0;border-radius:12px;padding:1.2rem 1.4rem;
     text-align:center;background:linear-gradient(135deg,{g1},{g2});">
  <div style="font-size:2rem">{icon}</div>
  <div style="font-weight:600;margin:.4rem 0">{title}</div>
  <div style="font-size:.85rem;color:#888">{sub}</div></div>"""

with qa1:
    st.markdown(CARD.format(icon="🎤", title="Log Transaction",
        sub="Speak or type naturally", g1="#667eea22", g2="#764ba222"), unsafe_allow_html=True)
    st.page_link("pages/1_log.py", label="→ Log now", use_container_width=True)

with qa2:
    st.markdown(CARD.format(icon="📊", title="Dashboard",
        sub="Charts, trends, breakdown", g1="#11998e22", g2="#38ef7d22"), unsafe_allow_html=True)
    st.page_link("pages/2_dashboard.py", label="→ View dashboard", use_container_width=True)

with qa3:
    st.markdown(CARD.format(icon="🤝", title="Splits",
        sub="Split expenses with friends", g1="#f0981922", g2="#edde5d22"), unsafe_allow_html=True)
    st.page_link("pages/4_splits.py", label="→ Manage splits", use_container_width=True)

st.markdown("---")

# ── Recent activity + top categories ─────────────────────────────────────────
left, right = st.columns([3, 2])
CAT_EMOJI = {"Food":"🍽️","Transport":"🚗","Shopping":"🛍️","Bills":"⚡",
             "Health":"💊","Entertainment":"🎬","Income":"💰","Other":"📦"}

with left:
    st.markdown("### Recent Activity")
    recent = get("/api/expenses/", {
        "from_date": str(date.today() - timedelta(days=7)),
        "to_date": str(date.today()), "limit": 8,
    })
    if not recent:
        st.info("No expenses yet — head to **Log** to add your first one.")
    else:
        for exp in recent:
            icon = CAT_EMOJI.get(exp["category"], "📦")
            tx_icon = "💸" if exp.get("transaction_type") == "expense" else "💰"
            ca, cb, cc = st.columns([0.5, 4, 1.5])
            ca.markdown(f"### {icon}")
            cb.markdown(f"{tx_icon} **{exp['category']}** — {exp.get('description') or '—'}")
            cb.caption(f"{exp['date']}  ·  {exp['payment_method']}")
            cc.markdown(f"**₹{exp['amount']:,.0f}**")
            st.divider()

with right:
    st.markdown("### Top Categories")
    categories = get("/api/analytics/categories")
    if categories:
        for cat in categories[:5]:
            icon = CAT_EMOJI.get(cat["category"], "📦")
            col_l, col_r = st.columns([4, 1])
            col_l.markdown(f"{icon} **{cat['category']}**")
            col_r.markdown(f"₹{cat['total']:,.0f}")
            st.progress(int(cat["percentage"]))
    else:
        st.info("Categories appear here once you log some expenses.")

    st.markdown("---")
    st.markdown("**How to use**")
    with st.expander("Step-by-step", expanded=True):
        st.markdown("""
1. Pick a model in the sidebar
2. Go to **Log** → record voice or type
3. Say: *"spent 200 on groceries"*
4. Review extracted details and save ✅
        """)
