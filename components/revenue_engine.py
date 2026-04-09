import streamlit as st
import pandas as pd
import calendar
from db import supabase
from datetime import date
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
# ✅ Fetch booking_type values from revenue_type table
# =========================================================
def get_booking_types():
    resp = (
        supabase.table("revenue_type")
        .select("revenue_type_id, revenue_type_name")
        .order("revenue_type_name")
        .execute()
    )
    data = resp.data or []
    id_to_name = {d["revenue_type_id"]: d["revenue_type_name"] for d in data}
    name_to_id = {v: k for k, v in id_to_name.items()}
    return id_to_name, name_to_id


# =========================================================
# ✅ Build blank row based on structure
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
# ✅ DAILY ENTRY TABLE (UNCHANGED except booking_type fixes)
# =========================================================
def render_entry_table(project_id, selected_date, structure):

    # Load booking types
    id_to_name, name_to_id = get_booking_types()
    booking_type_options = list(name_to_id.keys())

    # Fetch existing rows for the selected date
    rows = (
        supabase.table("project_revenue")
        .select("*")
        .eq("project_id", project_id)
        .eq("revenue_date", str(selected_date))
        .order("revenue_id")
        .execute()
        .data
    )

    # Build DataFrame
    if not rows:
        df = pd.DataFrame([build_blank_row(structure)])
    else:
        df = pd.DataFrame(rows)

        # ✅ Map revenue_type_id → booking_type name
        if "revenue_type_id" in df.columns:
            df["booking_type"] = df["revenue_type_id"].apply(
                lambda v: id_to_name.get(v, "")
            )

        ordered_cols = ["revenue_id"] + [col["name"] for col in structure["columns"]]
        df = df[ordered_cols]

    

    # Build column configs
    col_config = {}

    for col in structure["columns"]:
        if col["type"] == "dropdown" and col["source"] == "revenue_type":
            col_config[col["name"]] = st.column_config.SelectboxColumn(
                col["label"],
                options=booking_type_options,
                required=True,
            )
        elif col["type"] == "number":
            col_config[col["name"]] = st.column_config.NumberColumn(
                col["label"], min_value=0.0
            )
        else:
            col_config[col["name"]] = st.column_config.TextColumn(col["label"])

    # Editable grid
    edited_df = st.data_editor(
        df.drop(columns=["revenue_id"]),
        num_rows="dynamic",
        use_container_width=True,
        column_config=col_config,
        key="rev_edit_grid",
    )

    edited_df["revenue_id"] = df["revenue_id"]

    # =========================================================
    # ✅ SAVE — UPSERT
    # =========================================================
    if st.button("💾 Save Revenue", type="primary"):

        for idx, row in edited_df.iterrows():

            # Skip empty rows
            if all(
                (row[col["name"]] in ("", None) or str(row[col["name"]]).strip() == "")
                for col in structure["columns"]
                if col["name"] != "booking_type"
            ):
                continue

            # ✅ Convert booking_type (string) → revenue_type_id
            booking_type_name = row["booking_type"]
            revenue_type_id = name_to_id.get(booking_type_name)

            # ✅ Compute amount
            paid_app = float(row.get("paid_app") or 0)
            paid_gpay = float(row.get("paid_gpay") or 0)
            paid_cash = float(row.get("paid_cash") or 0)
            computed_amount = paid_app + paid_gpay + paid_cash

            payload = {
                "project_id": project_id,
                "revenue_date": str(selected_date),
                "revenue_type_id": revenue_type_id,
                "amount": computed_amount,
            }

            # ✅ Add other fields EXCEPT booking_type
            for col in structure["columns"]:
                name = col["name"]

                if name == "booking_type":
                    continue  # ✅ DO NOT insert booking_type into DB

                if col["type"] == "number":
                    payload[name] = float(row[name] or 0)
                else:
                    payload[name] = sanitize(row[name])

            # ✅ UPSERT logic
            if row["revenue_id"]:
                supabase.table("project_revenue") \
                    .update(payload) \
                    .eq("revenue_id", int(row["revenue_id"])) \
                    .execute()
            else:
                supabase.table("project_revenue") \
                    .insert(payload) \
                    .execute()

        st.success("✅ Revenue saved successfully!")
        st.rerun()
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
# ✅ Safe float conversion (prevents NaN/Inf/None errors)
# =========================================================
def safe_float(val):
    try:
        f = float(val)
        if f != f:     # NaN
            return 0.0
        if f in (float("inf"), float("-inf")):
            return 0.0
        return f
    except:
        return 0.0


