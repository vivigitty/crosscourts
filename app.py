# =========================================================
# app.py — Main controller for the Cross Courts System
# Handles authentication, routing, and page access
# =========================================================

import streamlit as st
from auth import (
    login_user,
    signup_user,
    forgot_password,
    reset_password,
)
from roles import get_user_status
from constants import STATUS_PENDING, STATUS_ACTIVE


st.set_page_config(
    page_title="Cross Courts Admin",
    layout="wide",
    initial_sidebar_state="expanded"
)


# =========================================================
# ✅ PAGE ROUTING CONTROLLER
# =========================================================

def route_main():
    """Main router that decides what to show based on session state."""
    query_params = st.query_params

    # ✅ Handle password reset tokens from email
    if "reset_token" in query_params:
        token = query_params["reset_token"]
        reset_password(token)
        return

    # ✅ Initial landing page
    if "page" not in st.session_state:
        st.session_state["page"] = "login"

    page = st.session_state["page"]

    # ✅ If user is NOT logged in → show auth pages
    if "user" not in st.session_state:

        if page == "login":
            login_user()
            return

        elif page == "signup":
            signup_user()
            return

        elif page == "forgot":
            forgot_password()
            return

        else:
            # fallback
            st.session_state["page"] = "login"
            login_user()
            return

    # ✅ If user IS logged in → enforce status rules
    user = st.session_state["user"]
    status = get_user_status(user["user_id"])

    if status == STATUS_PENDING:
        st.error("✅ Logged in, but your account is awaiting approval by the Administrator.")
        st.info("Please wait until your account is activated.")
        if st.sidebar.button("Logout"):
            st.session_state.clear()
            st.rerun()
        return

    if status != STATUS_ACTIVE:
        st.error("Your account is not active.")
        if st.sidebar.button("Logout"):
            st.session_state.clear()
            st.rerun()
        return

    # ✅ Authenticated + Active → Show the multi‑page sidebar navigation
    show_authenticated_home()


# =========================================================
# ✅ AUTHENTICATED USER HOME + SIDEBAR
# =========================================================

def show_authenticated_home():

    user = st.session_state["user"]

    st.sidebar.title("📌 Navigation")

    st.sidebar.write(f"👤 **{user['email']}**")

    if st.sidebar.button("Logout"):
        st.session_state.clear()
        st.rerun()

    st.title("✅ Logged In Successfully")
    st.write("Use the sidebar to navigate between application pages.")

    st.success("You are logged in. Navigate using the left sidebar.")


# =========================================================
# ✅ RUN ROUTER
# =========================================================

if __name__ == "__main__":
    route_main()
