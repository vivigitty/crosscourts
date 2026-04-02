import streamlit as st
import pandas as pd
import bcrypt
import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

st.set_page_config(page_title="Sports Academy Admin", layout="wide")

# ----------------------------------------------------------
# Utility functions
# ----------------------------------------------------------
def hash_password(password: str):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password: str, hashed: str):
    return bcrypt.checkpw(password.encode(), hashed.encode())

def get_user(username):
    return supabase.table("users").select("*").eq("username", username).execute().data

def get_role(user_id):
    role_data = (
        supabase.table("user_roles")
        .select("roles(role_name)")
        .eq("user_id", user_id)
        .execute()
    ).data

    if role_data:
        return role_data[0]["roles"]["role_name"]
    return None

def assign_role(user_id, role_name):
    # Get role_id
    role_id = (
        supabase.table("roles")
        .select("role_id")
        .eq("role_name", role_name)
        .execute()
    ).data[0]["role_id"]

    # Check if role already exists
    exists = (
        supabase.table("user_roles")
        .select("*")
        .eq("user_id", user_id)
        .eq("role_id", role_id)
        .execute()
    ).data

    if not exists:
        supabase.table("user_roles").insert({"user_id": user_id, "role_id": role_id}).execute()

# ----------------------------------------------------------
# Signup Page
# ----------------------------------------------------------
def signup_page():
    st.header("📝 Create an Account")

    username = st.text_input("Username")
    full_name = st.text_input("Full Name")
    password = st.text_input("Password", type="password")

    if st.button("Sign Up"):
        users = supabase.table("users").select("*").execute().data
        is_first_user = len(users) == 0

        supabase.table("users").insert({
            "username": username,
            "full_name": full_name,
            "password_hash": hash_password(password),
        }).execute()

        new_user = get_user(username)[0]
        user_id = new_user["user_id"]

        # Assign roles
        if is_first_user:
            assign_role(user_id, "SuperUser")
            st.success("✅ You have been registered as the Super User!")
        else:
            assign_role(user_id, "Viewer")
            st.success("✅ Account created! You have Viewer access.")

        st.session_state["user"] = new_user
        st.rerun()

# ----------------------------------------------------------
# Login Page
# ----------------------------------------------------------
def login_page():
    st.header("🔐 Login")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        user = get_user(username)
        if user:
            user = user[0]
            if verify_password(password, user["password_hash"]):
                st.session_state["user"] = user
                st.rerun()
            else:
                st.error("❌ Incorrect password")
        else:
            st.error("❌ User does not exist")

# ----------------------------------------------------------
# Admin Dashboard (SuperUser Only)
# ----------------------------------------------------------
def admin_dashboard():
    st.title("🏆 Super User Dashboard")

    tab1, tab2, tab3, tab4 = st.tabs([
        "Users & Roles", "Projects", "Shareholders", "Project Shareholders"
    ])

    # ---------------- USERS & ROLES ----------------------
    with tab1:
        st.subheader("👥 Manage Users & Roles")

        users = supabase.table("users").select("*").execute().data
        roles = supabase.table("roles").select("*").execute().data

        # Join users with assigned roles
        user_role_query = """
            SELECT 
                u.user_id, u.username, u.full_name,
                r.role_name
            FROM users u
            LEFT JOIN user_roles ur ON ur.user_id = u.user_id
            LEFT JOIN roles r ON r.role_id = ur.role_id;
        """

        user_role_data = supabase.rpc("exec_sql", {"query": user_role_query}).execute().data
        df_roles = pd.DataFrame(user_role_data)

        edited = st.data_editor(df_roles, key="roles_editor")

        if st.button("💾 Save Role Changes"):
            for row in edited.itertuples():
                assign_role(row.user_id, row.role_name)
            st.success("✅ Roles updated!")

    # ---------------- PROJECTS ---------------------------
    with tab2:
        st.subheader("📁 Manage Projects")

        projects = supabase.table("projects").select("*").execute().data
        df_proj = st.data_editor(pd.DataFrame(projects), num_rows="dynamic")

        if st.button("Save Projects"):
            for _, row in df_proj.iterrows():
                if pd.isna(row["project_id"]):
                    supabase.table("projects").insert({"project_name": row["project_name"]}).execute()
                else:
                    supabase.table("projects").update({"project_name": row["project_name"]}).eq("project_id", row["project_id"]).execute()

            st.success("✅ Projects updated!")

    # ---------------- SHAREHOLDERS -----------------------
    with tab3:
        st.subheader("💼 Shareholders")

        sh = supabase.table("shareholders").select("*").execute().data
        df_sh = st.data_editor(pd.DataFrame(sh), num_rows="dynamic")

        if st.button("Save Shareholders"):
            for _, row in df_sh.iterrows():
                if pd.isna(row["shareholder_id"]):
                    supabase.table("shareholders").insert({"shareholder_name": row["shareholder_name"]}).execute()
                else:
                    supabase.table("shareholders").update({"shareholder_name": row["shareholder_name"]}).eq("shareholder_id", row["shareholder_id"]).execute()

            st.success("✅ Shareholders updated!")

    # ---------------- PROJECT SHAREHOLDER SPLIT ----------
    with tab4:
        st.subheader("📊 Project Share Allocations")

        ps = supabase.table("project_shareholders").select("*").execute().data
        df_ps = st.data_editor(pd.DataFrame(ps), num_rows="dynamic")

        if st.button("Save Share Allocations"):
            for _, row in df_ps.iterrows():
                data = {
                    "project_id": int(row["project_id"]),
                    "shareholder_id": int(row["shareholder_id"]),
                    "share_percentage": float(row["share_percentage"]),
                }
                supabase.table("project_shareholders").upsert(data).execute()

            st.success("✅ Shareholders updated!")

# ----------------------------------------------------------
# Viewer Dashboard
# ----------------------------------------------------------
def viewer_dashboard():
    st.title("👁 Viewer Dashboard")
    st.info("You have view-only access.")

# ----------------------------------------------------------
# APP ROUTER
# ----------------------------------------------------------
if "user" not in st.session_state:
    action = st.radio("Choose Action", ["Login", "Sign Up"])
    login_page() if action == "Login" else signup_page()

else:
    role = get_role(st.session_state["user"]["user_id"])

    st.sidebar.write(f"👤 Logged in as: **{st.session_state['user']['username']}**")
    st.sidebar.write(f"🔑 Role: **{role}**")

    if st.sidebar.button("Logout"):
        st.session_state.clear()
        st.rerun()

    if role == "SuperUser":
        admin_dashboard()
    else:
        viewer_dashboard()
