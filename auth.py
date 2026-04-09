# =========================================================
# auth.py  — FINAL CLEAN VERSION
# =========================================================

import streamlit as st
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from db import supabase
from sanitization import sanitize
from email_utils import send_reset_email
from constants import (
    ROLE_SUPERUSER,
    ROLE_EDITOR,
    ROLE_VIEWER,
    ROLE_PENDING
)

argon = PasswordHasher()


# =========================================================
# ✅ INTERNAL SESSION HELPERS
# =========================================================

def _set_session(user, role_name: str):
    """Store authenticated session info."""
    st.session_state["user"] = user
    st.session_state["user_id"] = user["user_id"]
    st.session_state["email"] = user["email"]
    st.session_state["full_name"] = user.get("full_name")
    st.session_state["role"] = role_name
    st.session_state["logged_in"] = True


def _clear_session():
    """Logout helper."""
    for key in ["user", "user_id", "email", "full_name", "role",
                "logged_in", "reset_token", "signup_success", "page"]:
        st.session_state.pop(key, None)


# =========================================================
# ✅ USER FETCH HELPERS
# =========================================================

def get_user_by_email(email: str):
    resp = (
        supabase.table("users")
        .select("*")
        .eq("email", email)
        .execute()
    )
    return resp.data if resp.data else None


def get_user_role(user_id: int) -> str:
    """Get EXACT one role for the user."""
    resp = (
        supabase.table("user_roles")
        .select("roles(role_name)")
        .eq("user_id", user_id)
        .execute()
    )

    if not resp.data:
        return None  # No role assigned

    return resp.data[0]["roles"]["role_name"]


# =========================================================
# ✅ PASSWORD HELPERS
# =========================================================

def hash_password(password: str):
    return argon.hash(password)


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        return argon.verify(stored_hash, password)
    except VerifyMismatchError:
        return False


# =========================================================
# ✅ LOGIN PAGE (Option‑A: page switching)
# =========================================================

def login_user():
    st.title("🔐 Login")

    # show signup success
    if st.session_state.get("signup_success"):
        st.success("✅ Account created! Awaiting SuperUser approval.")
        st.session_state["signup_success"] = False

    email = sanitize(st.text_input("Email"))
    password = sanitize(st.text_input("Password", type="password"))

    if st.button("Login", use_container_width=True):

        users = get_user_by_email(email)
        if not users:
            st.error("❌ User not found.")
            return

        user = users[0]

        if not verify_password(password, user["password_hash"]):
            st.error("❌ Incorrect password.")
            return

        # ✅ First check account status from USERS table
        if user["status"] != "Active":
            st.error("⏳ Your account is pending approval.")
            return

        # ✅ Fetch role from role tables
        role_name = get_user_role(user["user_id"])
        if not role_name:
            st.error("❌ No role assigned. Contact administrator.")
            return

        # ✅ Store session
        _set_session(user, role_name)

        st.success("✅ Login successful!")
        st.rerun()

    # Navigation options
    st.write("---")
    col1, col2 = st.columns(2)

    with col1:
        if st.button("Create Account"):
            st.session_state["page"] = "signup"
            st.rerun()

    with col2:
        if st.button("Forgot Password?"):
            st.session_state["page"] = "forgot"
            st.rerun()


# =========================================================
# ✅ SIGNUP PAGE (status = Pending, NO role yet)
# =========================================================

def signup_user():
    st.title("📝 Create Account")

    full_name = sanitize(st.text_input("Full Name"))
    email = sanitize(st.text_input("Email"))
    pwd = st.text_input("Password", type="password")
    confirm = st.text_input("Confirm Password", type="password")

    if st.button("Create Account", use_container_width=True):

        if pwd != confirm:
            st.error("❌ Passwords do not match.")
            return

        if get_user_by_email(email):
            st.error("❌ Email already registered.")
            return

        hashed = hash_password(pwd)

        # ✅ Insert user with DEFAULT status = Pending
        resp = supabase.table("users").insert({
            "full_name": full_name,
            "email": email,
            "password_hash": hashed,
            "status": "Pending",
            "active": True
        }).execute()

        st.session_state["signup_success"] = True
        st.session_state["page"] = "login"
        st.rerun()

    st.write("---")
    if st.button("⬅️ Back to Login"):
        st.session_state["page"] = "login"
        st.rerun()


# =========================================================
# ✅ FORGOT PASSWORD PAGE
# =========================================================

def forgot_password():
    st.title("🔑 Forgot Password")

    email = st.text_input("Enter your email")

    if st.button("Send Reset Link"):

        users = get_user_by_email(email)
        if not users:
            st.warning("If the email is valid, a reset link will be sent.")
            return

        user = users[0]

        import uuid
        token = str(uuid.uuid4())

        supabase.table("password_reset_tokens").insert({
            "user_id": user["user_id"],
            "token": token
        }).execute()

        send_reset_email(email, token)

        st.success("✅ Reset link sent! Check your email.")

    st.write("---")
    if st.button("⬅️ Back to Login"):
        st.session_state["page"] = "login"
        st.rerun()


# =========================================================
# ✅ PASSWORD RESET FORM
# =========================================================

def reset_password(token):
    st.title("🔐 Reset Password")

    new_pwd = st.text_input("New Password", type="password")
    confirm = st.text_input("Confirm Password", type="password")

    if st.button("Reset Password"):
        if new_pwd != confirm:
            st.error("Passwords do not match.")
            return

        # fetch token row
        resp = (
            supabase.table("password_reset_tokens")
            .select("user_id")
            .eq("token", token)
            .execute()
        )

        if not resp.data:
            st.error("❌ Invalid or expired token.")
            return

        user_id = resp.data[0]["user_id"]
        new_hash = hash_password(new_pwd)

        # update password
        supabase.table("users").update({
            "password_hash": new_hash
        }).eq("user_id", user_id).execute()

        supabase.table("password_reset_tokens").delete().eq("token", token).execute()

        st.success("✅ Password updated!")
        st.session_state["page"] = "login"
        st.rerun()


# =========================================================
# ✅ LOGOUT
# =========================================================

def logout_user():
    _clear_session()
    st.rerun()


# =========================================================
# ✅ ROLE GUARD
# =========================================================

def require_role(allowed_roles):
    if "user_id" not in st.session_state or "role" not in st.session_state:
        st.error("🔒 Please login to access this page.")
        st.stop()

    if st.session_state["role"] not in allowed_roles:
        st.error("🚫 You are not authorized to view this page.")
        st.stop()


# =========================================================
# ✅ ROLE ASSIGNMENT (Approval Center)
# =========================================================

def set_user_role(user_id: int, new_role: str):
    """Assign exactly ONE role to user; ensure user.status becomes Active."""

    # get role_id
    role_resp = (
        supabase.table("roles")
        .select("role_id")
        .eq("role_name", new_role)
        .execute()
    )

    if not role_resp.data:
        raise Exception(f"Role '{new_role}' not found.")

    role_id = role_resp.data[0]["role_id"]

    # ✅ Activate user
    supabase.table("users").update({"status": "Active"}).eq("user_id", user_id).execute()

    # ✅ Remove any existing role
    supabase.table("user_roles").delete().eq("user_id", user_id).execute()

    # ✅ Assign new one
    supabase.table("user_roles").insert({
        "user_id": user_id,
        "role_id": role_id
    }).execute()

    # ✅ If updating the logged-in user → update session
    if st.session_state.get("user_id") == user_id:
        st.session_state["role"] = new_role
