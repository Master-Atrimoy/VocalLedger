"""Page 5 — Pattern intelligence insights."""
import streamlit as st
import requests

st.set_page_config(page_title="Insights", page_icon="🧠", layout="wide")
API = st.session_state.get("api_url", "http://localhost:8000")

SEV = {
    "warning":  ("🔴", "#ff4b4b22", "#ff4b4b"),
    "positive": ("🟢", "#21c35422", "#21c354"),
    "info":     ("🔵", "#1c83e122", "#1c83e1"),
}
TYPE_EMOJI = {
    "anomaly":"⚠️","trend":"📈","recurring":"🔄",
    "pattern":"📊","summary":"📋","split":"🤝",
}

st.title("🧠 Pattern Intelligence")
st.caption("Insights from your transaction history. Needs at least 14 days of data.")

if st.button("🔄 Generate Fresh Insights", type="primary"):
    with st.spinner("Analysing transactions..."):
        r = requests.post(f"{API}/api/insights/generate", timeout=120)
        if r.status_code == 200:
            data = r.json()
            st.success(f"Generated {data['generated']} insights")
            st.rerun()
        else:
            st.error("Generation failed — check backend logs")

try:
    insights = requests.get(f"{API}/api/insights/", timeout=10).json()
except Exception:
    insights = []
    st.error("Could not reach API")

if not insights:
    st.markdown("---")
    st.info("No insights yet. Click **Generate Fresh Insights** above.")
    st.markdown("""
**What gets detected:**
- 🔴 Spending anomalies — categories above your usual average
- 📈 3-month spend trends — rising or falling consistently
- 🔄 Recurring expenses — subscriptions and regular payments
- 📊 Weekend vs weekday patterns
- 📋 Monthly narrative summary
- 🤝 Split balances outstanding
    """)
else:
    by_type = {}
    for ins in insights:
        by_type.setdefault(ins["insight_type"], []).append(ins)

    for itype, items in by_type.items():
        emoji = TYPE_EMOJI.get(itype, "💡")
        st.markdown(f"### {emoji} {itype.title()}")
        for ins in items:
            icon, bg, border = SEV.get(ins.get("severity", "info"), SEV["info"])
            st.markdown(f"""
<div style="border-left:4px solid {border};background:{bg};
     border-radius:8px;padding:1rem 1.2rem;margin-bottom:12px;">
  <div style="font-weight:600;font-size:15px;margin-bottom:6px;">
    {icon} {ins['title']}
  </div>
  <div style="font-size:13px;line-height:1.6;">{ins['body']}</div>
  <div style="font-size:11px;color:#999;margin-top:8px;">
    Generated {ins['generated_at'][:16].replace('T',' at ')}
  </div>
</div>""", unsafe_allow_html=True)
            if st.button("Dismiss", key=f"d_{ins['id']}"):
                requests.patch(f"{API}/api/insights/{ins['id']}/dismiss", timeout=10)
                st.rerun()
        st.markdown("---")
