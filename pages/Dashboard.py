import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from db import supabase

st.set_page_config(page_title="Cross Courts Dashboard", layout="wide")

# =========================================================
# ✅ LOAD PROJECT LIST
# =========================================================
projects = supabase.table("projects").select("*").order("project_id").execute().data
project_map = {p["project_name"]: p["project_id"] for p in projects}

st.title("📊 Cross Courts Shareholder & Revenue Dashboard")
selected_project = st.selectbox("Select Project", list(project_map.keys()))
project_id = project_map[selected_project]


# =========================================================
# ✅ DATA LOADERS
# =========================================================
def load_revenue(project_id):
    rows = supabase.table("project_revenue").select("amount, revenue_date").eq("project_id", project_id).execute().data
    df = pd.DataFrame(rows)
    if not df.empty:
        df["revenue_date"] = pd.to_datetime(df["revenue_date"])
    return df

def load_expenses(project_id):
    rows = supabase.table("project_expenses").select("amount, expense_date").eq("project_id", project_id).execute().data
    df = pd.DataFrame(rows)
    if not df.empty:
        df["expense_date"] = pd.to_datetime(df["expense_date"])
    return df

def load_paybacks(project_id):
    rows = supabase.table("shareholder_payments").select("amount_paid, payment_date").eq("project_id", project_id).execute().data
    df = pd.DataFrame(rows)
    if not df.empty:
        df["payment_date"] = pd.to_datetime(df["payment_date"])
    return df

def load_contributions(project_id):
    rows = supabase.table("shareholder_contributions").select("amount, contribution_date").eq("project_id", project_id).execute().data
    df = pd.DataFrame(rows)
    if not df.empty:
        df["contribution_date"] = pd.to_datetime(df["contribution_date"])
    return df


rev_df = load_revenue(project_id)
exp_df = load_expenses(project_id)
pay_df = load_paybacks(project_id)
cont_df = load_contributions(project_id)

total_revenue = rev_df["amount"].sum() if not rev_df.empty else 0
total_expenses = exp_df["amount"].sum() if not exp_df.empty else 0
total_payback = pay_df["amount_paid"].sum() if not pay_df.empty else 0
total_contribution = cont_df["amount"].sum() if not cont_df.empty else 0


# =========================================================
# ✅ PURE PYTHON XNPV + XIRR (Cloud-safe)
# =========================================================
def xnpv(rate, values, dates):
    d0 = dates[0]
    return sum([
        v / ((1 + rate) ** ((d - d0).days / 365))
        for v, d in zip(values, dates)
    ])

def xirr(values, dates, guess=0.1):
    rate = guess
    tolerance = 1e-6
    max_iter = 100

    for _ in range(max_iter):
        f = xnpv(rate, values, dates)
        df = sum([
            -((d - dates[0]).days / 365) * v / ((1 + rate) ** (((d - dates[0]).days / 365) + 1))
            for v, d in zip(values, dates)
        ])

        if df == 0:
            return None

        new_rate = rate - f / df
        if abs(new_rate - rate) < tolerance:
            return new_rate
        rate = new_rate

    return None

def compute_xirr():
    cashflows = []

    # Contributions (negative)
    if not cont_df.empty:
        for _, row in cont_df.iterrows():
            cashflows.append((row["contribution_date"], -float(row["amount"])))

    # Paybacks (positive)
    if not pay_df.empty:
        for _, row in pay_df.iterrows():
            cashflows.append((row["payment_date"], float(row["amount_paid"])))

    if len(cashflows) < 2:
        return 0

    dates = [c[0] for c in cashflows]
    values = [c[1] for c in cashflows]

    try:
        irr = xirr(values, dates)
        return irr * 100 if irr else 0
    except:
        return 0


# =========================================================
# ✅ TRAILING 12-MONTH METRICS
# =========================================================
today = datetime.today()
past_12m = today - timedelta(days=365)

rev_12 = rev_df[rev_df["revenue_date"] >= past_12m] if not rev_df.empty else pd.DataFrame()
exp_12 = exp_df[exp_df["expense_date"] >= past_12m] if not exp_df.empty else pd.DataFrame()

rev_12_sum = rev_12["amount"].sum() if not rev_12.empty else 0
exp_12_sum = exp_12["amount"].sum() if not exp_12.empty else 0

roi_actual = ((rev_12_sum - exp_12_sum) / total_contribution) * 100 if total_contribution > 0 else 0
payback_pct = (total_payback / total_contribution) * 100 if total_contribution > 0 else 0
actual_irr = compute_xirr()


# =========================================================
# ✅ KPI CARDS
# =========================================================
st.markdown("## 📘 Shareholder Health Metrics")

c1, c2, c3 = st.columns(3)
c1.metric("ROI (Trailing 12 Months)", f"{roi_actual:,.2f}%")
c2.metric("Payback %", f"{payback_pct:,.2f}%")
c3.metric("Actual IRR", f"{actual_irr:,.2f}%")


# =========================================================
# ✅ AI‑DRIVEN ALERTS
# =========================================================
st.markdown("## 🤖 AI‑Driven Alerts")

alerts = []

