# =========================================================
# roles.py
# Role-based access control utilities
# =========================================================

import streamlit as st
from constants import (
    ROLE_SUPERUSER,
    ROLE_EDITOR,
    ROLE_VIEWER,
    ROLE_PENDING,
    STATUS_ACTIVE,
    STATUS_PENDING,
    STATUS_INACTIVE,
)
from db import get_user_role, get_user_by_id


# =========================================================
# ✅ Fetch user status (Active / Pending / Inactive)
# =========================================================

def get_user_status(user_id: int):
    user = get_user_by_id(user_id)
    if not user:
        return None
    return user[0]["status"]


# =========================================================
# ✅ Simple role checking helpers
# =========================================================

def has_role(user_id: int, allowed_roles: list):
    role = get_user_role(user_id)
    return role in allowed_roles


def is_superuser(user_id: int):
    return get_user_role(user_id) == ROLE_SUPERUSER


def is_editor(user_id: int):
    return get_user_role(user_id) == ROLE_EDITOR


def is_viewer(user_id: int):
    return get_user_role(user_id) == ROLE_VIEWER


# =========================================================
# ✅ Page Protection Decorator
# =========================================================

def require_role(allowed_roles: list):
    """
    Enforce role-level access inside pages.
    Usage:
        from roles import require_role
        require_role([ROLE_SUPERUSER])
    """

    if "user" not in st.session_state:
        st.error("Please log in to access this page.")
        st.stop()

    user = st.session_state["user"]
    user_id = user["user_id"]

    # Check status
    status = get_user_status(user_id)
    if status == STATUS_PENDING:
        st.error("Your account is awaiting approval by the administrator.")
        st.stop()
    if status == STATUS_INACTIVE:
        st.error("Your account is inactive. Contact admin.")
        st.stop()

    # Check role
    if not has_role(user_id, allowed_roles):
        st.error("⛔ You do not have permission to access this page.")
        st.stop()
