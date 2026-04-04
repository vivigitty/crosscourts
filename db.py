# =========================================================
# db.py
# Centralized Supabase database access layer
# =========================================================

import os
import streamlit as st
from supabase import create_client
from dotenv import load_dotenv

from constants import (
    STATUS_PENDING,
    STATUS_ACTIVE,
    STATUS_INACTIVE,
    ROLE_SUPERUSER,
    ROLE_EDITOR,
    ROLE_VIEWER,
    ROLE_PENDING,
)
from sanitization import sanitize, sanitize_payload


# =========================================================
# ✅ Dual environment loader (local .env + Streamlit Cloud)
# =========================================================

def load_supabase_keys():
    """Load Supabase keys from Streamlit Cloud or local .env."""
    # Streamlit Cloud
    try:
        return st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"]
    except Exception:
        pass

    # Local dev
    load_dotenv()
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")

    if not url or not key:
        raise ValueError("❌ Missing SUPABASE_URL or SUPABASE_KEY")

    return url, key


SUPABASE_URL, SUPABASE_KEY = load_supabase_keys()
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


# =========================================================
# ✅ USER MANAGEMENT (Signup, Fetch, Status updates)
# =========================================================

def create_user(email: str, full_name: str, password_hash: str):
    """Insert a new user into the database with Pending status."""
    payload = sanitize_payload({
        "email": email,
        "full_name": full_name,
        "password_hash": password_hash,
        "status": STATUS_PENDING,
    })
    return supabase.table("users").insert(payload).execute()


def get_user_by_email(email: str):
    email = sanitize(email)
    return supabase.table("users") \
        .select("*") \
        .eq("email", email) \
        .execute() \
        .data


def get_user_by_id(user_id: int):
    return supabase.table("users") \
        .select("*") \
        .eq("user_id", user_id) \
        .execute() \
        .data


def get_pending_users():
    """Return users awaiting approval."""
    return supabase.table("users") \
        .select("*") \
        .eq("status", STATUS_PENDING) \
        .execute() \
        .data


def set_user_status(user_id: int, status: str):
    """Activate / Deactivate / Pending a user."""
    return supabase.table("users") \
        .update({"status": sanitize(status)}) \
        .eq("user_id", user_id) \
        .execute()


# =========================================================
# ✅ ROLE ASSIGNMENT HELPERS
# =========================================================

def get_user_role(user_id: int):
    """Return the user's role name (SuperUser / Editor / Viewer / Pending)."""
    data = (
        supabase.table("user_roles")
        .select("roles(role_name)")
        .eq("user_id", user_id)
        .execute()
        .data
    )
    if data and data[0]["roles"]:
        return data[0]["roles"]["role_name"]
    return ROLE_PENDING


def set_user_role(user_id: int, role_name: str):
    """Assign or change a user's role."""
    # Get role_id
    role_row = supabase.table("roles") \
        .select("role_id") \
        .eq("role_name", role_name) \
        .execute() \
        .data

    if not role_row:
        raise ValueError(f"Role not found: {role_name}")

    role_id = role_row[0]["role_id"]

    # Upsert ensures update or insert
    return supabase.table("user_roles") \
        .upsert({"user_id": user_id, "role_id": role_id}) \
        .execute()


# =========================================================
# ✅ REVENUE DB HELPERS  (Filled later when pages are added)
# =========================================================

def insert_revenue(project_id, date, revenue_type_id, time_slot, amount):
    payload = sanitize_payload({
        "project_id": project_id,
        "revenue_date": date,
        "revenue_type_id": revenue_type_id,
        "time_slot": time_slot,
        "amount": amount
    })
    return supabase.table("project_revenue").insert(payload).execute()


def fetch_revenue(project_id=None):
    q = supabase.table("project_revenue").select("*")
    if project_id:
        q = q.eq("project_id", project_id)
    return q.execute().data


# =========================================================
# ✅ EXPENSE DB HELPERS
# =========================================================

def insert_expense(project_id, date, category, description, amount):
    payload = sanitize_payload({
        "project_id": project_id,
        "expense_date": date,
        "expense_category": category,
        "description": description,
        "amount": amount
    })
    return supabase.table("project_expenses").insert(payload).execute()


def fetch_expenses(project_id=None):
    q = supabase.table("project_expenses").select("*")
    if project_id:
        q = q.eq("project_id", project_id)
    return q.execute().data


# =========================================================
# ✅ SHAREHOLDER CONTRIBUTIONS
# =========================================================

def insert_shareholder_contribution(project_id, shareholder_id, date, amount):
    payload = sanitize_payload({
        "project_id": project_id,
        "shareholder_id": shareholder_id,
        "contribution_date": date,
        "amount": amount
    })
    return supabase.table("shareholder_contributions").insert(payload).execute()


def fetch_shareholder_contributions(project_id=None):
    q = supabase.table("shareholder_contributions").select("*")
    if project_id:
        q = q.eq("project_id", project_id)
    return q.execute().data
