# =========================================================
# auth.py
# Authentication logic: signup, login, reset password
# =========================================================

import streamlit as st
import uuid
from argon2 import PasswordHasher

from db import (
    create_user,
    get_user_by_email,
)
from constants import (
    STATUS_PENDING,
    STATUS_ACTIVE,
)
from sanitization import sanitize
from email_utils import send_reset_email

# Argon2 Password Hasher
argon = PasswordHasher()


# =========================================================
# ✅ Password Hashing (Argon2)
# =========================================================

def hash_password(password: str):
    return argon.hash(password)


def verify_password(password: str, stored_hash: str):
    try:
        return argon.verify(stored_hash, password)
    except Exception:
        return False


# =========================================================
# ✅ LOGIN PAGE
# =========================================================

def login_user():
    st.title("🔐 Login")

    # ✅ Show signup success message (from previous redirect)
    if st.session_state.get("signup_success"):
        st.success("✅ Account created! Awaiting administrator approval.")
        st.session_state["signup_success"] = False

    email = sanitize(st.text_input("Email"))
    password = sanitize(st.text_input("Password", type="password"))

    if st.button("Login"):
        users = get_user_by_email(email)
        if not users:
            st.error("User not found.")
            return

        user = users[0]

        # ✅ Check account status
        if user["status"] == STATUS_PENDING:
            st.error("Your account is awaiting approval by the administrator.")
            return

        if user["status"] != STATUS_ACTIVE:
            st.error("Your account is not active.")
            return

        # ✅ Validate password
        if verify_password(password, user["password_hash"]):
            st.session_state["user"] = user
            st.success("✅ Login successful!")
            st.rerun()
        else:
            st.error("Incorrect password.")

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
# ✅ SIGNUP PAGE
# =========================================================

def signup_user():
    st.title("📝 Create Account")

    email = sanitize(st.text_input("Email"))
    full_name = sanitize(st.text_input("Full Name"))
    password = sanitize(st.text_input("Password", type="password"))

    if st.button("Sign Up"):
        if not email or "@" not in email:
            st.error("Invalid email address.")
            return

        if len(password) < 6:
            st.error("Password must be at least 6 characters.")
            return

        # ✅ Prevent duplicate signup
        if get_user_by_email(email):
            st.error("Email already registered.")
            return

        hashed = hash_password(password)

        # ✅ Create Pending user
        create_user(email, full_name, hashed)

        # ✅ Store a flag so Login page can show the success message
        st.session_state["signup_success"] = True

        # ✅ Move user to login page
        st.session_state["page"] = "login"
        st.rerun()

    if st.button("⬅ Back to Login"):
        st.session_state["page"] = "login"
        st.rerun()


# =========================================================
# ✅ FORGOT PASSWORD PAGE
# =========================================================

def forgot_password():
    st.title("🔑 Forgot Password")

    email = sanitize(st.text_input("Enter your email"))

    if st.button("Send Reset Email"):
        users = get_user_by_email(email)
        if not users:
            st.error("Email not found.")
            return

        user = users[0]
        token = str(uuid.uuid4())

        # Store token in DB
        from db import supabase
        supabase.table("password_reset_tokens").insert({
            "token": token,
            "user_id": user["user_id"]
        }).execute()

        send_reset_email(email, token)
        st.success("✅ Reset link has been sent to your email.")

    if st.button("⬅ Back to Login"):
        st.session_state["page"] = "login"
        st.rerun()


# =========================================================
# ✅ RESET PASSWORD PAGE
# =========================================================

def reset_password(token):
    st.title("🔐 Reset Password")

    from db import supabase
    record = supabase.table("password_reset_tokens").select("*").eq("token", token).execute().data

    if not record:
        st.error("Invalid or expired reset link.")
        return

    user_id = record[0]["user_id"]
    new_pw = sanitize(st.text_input("New Password", type="password"))

    if len(new_pw) < 6:
        st.error("Password must be at least 6 characters.")
        return

    if st.button("Update Password"):
        hashed = hash_password(new_pw)

        supabase.table("users").update({"password_hash": hashed}).eq("user_id", user_id).execute()

        # Delete token so it cannot be reused
        supabase.table("password_reset_tokens").delete().eq("token", token).execute()

        st.success("✅ Password updated. Please log in.")
        st.session_state["page"] = "login"
        st.rerun()
