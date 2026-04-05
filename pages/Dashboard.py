import streamlit as st
import pandas as pd
from db import supabase

st.set_page_config(page_title="Cross Courts Dashboard", layout="wide")

# =========================================================
# ✅ Load Project List
# =========================================================
projects = supabase.table("projects").select("*").order("project_id").execute().data
project_map = {p["project_name"]: p["project_id"] for p in projects}

st.title("📊 Cross Courts Dashboard")

selected_project = st.selectbox("Select Project", list(project_map.keys()))
project_id = project_map[selected_project]


# =========================================================
# ✅ Helper Functions
# =========================================================

def load_revenue(project_id):
    rows = (
        supabase.table("project_revenue")
        .select("amount, revenue_date")
        .eq("project_id", project_id)
        .execute()
        .data
    )
    df = pd.DataFrame(rows)
    if not df.empty:
        df["revenue_date"] = pd.to_datetime(df["revenue_date"])
    return df


def load_paybacks(project_id):
    rows = (
        supabase.table("shareholder_payments")
        .select("amount_paid, payment_date")
        .eq("project_id", project_id)
        .execute()
        .data
    )
    df = pd.DataFrame(rows)
    if not df.empty:
        df["payment_date"] = pd.to_datetime(df["payment_date"])
    return df


def load_contributions(project_id):
    rows = (
        supabase.table("shareholder_contributions")
        .select("amount")
        .eq("project_id", project_id)
        .execute()
        .data
    )
    df = pd.DataFrame(rows)
    return df


# =========================================================
# ✅ Load Data
# =========================================================
rev_df = load_revenue(project_id)
pay_df = load_paybacks(project_id)
cont_df = load_contributions(project_id)

total_revenue = rev_df["amount"].sum() if not rev_df.empty else 0
total_payback = pay_df["amount_paid"].sum() if not pay_df.empty else 0
total_contribution = cont_df["amount"].sum() if not cont_df.empty else 0


# =========================================================
# ✅ KPI CARDS (NO ROI, NO RETAINED)
# =========================================================
col1, col2, col3 = st.columns(3)

col1.metric("Total Revenue", f"₹{total_revenue:,.0f}")
col2.metric("Total Shareholder Contribution", f"₹{total_contribution:,.0f}")
col3.metric("Total Payback", f"₹{total_payback:,.0f}")

# =========================================================
# ✅ Revenue Trend (Monthly)
# =========================================================
st.markdown("### 📈 Revenue Trend (Monthly)")

if rev_df.empty:
    st.info("No revenue data available.")
else:
    rev_df["month"] = rev_df["revenue_date"].dt.to_period("M")
    rev_monthly = rev_df.groupby("month")["amount"].sum().to_frame()
    rev_monthly.index = rev_monthly.index.to_timestamp()

    st.line_chart(rev_monthly)


# =========================================================
# ✅ Shareholder Payback Trend (Monthly)
# =========================================================
st.markdown("### 💸 Shareholder Payback Trend (Monthly)")

if pay_df.empty:
    st.info("No payback data available.")
else:
    pay_df["month"] = pay_df["payment_date"].dt.to_period("M")
    pay_monthly = pay_df.groupby("month")["amount_paid"].sum().to_frame()
    pay_monthly.index = pay_monthly.index.to_timestamp()

    st.line_chart(pay_monthly)


# =========================================================
# ✅ Revenue vs Payback Comparison
# =========================================================
st.markdown("### 🔄 Revenue vs Payback Comparison")

if rev_df.empty or pay_df.empty:
    st.info("Not enough data to compare revenue and payback.")
else:
    combined = rev_monthly.join(pay_monthly, how="outer").fillna(0)
    combined.columns = ["Revenue", "Payback"]

    st.bar_chart(combined)

# =========================================================
# ✅ Monthly Revenue Table (optional)
# =========================================================
st.markdown("### 📊 Monthly Revenue Table")

if not rev_df.empty:
    monthly_table = rev_monthly.copy()
    monthly_table.index = monthly_table.index.strftime("%Y-%m")
    st.dataframe(monthly_table)
else:
    st.info("No revenue data available.")
