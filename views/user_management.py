import streamlit as st
from utils.gsheet_db import get_users, add_user, update_user_password, update_user_role, delete_user


def render():
    """Admin-only User Management page."""
    if st.session_state.get("user_role") != "admin":
        st.error("Access denied. This page is for administrators only.")
        return

    st.header("👥 User Management")

    tab_all, tab_add, tab_change, tab_delete = st.tabs(
        ["All Users", "Add User", "Change Password / Role", "Delete User"]
    )

    # ========================
    # TAB 1 -- All Users
    # ========================
    with tab_all:
        st.subheader("All Users")
        df = get_users()
        if df.empty:
            st.info("No users found.")
        else:
            display_cols = [c for c in ["username", "role", "display_name", "created"] if c in df.columns]
            st.dataframe(df[display_cols] if display_cols else df, use_container_width=True, hide_index=True)

    # ========================
    # TAB 2 -- Add User
    # ========================
    with tab_add:
        st.subheader("Add New User")
        with st.form("add_user_form", clear_on_submit=True):
            au1, au2 = st.columns(2)
            with au1:
                new_username = st.text_input("Username *")
                new_display = st.text_input("Display Name")
            with au2:
                new_role = st.selectbox("Role", ["viewer", "crew", "admin"])
            new_password = st.text_input("Password *", type="password", key="add_pw")
            new_password_confirm = st.text_input("Confirm Password *", type="password", key="add_pw_confirm")

            if st.form_submit_button("Add User", type="primary"):
                if not new_username:
                    st.error("Username is required.")
                elif not new_password:
                    st.error("Password is required.")
                elif new_password != new_password_confirm:
                    st.error("Passwords do not match.")
                else:
                    # Check if username already taken
                    existing_df = get_users()
                    already_exists = (
                        not existing_df.empty
                        and "username" in existing_df.columns
                        and new_username.lower() in existing_df["username"].str.lower().tolist()
                    )
                    if already_exists:
                        st.error(f"Username '{new_username}' is already taken.")
                    else:
                        add_user(new_username, new_password, new_role, new_display)
                        st.success(f"User '{new_username}' added with role '{new_role}'.")
                        st.rerun()

    # ========================
    # TAB 3 -- Change Password / Role
    # ========================
    with tab_change:
        st.subheader("Change Password or Role")
        df = get_users()
        if df.empty or "username" not in df.columns:
            st.info("No users to manage.")
        else:
            usernames = df["username"].tolist()
            sel_user = st.selectbox("Select user", usernames, key="change_user_sel")

            st.markdown("#### Change Password")
            with st.form("change_password_form", clear_on_submit=True):
                cp_new = st.text_input("New Password *", type="password", key="cp_new")
                cp_confirm = st.text_input("Confirm New Password *", type="password", key="cp_confirm")
                if st.form_submit_button("Update Password", type="primary"):
                    if not cp_new:
                        st.error("New password is required.")
                    elif cp_new != cp_confirm:
                        st.error("Passwords do not match.")
                    else:
                        if update_user_password(sel_user, cp_new):
                            st.success(f"Password updated for '{sel_user}'.")
                        else:
                            st.error("Failed to update password.")

            st.markdown("#### Change Role")
            with st.form("change_role_form", clear_on_submit=False):
                # Pre-select current role
                current_role = "viewer"
                if not df.empty and "role" in df.columns:
                    match = df[df["username"].str.lower() == sel_user.lower()]
                    if not match.empty:
                        current_role = match.iloc[0].get("role", "viewer")
                role_options = ["viewer", "crew", "admin"]
                role_index = role_options.index(current_role) if current_role in role_options else 0
                new_role_sel = st.selectbox("New Role", role_options, index=role_index, key="cr_new_role")
                if st.form_submit_button("Update Role", type="primary"):
                    if update_user_role(sel_user, new_role_sel):
                        st.success(f"Role for '{sel_user}' updated to '{new_role_sel}'.")
                    else:
                        st.error("Failed to update role.")

    # ========================
    # TAB 4 -- Delete User
    # ========================
    with tab_delete:
        st.subheader("Delete User")
        df = get_users()
        current_admin = st.session_state.get("current_user", "")
        if df.empty or "username" not in df.columns:
            st.info("No users to delete.")
        else:
            # Exclude the currently logged-in admin so they can't delete themselves
            deletable = [u for u in df["username"].tolist() if u.lower() != current_admin.lower()]
            if not deletable:
                st.info("No other users to delete.")
            else:
                del_user_sel = st.selectbox("Select user to delete", deletable, key="del_user_sel")
                if st.button("🗑 Delete Selected User", type="secondary"):
                    st.session_state["confirm_delete_user"] = del_user_sel
                if st.session_state.get("confirm_delete_user") == del_user_sel:
                    st.warning(f"Are you sure you want to delete user **{del_user_sel}**? This cannot be undone.")
                    c_yes, c_no = st.columns(2)
                    with c_yes:
                        if st.button("✅ Yes, Delete", type="primary", key="confirm_del_user_yes"):
                            if delete_user(del_user_sel):
                                st.success(f"User '{del_user_sel}' deleted.")
                            else:
                                st.error("Failed to delete user.")
                            st.session_state.pop("confirm_delete_user", None)
                            st.rerun()
                    with c_no:
                        if st.button("❌ Cancel", key="confirm_del_user_no"):
                            st.session_state.pop("confirm_delete_user", None)
                            st.rerun()
