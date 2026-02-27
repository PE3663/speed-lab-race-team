import streamlit as st


def get_role():
    """Return current user's role."""
    return st.session_state.get("user_role", "viewer")


def can_edit():
    """Return True if user can add/edit records."""
    return get_role() in ("admin", "crew")


def can_delete():
    """Return True if user can delete records."""
    return get_role() == "admin"


def is_admin():
    """Return True if user is admin."""
    return get_role() == "admin"
