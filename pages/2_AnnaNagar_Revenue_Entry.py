import streamlit as st
from auth import require_role
from constants import ROLE_SUPERUSER, ROLE_EDITOR
from components.revenue_engine import revenue_page

# ✅ Access control
require_role([ROLE_SUPERUSER, ROLE_EDITOR])

revenue_page(
    project_id=1,
    project_name="Cross Courts Anna Nagar"
)