# =========================================================
# ✅ EXCEL UPLOAD (FINAL VERSION — DO NOT MODIFY)
# =========================================================
def render_excel_upload(project_id, structure):
    st.subheader("📤 Bulk Upload (Excel)")

    file = st.file_uploader("Upload Excel (.xlsx)", type=["xlsx"])

    if file and st.button("Process Excel"):
        try:
            df = pd.read_excel(file)

            # -------------------------------------------------
            # ✅ Clean text columns
            # -------------------------------------------------
            for col in df.select_dtypes(include=["object"]).columns:
                df[col] = df[col].astype(str).str.strip()

            # -------------------------------------------------
            # ✅ DATE Handling (DD-MM-YYYY → YYYY-MM-DD)
            # -------------------------------------------------
            if "Date" not in df.columns:
                st.error("❌ Excel is missing required column: Date")
                return

            df["Date"] = pd.to_datetime(
                df["Date"],
                errors="coerce",
                dayfirst=True
            ).dt.strftime("%Y-%m-%d")

            if df["Date"].isnull().any():
                st.error("❌ One or more rows have invalid dates. Please check Excel.")
                return

            # -------------------------------------------------
            # ✅ Fetch revenue type map
            # -------------------------------------------------
            revtypes = (
                supabase.table("revenue_type")
                .select("revenue_type_id, revenue_type_name")
                .execute()
                .data
            )

            revenue_type_map = {
                r["revenue_type_name"]: r["revenue_type_id"] for r in revtypes
            }

            # -------------------------------------------------
            # ✅ Structure-based amount calculator
            # -------------------------------------------------
            compute_amount = structure["compute_amount"]

            # -------------------------------------------------
            # ✅ REQUIRED Excel columns (match structure_1 labels)
            # -------------------------------------------------
            required_cols = [
                "Date",
                "Time Slot",
                "Name",
                "Booking_Type",
                "Paid in App",
                "Paid in Gpay",
                "Paid in Cash",
                "Remarks",
            ]

            missing = [c for c in required_cols if c not in df.columns]
            if missing:
                st.error(f"❌ Missing columns in Excel: {missing}")
                return

            # -------------------------------------------------
            # ✅ Process each row from the Excel file
            # -------------------------------------------------
            for _, row in df.iterrows():

                # --- Validate Booking_Type ---
                booking_name = row.get("Booking_Type")
                if booking_name not in revenue_type_map:
                    st.error(f"❌ Invalid Booking_Type: {booking_name}")
                    return

                revenue_type_id = revenue_type_map[booking_name]

                # --- Compute Amount (safe) ---
                amount = compute_amount({
                    "paid_app": safe_float(row.get("Paid in App")),
                    "paid_gpay": safe_float(row.get("Paid in Gpay")),
                    "paid_cash": safe_float(row.get("Paid in Cash")),
                })

                # --- Base payload ---
                payload = {
                    "project_id": project_id,
                    "revenue_date": row["Date"],
                    "revenue_type_id": revenue_type_id,
                    "amount": float(amount),
                }

                # -------------------------------------------------
                # ✅ Populate structure-driven fields dynamically
                # -------------------------------------------------
                for col in structure["columns"]:
                    field_name = col["name"]
                    excel_label = col["label"]

                    # Skip booking_type (mapped above)
                    if field_name == "booking_type":
                        continue

                    value = row.get(excel_label)

                    if col["type"] == "number":
                        payload[field_name] = safe_float(value)
                    else:
                        payload[field_name] = sanitize(value)

                # -------------------------------------------------
                # ✅ Insert row into DB
                # (Upsert removed to avoid collision on duplicate time slot)
                # -------------------------------------------------
                supabase.table("project_revenue").insert(payload).execute()

            st.success("✅ Excel upload completed successfully!")
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
