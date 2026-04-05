import streamlit as st
import pandas as pd
from datetime import date

from roles import require_role
from constants import ROLE_SUPERUSER
from db import supabase
from sanitization import sanitize


# =========================================================
# ✅ SUPERUSER-ONLY ACCESS
# =========================================================
require_role([ROLE_SUPERUSER])

st.title("💼 Shareholder Payback Tracker")


# =========================================================
# ✅ DATE NORMALIZATION (Handles all types)
# =========================================================
def normalize_date(d):
    """
    Accepts: date, datetime, pandas Timestamp, numpy.datetime64, str
    Returns: 'YYYY-MM-DD' or None
    """
    if d is None or d == "":
        return None

    if isinstance(d, date):
        return d.strftime("%Y-%m-%d")

    try:
        return pd.to_datetime(d).strftime("%Y-%m-%d")
    except:
        return None


# =========================================================
# ✅ KPI LOADER (using ACTUAL shareholder_contributions table)
# =========================================================
def load_shareholder_kpis(project_id):

    # ✅ Total Contribution
    contrib_rows = (
        supabase.table("shareholder_contributions")
        .select("amount")
        .eq("project_id", project_id)
        .execute()
        .data
    )
    total_contribution = sum([float(r["amount"] or 0) for r in contrib_rows])

    # ✅ Total Payback
    pay_rows = (
        supabase.table("shareholder_payments")
        .select("amount_paid")
        .eq("project_id", project_id)
        .execute()
        .data
    )
    total_payback = sum([float(r["amount_paid"] or 0) for r in pay_rows])

    # ✅ Net retained earnings = contribution - payback
    net_retained = total_contribution - total_payback

    return total_contribution, total_payback, net_retained


# =========================================================
# ✅ LOAD PROJECTS
# =========================================================
projects = supabase.table("projects").select("*").execute().data
project_map = {p["project_name"]: p["project_id"] for p in projects}

selected_project = st.selectbox("Select Project", list(project_map.keys()))
project_id = project_map[selected_project]


# =========================================================
# ✅ SHOW SHAREHOLDER KPIs
# =========================================================
total_contribution, total_payback, net_retained = load_shareholder_kpis(project_id)

k1, k2, k3 = st.columns(3)
k1.metric("Total Contribution", f"₹{total_contribution:,.0f}")
k2.metric("Total Payback", f"₹{total_payback:,.0f}")
k3.metric("Net Retained Earnings", f"₹{net_retained:,.0f}")

st.subheader(f"📘 Payback Entries for {selected_project}")


# =========================================================
# ✅ LOAD SHAREHOLDERS FOR SELECTED PROJECT
# =========================================================
ps = (
    supabase.table("project_shareholders")
    .select("shareholders (shareholder_id, shareholder_name), shareholder_id")
    .eq("project_id", project_id)
    .execute()
    .data
)

project_shareholders_by_id = {
    row["shareholder_id"]: row["shareholders"]["shareholder_name"]
    for row in ps
}

shareholder_id_by_name = {v: k for k, v in project_shareholders_by_id.items()}
shareholder_names = list(shareholder_id_by_name.keys())  # Dropdown options


# =========================================================
# ✅ LOAD PAYBACK ENTRIES
# =========================================================
rows = (
    supabase.table("shareholder_payments")
    .select("*")
    .eq("project_id", project_id)
    .order("payment_date")
    .execute()
    .data
)


# =========================================================
# ✅ BUILD EDITOR TABLE
# =========================================================
def blank_row():
    return {
        "payment_id": None,
        "payment_date": None,   # Calendar widget
        "shareholder": shareholder_names.copy(),  # Default = ALL
        "amount_paid": 0.0,
        "remarks": ""
    }

if not rows:
    df = pd.DataFrame([blank_row()])
