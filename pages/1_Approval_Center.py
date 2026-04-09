import streamlit as st
from db import supabase
from auth import require_role, set_user_role, get_user_role
from constants import ROLE_SUPERUSER, ROLE_EDITOR, ROLE_VIEWER

# =========================================================
# ✅ ACCESS RESTRICTION: SuperUser ONLY
# =========================================================
require_role([ROLE_SUPERUSER])

st.title("✅ Approval Center")

st.write("Manage account approvals and assign roles to users.")


# =========================================================
# ✅ HELPERS
# =========================================================

def fetch_pending_users():
    return (
        supabase.table("users")
        .select("user_id, email, full_name, created_at, status")
        .eq("status", "Pending")  # ✅ pending in USERS table
        .execute()
        .data
    ) or []


def fetch_active_users():
    return (
        supabase.table("users")
        .select("user_id, email, full_name, created_at, status")
        .eq("status", "Active")
        .order("created_at")
        .execute()
        .data
    ) or []


def fetch_roles():
    return (
        supabase.table("roles")
        .select("role_id, role_name")
        .order("role_id")
        .execute()
        .data
    ) or []


# =========================================================
# ✅ SECTION A — PENDING USERS APPROVAL
# =========================================================

pending_users = fetch_pending_users()
roles = fetch_roles()

role_names = [r["role_name"] for r in roles]
role_name_to_id = {r["role_name"]: r["role_id"] for r in roles}

st.subheader("⏳ Pending Account Approvals")

if not pending_users:
    st.success("✅ No pending users. All accounts approved.")
else:
    for user in pending_users:
        user_id = user["user_id"]
        full_name = user["full_name"]
        email = user["email"]
        created = user["created_at"]

        with st.container(border=True):

            c1, c2 = st.columns([0.45, 0.55])

            with c1:
                st.markdown(f"""
                **Name:** {full_name}  
                **Email:** {email}  
                **Created:** {created}  
                **Status:** `Pending`
                """)

            with c2:
                selected_role = st.selectbox(
                    f"Assign Initial Role for {full_name}",
                    role_names,
                    key=f"pending_role_select_{user_id}"
                )

                if st.button(f"✅ Approve {full_name}", key=f"approve_{user_id}", use_container_width=True):
                    try:
                        # ✅ set_user_role also activates the user
                        set_user_role(user_id, selected_role)

                        st.success(f"✅ {full_name} approved! Assigned role: {selected_role}")
                        st.rerun()

                    except Exception as e:
                        st.error(f"❌ Error approving user: {e}")


# =========================================================
# ✅ SECTION B — ACTIVE USERS (ROLE MANAGEMENT)
# =========================================================
st.subheader("👥 Active Users — Role Management")

active_users = fetch_active_users()

if not active_users:
    st.info("No active users found.")
else:
    for user in active_users:
        user_id = user["user_id"]
        full_name = user["full_name"]
        email = user["email"]
        created = user["created_at"]

        # ✅ Do not allow self-role-edit by SuperUser
        if user_id == st.session_state.get("user_id"):
            continue

        current_role = get_user_role(user_id) or "None"

        with st.container(border=True):
            col1, col2 = st.columns([0.45, 0.55])

            with col1:
                st.markdown(f"""
                **Name:** {full_name}  
                **Email:** {email}  
                **Created:** {created}  
                **Account Status:** `Active`  
                **Current Role:** `{current_role}`
                """)

            with col2:
                new_role = st.selectbox(
                    f"Change Role for {full_name}",
                    role_names,
                    index=role_names.index(current_role) if current_role in role_names else 0,
                    key=f"active_role_{user_id}"
                )

                if st.button(f"✅ Update Role for {full_name}", key=f"update_role_{user_id}", use_container_width=True):
                    try:
                        set_user_role(user_id, new_role)
                        st.success(f"✅ Role updated: {full_name} → {new_role}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error updating role: {e}")
