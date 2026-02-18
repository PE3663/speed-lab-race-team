import streamlit as st
from utils.gsheet_db import read_sheet, get_chassis_list


def render():
    st.header("🏠 Dashboard")
    st.markdown("Welcome to the **Speed Lab Race Team** setup book and manager.")

    # Quick stats
    col1, col2, col3, col4 = st.columns(4)

    chassis_list = get_chassis_list()
    with col1:
        st.metric("Chassis", len(chassis_list))

    try:
        tires_df = read_sheet("tires")
        active_tires = len(tires_df[tires_df["status"] == "In Use"]) if not tires_df.empty and "status" in tires_df.columns else 0
        total_tires = len(tires_df) if not tires_df.empty else 0
    except Exception:
        active_tires = 0
        total_tires = 0
    with col2:
        st.metric("Active Tires", active_tires)
    with col3:
        st.metric("Total Tires", total_tires)

    try:
        maint_df = read_sheet("maintenance")
        due_count = len(maint_df[maint_df["status"] == "Due"]) if not maint_df.empty and "status" in maint_df.columns else 0
    except Exception:
        due_count = 0
    with col4:
        st.metric("Maintenance Due", due_count, delta_color="inverse")

    st.divider()

    # Recent race day logs
    st.subheader("📋 Recent Race Day Logs")
    try:
        race_df = read_sheet("race_day")
        if not race_df.empty:
            st.dataframe(race_df.tail(5).iloc[::-1], use_container_width=True, hide_index=True)
        else:
            st.info("No race day logs yet. Go to Race Day Log to add your first entry.")
    except Exception:
        st.info("No race day logs yet. Connect your Google Sheet to get started.")

    # Quick links
    st.divider()
    st.subheader("⚡ Quick Actions")
    qc1, qc2, qc3 = st.columns(3)
    with qc1:
        st.markdown("🔧 **Setup Book** \u2014 View and edit chassis setups")
    with qc2:
        st.markdown("🛞 **Tire Inventory** \u2014 Track tire numbers and wear")
    with qc3:
        st.markdown("🛠️ **Maintenance** \u2014 Check upcoming tasks")