else:
    df = pd.DataFrame(rows)

    df["shareholder"] = df["shareholder_id"].apply(
        lambda sid: [project_shareholders_by_id.get(sid, "")]
    )
    df["payment_date"] = pd.to_datetime(df["payment_date"], errors="coerce").dt.date

    df = df[[
        "payment_id",
        "payment_date",
        "shareholder",
        "amount_paid",
        "remarks"
    ]]

df.loc[len(df)] = blank_row()   # Append new row

editor_df = df.drop(columns=["payment_id"])


# =========================================================
# ✅ EDITOR UI (DateColumn + ListColumn)
# =========================================================
st.subheader("✏️ Add / Edit Payback Entries")

edited = st.data_editor(
    editor_df,
    num_rows="dynamic",
    use_container_width=True,
    column_config={
        "payment_date": st.column_config.DateColumn(
            "Payment Date",
            format="YYYY-MM-DD",
            required=True,
        ),
        "shareholder": st.column_config.ListColumn(
            "Shareholders",
            help="Click to remove shareholders who are NOT receiving payment."
        ),
        "amount_paid": st.column_config.NumberColumn(
            "Amount Paid (₹)",
            min_value=0.0
        )
    },
    key="payback_editor"
)

edited["payment_id"] = df["payment_id"]


# =========================================================
# ✅ SAVE (multi-row expansion)
# =========================================================
if st.button("💾 Save Changes"):
    try:
        for _, row in edited.iterrows():

            selected_names = row["shareholder"]
            if not selected_names:
                continue

            payment_date_clean = normalize_date(row["payment_date"])
            if not payment_date_clean:
                st.error(f"❌ Invalid date: {row['payment_date']}")
                st.stop()

            selected_ids = [
                shareholder_id_by_name[n]
                for n in selected_names if n in shareholder_id_by_name
            ]

            # Case 1 — Update existing single-shareholder row
            if row["payment_id"] not in [None, "", 0] and len(selected_ids) == 1:

                supabase.table("shareholder_payments").update({
                    "project_id": project_id,
                    "payment_date": payment_date_clean,
                    "shareholder_id": selected_ids[0],
                    "amount_paid": float(row["amount_paid"]),
                    "remarks": sanitize(row["remarks"])
                }).eq("payment_id", int(row["payment_id"])).execute()

            else:
                # Case 2 — Delete old & insert multiple new rows
                if row["payment_id"] not in [None, "", 0]:
                    supabase.table("shareholder_payments") \
                        .delete() \
                        .eq("payment_id", int(row["payment_id"])) \
                        .execute()

                for sid in selected_ids:
                    supabase.table("shareholder_payments").insert({
                        "project_id": project_id,
                        "payment_date": payment_date_clean,
                        "shareholder_id": sid,
                        "amount_paid": float(row["amount_paid"]),
                        "remarks": sanitize(row["remarks"])
                    }).execute()

        st.success("✅ Payback entries saved successfully!")
        st.rerun()

    except Exception as e:
        st.error(f"❌ Save Error: {e}")


# =========================================================
# ✅ DELETE SECTION
# =========================================================
st.subheader("🗑 Delete Payback Entries")

rows_delete = (
    supabase.table("shareholder_payments")
    .select("*")
    .eq("project_id", project_id)
    .order("payment_date")
    .execute()
    .data
)

if not rows_delete:
    st.info("No payback entries found.")
else:
    delete_df = pd.DataFrame(rows_delete)

    for _, row in delete_df.iterrows():
        rid = row["payment_id"]
        sid = row["shareholder_id"]
        shareholder_name = project_shareholders_by_id.get(sid, "")

        col1, col2 = st.columns([0.1, 0.9])

        with col1:
            if st.button("🗑️", key=f"del_{rid}"):
                supabase.table("shareholder_payments") \
                    .delete() \
                    .eq("payment_id", rid) \
                    .execute()
                st.warning(f"✅ Deleted entry #{rid}")
                st.rerun()

        with col2:
            st.write(
                f"**{row['payment_date']}** | "
                f"{shareholder_name} | "
                f"₹{row['amount_paid']} | "
                f"{row.get('remarks', '')}"
            )
