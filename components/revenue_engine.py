# =========================================================
# revenue_engine.py
# Reusable Revenue Entry Engine for ALL projects
# Supports multiple revenue structures (structure_1, structure_2...)
# =========================================================

import streamlit as st
import pandas as pd
import calendar

from db import supabase
from sanitization import sanitize
from components.revenue_structures import REVENUE_STRUCTURES


# =========================================================
# ✅ INR FORMATTER
# =========================================================
def format_inr(amount):
    """Format an amount as Indian Rupees with proper comma grouping."""
    try:
        amount = float(amount)
    except:
        return "₹0"

    s = f"{amount:,.2f}"
    whole, frac = s.split(".")
    if len(whole) > 3:
        whole = whole[:-3].replace(",", "") + "," + whole[-3:]
    return f"₹{whole}.{frac}"


# =========================================================
# ✅ KPI METRICS FOR DAY + MONTH
# =========================================================
def render_kpis(project_id, selected_date):
    date_str = str(selected_date)

    # ---------- Daily Total ----------
    day_rows = (
        supabase.table("project_revenue")
        .select("amount")
        .eq("project_id", project_id)
        .eq("revenue_date", date_str)
        .execute()
        .data
    )
    total_day = sum([float(r["amount"] or 0) for r in day_rows])

    # ---------- Monthly Total ----------
    year = selected_date.year
    month = selected_date.month
    last_day = calendar.monthrange(year, month)[1]

    month_rows = (
        supabase.table("project_revenue")
        .select("amount")
        .eq("project_id", project_id)
        .gte("revenue_date", f"{year}-{month:02d}-01")
        .lte("revenue_date", f"{year}-{month:02d}-{last_day:02d}")
        .execute()
        .data
    )
    total_month = sum([float(r["amount"] or 0) for r in month_rows])

    # ---------- Render KPIs ----------
    st.subheader("📊 Key Metrics")
    col1, col2 = st.columns(2)

    with col1:
        st.metric(
            label=f"Total Income for {selected_date.strftime('%d-%b-%Y')}",
            value=format_inr(total_day)
        )

    with col2:
        st.metric(
            label=f"Total Income for {selected_date.strftime('%B %Y')}",
            value=format_inr(total_month)
        )


# =========================================================
# ✅ BUILD A BLANK ROW BASED ON STRUCTURE
# =========================================================
def build_blank_row(structure):
    row = {}
    for col in structure["columns"]:
        if col["type"] == "number":
            row[col["name"]] = 0.0
        else:
            row[col["name"]] = ""
    row["revenue_id"] = None
    return row


# =========================================================
# ✅ INSERT / EDIT TABLE
# =========================================================
def render_entry_table(project_id, selected_date, structure):
    date_str = str(selected_date)

    # ---------- Load existing rows ----------
    db_rows = (
        supabase.table("project_revenue")
        .select("*")
        .eq("project_id", project_id)
        .eq("revenue_date", date_str)
        .order("revenue_id")
        .execute()
        .data
    )

    # ---------- Convert DB → editable DF ----------
    if not db_rows:
        df = pd.DataFrame([build_blank_row(structure)])
    else:
        df = pd.DataFrame(db_rows)

        # Map revenue_type_id → string booking_type
        revenue_type_map = {
            rt["revenue_type_id"]: rt["revenue_type_name"]
            for rt in supabase.table("revenue_type").select("*").execute().data
        }
        df["booking_type"] = df["revenue_type_id"].map(revenue_type_map)

        # Keep only structure columns
        df = df[["revenue_id"] + [c["name"] for c in structure["columns"]]]

        # Normalize missing values
        for col in df.columns:
            df[col] = df[col].fillna(0.0 if df[col].dtype != "object" else "")

    # Always add blank new row
    df.loc[len(df)] = build_blank_row(structure)

    st.subheader("✏️ Add / Edit Revenue Entries")

    # ---------- Editable Grid ----------
    edited_df = st.data_editor(
        df.drop(columns=["revenue_id"]),
        num_rows="dynamic",
        use_container_width=True,
        key="rev_edit_grid"
    )

    # Restore hidden revenue_id
    edited_df["revenue_id"] = df["revenue_id"]

    # ---------- SAVE ----------
    if st.button("💾 Save Changes"):
        try:
            structure_compute = structure["compute_amount"]

            for _, row in edited_df.iterrows():

                # Skip empty
                if row["time_slot"].strip() == "" and row["name"].strip() == "":
                    continue

                # Compute Amount
                amount = structure_compute(row)

                # Booking type → revenue_type_id
                booking_name = str(row["booking_type"]).strip()
                rt = supabase.table("revenue_type") \
                    .select("revenue_type_id") \
                    .eq("revenue_type_name", booking_name) \
                    .execute().data

                if not rt:
                    st.error(f"❌ Invalid Booking Type: {booking_name}")
                    st.stop()

                revenue_type_id = rt[0]["revenue_type_id"]

                # Build payload
                payload = {
                    "project_id": project_id,
                    "revenue_date": date_str,
                    "time_slot": sanitize(row["time_slot"]),
                    "name": sanitize(row["name"]),
                    "revenue_type_id": revenue_type_id,
                    "remarks": sanitize(row["remarks"]),
                    "amount": float(amount)
                }

                # Add numeric fields dynamically
                for col in structure["columns"]:
                    if col["type"] == "number":
                        payload[col["name"]] = float(row[col["name"]] or 0)

                # ✅ UPSERT avoids duplicates (if UNIQUE constraint present)
                supabase.table("project_revenue").upsert(payload).execute()

            st.success("✅ Revenue saved!")
            st.rerun()

        except Exception as e:
            st.error(f"❌ Save Error: {e}")


