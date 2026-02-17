import streamlit as st

# ── Speed Lab Race Team App ──────────────────────────────────
# Main entry point — run with: streamlit run app.py
# ────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Speed Lab Race Team",
    page_icon="🏁",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Simple Authentication ───────────────────────────────────
def check_password():
    """Returns True if the user has entered a correct password."""
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if st.session_state.authenticated:
        return True

    # Read credentials from Streamlit secrets
    # In .streamlit/secrets.toml add:
    # [passwords]
    # admin = "your_admin_password"
    # crew1 = "crew_member_password"
    try:
        valid_users = dict(st.secrets["passwords"])
    except Exception:
        # Fallback for local dev — change these!
        valid_users = {"admin": "speedlab2026"}

    st.markdown(
        """
        <div style="text-align:center; padding-top:60px;">
            <h1 style="color:#cc0000;">🏁 Speed Lab Race Team</h1>
            <p style="color:#888; font-size:1.1rem;">Setup Book & Team Manager</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        username = st.text_input("Username", key="login_user")
        password = st.text_input("Password", type="password", key="login_pass")
        if st.button("Login", use_container_width=True, type="primary"):
            if username in valid_users and valid_users[username] == password:
                st.session_state.authenticated = True
                st.session_state.current_user = username
                st.rerun()
            else:
                st.error("Invalid username or password.")
    return False


if not check_password():
    st.stop()

# ── Sidebar Navigation ─────────────────────────────────────
with st.sidebar:
    st.image("https://img.icons8.com/color/96/checkered-flag.png", width=60)
    st.markdown("## Speed Lab Race Team")
    st.caption(f"Logged in as **{st.session_state.get('current_user', '')}**")
    st.divider()

    page = st.radio(
        "Navigate",
        [
            "🏠 Dashboard",
            "🚗 Chassis Profiles",
            "🔧 Setup Book",
            "📋 Race Day Log",
            "🛞 Tire Inventory",
            "📦 Parts Inventory",
            "🛠️ Maintenance",
            "🎯 Trackside Tuning",
        ],
        label_visibility="collapsed",
    )

    st.divider()
    if st.button("Logout", use_container_width=True):
        st.session_state.authenticated = False
        st.session_state.current_user = ""
        st.rerun()

# ── Page Router ─────────────────────────────────────────────
if page == "🏠 Dashboard":
    from pages import dashboard
    dashboard.render()
elif page == "🚗 Chassis Profiles":
    from pages import chassis_profiles
    chassis_profiles.render()
elif page == "🔧 Setup Book":
    from pages import setup_book
    setup_book.render()
elif page == "📋 Race Day Log":
    from pages import race_day_log
    race_day_log.render()
elif page == "🛞 Tire Inventory":
    from pages import tire_inventory
    tire_inventory.render()
elif page == "📦 Parts Inventory":
    from pages import parts_inventory
    parts_inventory.render()
elif page == "🛠️ Maintenance":
    from pages import maintenance
    maintenance.render()
elif page == "🎯 Trackside Tuning":
    from pages import trackside_tuning
    trackside_tuning.render()
