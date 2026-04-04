# =========================================================
# revenue_structures.py
# Defines revenue entry schemas (structure_1, structure_2…)
# =========================================================

# ✅ DEFAULT STRUCTURE (Structure 1)
structure_1 = {
    "columns": [
        {"name": "time_slot", "label": "Time Slot", "type": "text"},
        {"name": "name", "label": "Name", "type": "text"},
        {
            "name": "booking_type",
            "label": "Booking Type",
            "type": "dropdown",
            "source": "revenue_type"
        },
        {"name": "paid_app", "label": "Paid in App", "type": "number"},
        {"name": "paid_gpay", "label": "Paid in GPay", "type": "number"},
        {"name": "paid_cash", "label": "Paid in Cash", "type": "number"},
        {"name": "remarks", "label": "Remarks", "type": "text"},
    ],
    "compute_amount": lambda row: (
        float(row.get("paid_app") or 0) +
        float(row.get("paid_gpay") or 0) +
        float(row.get("paid_cash") or 0)
    )
}

# ✅ FUTURE STRUCTURE (Structure 2)
# Example: Different projects might need different fields
structure_2 = {
    "columns": [
        {"name": "time_slot", "label": "Time Slot", "type": "text"},
        {
            "name": "coach_name",
            "label": "Coach",
            "type": "dropdown",
            "source": "coaches"      # future usage
        },
        {
            "name": "batch",
            "label": "Batch",
            "type": "dropdown",
            "source": "batches"      # future usage
        },
        {"name": "paid_app", "label": "Paid in App", "type": "number"},
        {"name": "paid_cash", "label": "Paid in Cash", "type": "number"},
        {"name": "remarks", "label": "Remarks", "type": "text"},
    ],
    "compute_amount": lambda row: (
        float(row.get("paid_app") or 0) +
        float(row.get("paid_cash") or 0)
    )
}

# ✅ STRUCTURE REGISTRY
REVENUE_STRUCTURES = {
    "structure_1": structure_1,
    "structure_2": structure_2
}