# =========================================================
# ✅ DELETE TABLE (Option B)
# =========================================================
def render_delete_table(project_id, selected_date, structure):
    date_str = str(selected_date)

    rows = (
        supabase.table("project_revenue")
        .select("*")
        .eq("project_id", project_id)
        .eq("revenue_date", date_str)
        .order("time_slot")
        .execute()
        .data
    )

    st.subheader("🗑 Delete Entries")

    if not rows:
        st.info("No entries for this date.")
        return

    df = pd.DataFrame(rows)

    # Map revenue_type_id → booking_type
    rev_type_map = {
        rt["revenue_type_id"]: rt["revenue_type_name"]
        for rt in supabase.table("revenue_type").select("*").execute().data
    }
    df["booking_type"] = df["revenue_type_id"].map(rev_type_map)

    # ---------- Render as a deletion table ----------
    for _, row in df.iterrows():
        rid = row["revenue_id"]

        col1, col2 = st.columns([0.1, 0.9])

        with col1:
            if st.button("🗑️", key=f"delete_{rid}"):
                supabase.table("project_revenue") \
                    .delete() \
                    .eq("revenue_id", rid) \
                    .execute()
                st.warning(f"✅ Deleted entry #{rid}")
                st.rerun()

        with col2:
            st.write(
                f"**{row['time_slot']}** | "
                f"{row['name']} | "
                f"{row['booking_type']} | "
                f"App ₹{row['paid_app']} | "
                f"GPay ₹{row['paid_gpay']} | "
                f"Cash ₹{row['paid_cash']} | "
                f"{row['remarks']}"
            )


# =========================================================
# ✅ EXCEL UPLOAD
# =========================================================
def render_excel_upload(project_id, structure):
    st.subheader("📤 Bulk Upload (Excel)")

    file = st.file_uploader("Upload Excel (.xlsx)", type=["xlsx"])

    if file and st.button("Process Excel"):
        try:
            df = pd.read_excel(file)

            # Clean strings
            for col in df.select_dtypes(include=["object"]).columns:
                df[col] = df[col].astype(str).str.strip()

            # Date fix (DD-MM-YYYY → YYYY-MM-DD)
            df["Date"] = pd.to_datetime(df["Date"], dayfirst=True, errors="coerce") \
                .dt.strftime("%Y-%m-%d")

            if df["Date"].isnull().any():
                st.error("❌ Invalid dates found in Excel.")
                st.stop()

            compute_amount = structure["compute_amount"]

            for _, row in df.iterrows():

                amount = compute_amount({
                    "paid_app": row.get("Paid in App"),
                    "paid_gpay": row.get("Paid in Gpay"),
                    "paid_cash": row.get("Paid in Cash"),
                })

                # Booking type → revenue_type_id
                rt = supabase.table("revenue_type") \
                    .select("revenue_type_id") \
                    .eq("revenue_type_name", row["Booking_Type"]) \
                    .execute().data

                if not rt:
                    st.error(f"Invalid Booking Type: {row['Booking_Type']}")
                    st.stop()

                revenue_type_id = rt[0]["revenue_type_id"]

                payload = {
                    "project_id": project_id,
                    "revenue_date": row["Date"],
                    "time_slot": row["Time Slot"],
                    "name": sanitize(row["Name"]),
                    "revenue_type_id": revenue_type_id,
                    "remarks": sanitize(row.get("Remarks") or ""),
                    "amount": float(amount)
                }

                # Add numeric fields dynamically
                for c in structure["columns"]:
                    if c["type"] == "number":
                        payload[c["name"]] = float(row.get(c["label"], 0))

                supabase.table("project_revenue").upsert(payload).execute()

            st.success("✅ Excel upload completed!")
            st.rerun()

        except Exception as e:
            st.error(f"❌ Excel Processing Error: {e}")


# =========================================================
# ✅ MAIN PUBLIC FUNCTION – This is what each project page calls
# =========================================================
def revenue_page(project_id: int, project_name: str, structure_key: str = "structure_1"):
    structure = REVENUE_STRUCTURES.get(structure_key)

    st.title(f"💰 Revenue Entry — {project_name}")

    selected_date = st.date_input("Select Date")

    if selected_date:
        # KPI Metrics
        render_kpis(project_id, selected_date)

        # Insert/Edit Table
        render_entry_table(project_id, selected_date, structure)

        # Delete Table
        render_delete_table(project_id, selected_date, structure)

        # Excel Upload
        render_excel_upload(project_id, structure)
