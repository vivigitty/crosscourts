import streamlit as st
import pandas as pd
from datetime import date

from db import supabase
from sanitization import sanitize


# =========================================================
# ✅ MONTH-BASED EXPENSE ENTRY (UPSERT PER ROW)
# =========================================================
def expense_page(project_id: int, project_name: str):

    st.subheader(f"💸 Expense Entry — {project_name}")

    # -----------------------------------------------------
    # 1️⃣ Select Month
    # -----------------------------------------------------
    selected_month = st.date_input(
        "Select Expense Month",
        value=date.today().replace(day=1),
        format="YYYY-MM-DD"
    )

    month_start = selected_month.replace(day=1)
    st.caption(f"Editing expenses for **{month_start.strftime('%B %Y')}**")

    # -----------------------------------------------------
    # 2️⃣ Fetch existing expenses for the month
    # -----------------------------------------------------
    rows = (
        supabase.table("project_expenses")
        .select("*")
        .eq("project_id", project_id)
        .eq("expense_date", month_start.isoformat())   # 👈 month anchor
        .order("expense_id")
        .execute()
        .data
    )

    # -----------------------------------------------------
    # 3️⃣ Build editable table
    # -----------------------------------------------------
    def blank_row():
        return {
            "expense_id": None,
            "expense_category": "",
            "description": "",
            "amount": 0.0,
        }

    if not rows:
        df = pd.DataFrame([blank_row()])
    else:
        df = pd.DataFrame(rows)
        df = df[[
            "expense_id",
            "expense_category",
            "description",
            "amount"
        ]]

    # Always add an empty row for new entry
    df.loc[len(df)] = blank_row()

    editor_df = df.drop(columns=["expense_id"])

    # -----------------------------------------------------
    # 4️⃣ Editable UI
    # -----------------------------------------------------
    edited = st.data_editor(
        editor_df,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "expense_category": st.column_config.TextColumn(
                "Expense Category", required=True
            ),
            "amount": st.column_config.NumberColumn(
                "Amount (₹)", min_value=0.0
            ),
        },
        key=f"expense_editor_{project_id}_{month_start}"
    )

    edited["expense_id"] = df["expense_id"]

    # -----------------------------------------------------
    # 5️⃣ Save Logic (UPSERT)
    # -----------------------------------------------------
    if st.button("💾 Save Expenses"):
        try:
            for _, row in edited.iterrows():

                # Skip empty rows
                if row["expense_category"] == "" and float(row["amount"] or 0) == 0:
                    continue

                payload = {
                    "project_id": project_id,
                    "expense_date": month_start.isoformat(),  # month anchor
                    "expense_category": sanitize(row["expense_category"]),
                    "description": sanitize(row["description"]),
                    "amount": float(row["amount"] or 0),
                }

                # UPDATE existing row
                if row["expense_id"] not in [None, "", 0]:
                    supabase.table("project_expenses") \
                        .update(payload) \
                        .eq("expense_id", int(row["expense_id"])) \
                        .execute()

                # INSERT new row
                else:
                    supabase.table("project_expenses") \
                        .insert(payload) \
                        .execute()

            st.success(f"✅ Expenses saved for {month_start.strftime('%B %Y')}")
            st.rerun()

        except Exception as e:
            st.error(f"❌ Failed to save expenses: {e}")

    # -----------------------------------------------------
    # 6️⃣ Monthly Total
    # -----------------------------------------------------
    total = sum([
        float(r["amount"])
        for r in rows
    ]) if rows else sum(edited["amount"])

    st.markdown(f"### 🧮 Total Expenses for Month: **₹{total:,.2f}**")
