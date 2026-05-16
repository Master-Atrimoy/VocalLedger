"""Page 2 — Dashboard with charts and transaction list."""
import streamlit as st
import requests
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from datetime import date, timedelta

st.set_page_config(page_title="Dashboard", page_icon="📊", layout="wide")
API = st.session_state.get("api_url", "http://localhost:8000")


def get(ep, params=None):
    try:
        r = requests.get(f"{API}{ep}", params=params, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


st.title("📊 Dashboard")

col_p, col_f, col_t = st.columns(3)
with col_p:
    period = st.selectbox("Period", ["week", "month", "year"], index=1)
with col_f:
    from_date = st.date_input("From", value=date.today().replace(day=1))
with col_t:
    to_date = st.date_input("To", value=date.today())

st.markdown("---")

try:
    summary    = get("/api/analytics/summary", {"period": period})
    categories = get("/api/analytics/categories", {"from_date": str(from_date), "to_date": str(to_date)})
    daily      = get("/api/analytics/daily", {"days": 30})
    expenses   = get("/api/expenses/", {"from_date": str(from_date), "to_date": str(to_date), "limit": 200})
except Exception as e:
    st.error(f"Could not reach API: {e}")
    st.stop()

# ── Summary metrics ───────────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
if summary:
    net = summary.get("net", 0)
    c1.metric("Income",       f"₹{summary.get('total_income', 0):,.0f}")
    c2.metric("Expenses",     f"₹{summary.get('total_expense', 0):,.0f}")
    c3.metric("Net Balance",  f"₹{abs(net):,.0f}",
              delta="surplus" if net >= 0 else "deficit",
              delta_color="normal" if net >= 0 else "inverse")
    c4.metric("Transactions", summary.get("count", 0))
else:
    for col in [c1, c2, c3, c4]:
        col.metric("—", "—")

st.markdown("---")

# ── Charts ────────────────────────────────────────────────────────────────────
left, right = st.columns([3, 2])

with left:
    st.subheader("Daily Spend (last 30 days)")
    if daily:
        df = pd.DataFrame(daily)
        df["date"] = pd.to_datetime(df["date"])
        fig = go.Figure(go.Bar(
            x=df["date"], y=df["total"],
            marker_color="#5B8DEF",
            hovertemplate="₹%{y:,.0f}<extra>%{x|%b %d}</extra>",
        ))
        fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=280,
                          paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                          xaxis=dict(showgrid=False),
                          yaxis=dict(gridcolor="rgba(128,128,128,0.15)"))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No data yet.")

with right:
    st.subheader("By Category")
    if categories:
        df_cat = pd.DataFrame(categories)
        fig2 = go.Figure(go.Pie(
            labels=df_cat["category"], values=df_cat["total"],
            hole=0.5, textinfo="label+percent",
            hovertemplate="%{label}: ₹%{value:,.0f}<extra></extra>",
            marker_colors=px.colors.qualitative.Pastel,
        ))
        fig2.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=280,
                           paper_bgcolor="rgba(0,0,0,0)", showlegend=False)
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("No category data.")

# ── Category table ────────────────────────────────────────────────────────────
if categories:
    st.subheader("Category Breakdown")
    df_cat = pd.DataFrame(categories)
    df_cat["total"]      = df_cat["total"].map(lambda x: f"₹{x:,.0f}")
    df_cat["percentage"] = df_cat["percentage"].map(lambda x: f"{x}%")
    st.dataframe(df_cat.rename(columns={"category":"Category","total":"Total",
                                        "count":"Transactions","percentage":"Share"}),
                 use_container_width=True, hide_index=True)

# ── Recent transactions ───────────────────────────────────────────────────────
st.markdown("---")
st.subheader("Transactions")

CAT_EMOJI = {"Food":"🍽️","Transport":"🚗","Shopping":"🛍️","Bills":"⚡",
             "Health":"💊","Entertainment":"🎬","Income":"💰","Other":"📦"}

if not expenses:
    st.info("No transactions in this date range.")
else:
    df = pd.DataFrame(expenses)
    df["date"] = pd.to_datetime(df["date"]).dt.strftime("%b %d, %Y")
    for _, row in df.iterrows():
        icon = CAT_EMOJI.get(row["category"], "📦")
        tx_icon = "💸" if row.get("transaction_type") == "expense" else "💰"
        cd, ca, cc, cdesc, cdel = st.columns([2, 1.5, 1.5, 3, 0.5])
        cd.write(row["date"])
        ca.write(f"{tx_icon} **₹{row['amount']:,.0f}**")
        cc.write(f"{icon} `{row['category']}`")
        cdesc.write(row.get("description") or "—")
        if cdel.button("🗑", key=f"del_{row['id']}"):
            requests.delete(f"{API}/api/expenses/{row['id']}", timeout=10)
            st.rerun()