# Revenue drop >20%
if len(rev_df) >= 2:
    sorted_rev = rev_df.sort_values("revenue_date")
    last, prev = sorted_rev.iloc[-1]["amount"], sorted_rev.iloc[-2]["amount"]
    if prev > 0 and (prev - last) / prev * 100 > 20:
        alerts.append(("🔴 Revenue Drop", f"Revenue dropped {(prev - last)/prev*100:.1f}% MoM"))

# Expense spike >30%
if len(exp_df) >= 2:
    sorted_exp = exp_df.sort_values("expense_date")
    last, prev = sorted_exp.iloc[-1]["amount"], sorted_exp.iloc[-2]["amount"]
    if prev > 0 and (last - prev) / prev * 100 > 30:
        alerts.append(("🟧 Expense Spike", f"Expenses increased {(last - prev)/prev*100:.1f}% MoM"))

# Negative ROI
if roi_actual < 0:
    alerts.append(("🔴 Negative ROI", "ROI over trailing 12 months is negative."))

# Slow Payback
if payback_pct < 20:
    alerts.append(("🟡 Slow Payback", "Less than 20% payback achieved."))

# No payback in 60 days
if not pay_df.empty:
    last_pay = pay_df.sort_values("payment_date").iloc[-1]["payment_date"]
    if (today - last_pay).days > 60:
        alerts.append(("🟧 Dormant Payback", "No paybacks in the last 60 days."))

if not alerts:
    st.success("✅ All indicators normal.")
else:
    for icon, msg in alerts:
        st.warning(f"{icon} — {msg}")


# =========================================================
# ✅ RUN‑RATE PROJECTIONS
# =========================================================
st.markdown("## 📈 Run‑Rate Projections")

six_months_ago = today - timedelta(days=180)

rev_6m = rev_df[rev_df["revenue_date"] >= six_months_ago] if not rev_df.empty else pd.DataFrame()
exp_6m = exp_df[exp_df["expense_date"] >= six_months_ago] if not exp_df.empty else pd.DataFrame()

avg_rev = rev_6m["amount"].mean() if not rev_6m.empty else 0
avg_exp = exp_6m["amount"].mean() if not exp_6m.empty else 0
avg_surplus = avg_rev - avg_exp

allocation_pct = st.slider("Payback Allocation % of Surplus", 0.1, 1.0, 0.8)

remaining = total_contribution - total_payback
months_to_payback = remaining / (avg_surplus * allocation_pct) if avg_surplus > 0 else np.inf

st.metric("Projected Months to Break Even", "∞" if months_to_payback == np.inf else f"{months_to_payback:.1f}")


# =========================================================
# ✅ WHAT‑IF SIMULATOR
# =========================================================
st.markdown("## 🔮 What‑If Scenario Simulator")

with st.expander("Open Scenario Simulator"):
    colA, colB = st.columns(2)

    with colA:
        sim_rev = st.number_input("Projected Monthly Revenue (₹)", value=float(avg_rev or 50000))
        sim_growth = st.slider("Growth % per Year", 0.0, 20.0, 6.0)

    with colB:
        sim_exp = st.number_input("Projected Monthly Expenses (₹)", value=float(avg_exp or 20000))
        sim_alloc = st.slider("Payback Allocation %", 0.1, 1.0, allocation_pct)

    months = st.slider("Projection Horizon (Months)", 6, 60, 36)

    surplus = sim_rev - sim_exp
    monthly_payback_budget = surplus * sim_alloc

    if monthly_payback_budget > 0:
        sim_months_to_break_even = remaining / monthly_payback_budget
    else:
        sim_months_to_break_even = np.inf

    linear = []
    optimistic = []
    opt_surplus = surplus

    for m in range(months):
        linear.append(monthly_payback_budget)
        optimistic.append(opt_surplus * sim_alloc)
        opt_surplus *= (1 + sim_growth / 1200.0)

    df_proj = pd.DataFrame({
        "Linear Projection": linear,
        "Optimistic Projection": optimistic
    })

    st.metric("Simulated Months to BE", "∞" if sim_months_to_break_even == np.inf else f"{sim_months_to_break_even:.1f}")
    st.line_chart(df_proj)


# =========================================================
# ✅ REVENUE TREND
# =========================================================
st.markdown("## 📊 Revenue Trend")

if not rev_df.empty:
    rev_df["month"] = rev_df["revenue_date"].dt.to_period("M")
    rev_monthly = rev_df.groupby("month")["amount"].sum().to_frame()
    rev_monthly.index = rev_monthly.index.to_timestamp()
    st.line_chart(rev_monthly)
else:
    st.info("No revenue data available.")


# =========================================================
# ✅ EXPENSE TREND
# =========================================================
st.markdown("## 💸 Expense Trend")

if not exp_df.empty:
    exp_df["month"] = exp_df["expense_date"].dt.to_period("M")
    exp_monthly = exp_df.groupby("month")["amount"].sum().to_frame()
    exp_monthly.index = exp_monthly.index.to_timestamp()
    st.line_chart(exp_monthly)
else:
    st.info("No expense data available.")


# =========================================================
# ✅ REVENUE vs PAYBACK
