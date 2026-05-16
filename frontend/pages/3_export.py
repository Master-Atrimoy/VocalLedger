"""Page 3 — Export expenses with filters."""
import streamlit as st
import requests
import pandas as pd
from datetime import date

st.set_page_config(page_title="Export", page_icon="📥", layout="centered")
API = st.session_state.get("api_url", "http://localhost:8000")

CATEGORIES = ["All","Food","Transport","Shopping","Bills","Health","Entertainment","Income","Other"]

st.title("📥 Export")
st.markdown("Filter and download your transactions as CSV or JSON.")

col1, col2 = st.columns(2)
with col1:
    from_date = st.date_input("From", value=date.today().replace(day=1))
with col2:
    to_date = st.date_input("To", value=date.today())

category_filter = st.selectbox("Category", CATEGORIES)
tx_filter = st.selectbox("Type", ["All", "expense", "income"])

params = {"from_date": str(from_date), "to_date": str(to_date), "limit": 1000}
if category_filter != "All":
    params["category"] = category_filter

try:
    expenses = requests.get(f"{API}/api/expenses/", params=params, timeout=15).json()
except Exception as e:
    st.error(f"Could not reach API: {e}")
    st.stop()

if tx_filter != "All":
    expenses = [e for e in expenses if e.get("transaction_type") == tx_filter]

if not expenses:
    st.info("No transactions found for selected filters.")
else:
    df = pd.DataFrame(expenses)
    df["date"] = pd.to_datetime(df["date"])

    st.markdown(f"**{len(df)} records** · ₹{df['amount'].sum():,.0f} total")

    display_cols = ["date","amount","transaction_type","category","description","payment_method"]
    st.dataframe(
        df[display_cols].rename(columns={
            "date":"Date","amount":"Amount (₹)","transaction_type":"Type",
            "category":"Category","description":"Description","payment_method":"Payment",
        }).sort_values("Date", ascending=False),
        use_container_width=True, hide_index=True,
    )

    col_csv, col_json = st.columns(2)
    with col_csv:
        st.download_button("⬇️ Download CSV",
                           data=df[display_cols].to_csv(index=False),
                           file_name=f"expenses_{from_date}_{to_date}.csv",
                           mime="text/csv", type="primary")
    with col_json:
        st.download_button("⬇️ Download JSON",
                           data=df[display_cols].to_json(orient="records", date_format="iso", indent=2),
                           file_name=f"expenses_{from_date}_{to_date}.json",
                           mime="application/json")
