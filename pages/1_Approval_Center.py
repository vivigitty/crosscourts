import streamlit as st
import pandas as pd

from roles import require_role
from constants import (
    ROLE_SUPERUSER,
    ROLE_EDITOR,
    ROLE_VIEWER,
    STATUS_PENDING,
    STATUS_ACTIVE,
    STATUS_INACTIVE,
)
from db import (
    get_pending_users,
    get_user_by_id,
    set_user_status,
    set_user_role,
    supabase,
)


# =========================================================
# ✅ PAGE PROTECTION
# =========================================================
require_role([ROLE_SUPERUSER])

st.title("✅ User Approval & Role Management")


# =========================================================
# ✅ SECTION 1 — PENDING APPROVAL USERS
# =========================================================
st.subheader("⏳ Pending Approvals")

pending = get_pending_users()

if len(pending) == 0:
    st.info("No pending users.")
else:
    df_pending = pd.DataFrame(pending)

    for _, row in df_pending.iterrows():
        email = row["email"]
        uid = row["user_id"]

        with st.container(border=True):
            st.write(f"**📧 {email}**")
            st.write(f"Full Name: {row['full_name']}")

            colA, colB, colC = st.columns([1,1,2])

            with colA:
                if st.button("✅ Approve", key=f"approve_{uid}"):
                    set_user_status(uid, STATUS_ACTIVE)
                    set_user_role(uid, ROLE_VIEWER)
                    st.success(f"Approved {email}")
                    st.rerun()

            with colB:
                if st.button("❌ Reject", key=f"reject_{uid}"):
                    supabase.table("users").delete().eq("user_id", uid).execute()
                    st.warning(f"Rejected {email}")
                    st.rerun()


# =========================================================
# ✅ SECTION 2 — ACTIVE USERS (Manage Roles / Status)
# =========================================================
st.subheader("👥 Active Users")

active_users = (
    supabase.table("users")
    .select("*")
    .eq("status", STATUS_ACTIVE)
    .execute()
    .data
)

if len(active_users) == 0:
    st.info("No active users.")
else:
    df = pd.DataFrame(active_users)

    for _, row in df.iterrows():
        email = row["email"]
        uid = row["user_id"]

        # Fetch role
        role_data = supabase.table("user_roles") \
            .select("roles(role_name)") \
            .eq("user_id", uid).execute().data

        role_name = role_data[0]["roles"]["role_name"] if role_data else "Viewer"

        with st.container(border=True):
            st.write(f"**📧 {email}**")
            st.write(f"Role: **{role_name}**")

            new_role = st.selectbox(
                "Change Role",
                [ROLE_VIEWER, ROLE_EDITOR, ROLE_SUPERUSER],
                index=["Viewer", "Editor", "SuperUser"].index(role_name),
                key=f"role_select_{uid}",
            )

            col1, col2 = st.columns([1,1])

            with col1:
                if st.button("💾 Update Role", key=f"update_role_{uid}"):
                    set_user_role(uid, new_role)
                    st.success(f"Updated role for {email}")
                    st.rerun()

            with col2:
                if st.button("Deactivate User", key=f"deact_{uid}"):
                    set_user_status(uid, STATUS_INACTIVE)
                    st.warning(f"Deactivated {email}")
                    st.rerun()


# =========================================================
# ✅ SECTION 3 — INACTIVE USERS
# =========================================================
st.subheader("🚫 Inactive Users")

inactive_users = (
    supabase.table("users")
    .select("*")
    .eq("status", STATUS_INACTIVE)
    .execute()
    .data
)

if len(inactive_users) == 0:
    st.info("No inactive users.")
else:
    df = pd.DataFrame(inactive_users)

    for _, row in df.iterrows():
        email = row["email"]
        uid = row["user_id"]

        with st.container(border=True):
            st.write(f"📧 {email}")

            if st.button("✅ Activate", key=f"activate_{uid}"):
                set_user_status(uid, STATUS_ACTIVE)
                set_user_role(uid, ROLE_VIEWER)
                st.success(f"Activated {email}")
                st.rerun()
