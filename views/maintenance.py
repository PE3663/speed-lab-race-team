import streamlit as st
import pandas as pd
from datetime import datetime, date
from utils.gsheet_db import read_sheet, append_row, update_row, timestamp_now


def render():
    st.header("🛠️ Maintenance Log")
    st.markdown("Track all maintenance tasks, schedules, and service history.")

    df = read_sheet("maintenance")

    tab1, tab2, tab3 = st.tabs(["Active Tasks", "Completed", "New Task"])

    # --- Active Tasks ---
    with tab1:
        if df.empty:
            st.info("No maintenance tasks logged yet.")
        else:
            active = df[df.get("status", pd.Series(["Open"] * len(df))) != "Completed"] if "status" in df.columns else df

            if active.empty:
                st.success("All maintenance tasks are completed!")
            else:
                st.subheader(f"Active Tasks ({len(active)})")

                # Priority filter
                if "priority" in active.columns:
                    pri_filter = st.selectbox("Filter by Priority", ["All", "Critical", "High", "Medium", "Low"])
                    if pri_filter != "All":
                        active = active[active["priority"] == pri_filter]

                for i, row in active.iterrows():
                    priority = row.get("priority", "Medium")
                    pri_color = {"Critical": "🔴", "High": "🟠", "Medium": "🟡", "Low": "🟢"}.get(priority, "⚪")

                    with st.expander(f"{pri_color} {row.get('task', 'Untitled')} - {row.get('system', 'General')}"):
                        mc1, mc2, mc3 = st.columns(3)
                        with mc1:
                            st.markdown(f"**System:** {row.get('system', '-')}")
                            st.markdown(f"**Priority:** {priority}")
                        with mc2:
                            st.markdown(f"**Due Date:** {row.get('due_date', '-')}")
                            st.markdown(f"**Assigned To:** {row.get('assigned_to', '-')}")
                        with mc3:
                            st.markdown(f"**Status:** {row.get('status', 'Open')}")
                            st.markdown(f"**Created:** {row.get('created', '-')}")

                        if row.get("description"):
                            st.markdown(f"**Details:** {row['description']}")

                        bc1, bc2, bc3 = st.columns(3)
                        with bc1:
                            if st.button("Mark In Progress", key=f"prog_{i}"):
                                update_row("maintenance", int(i) + 2, {**row.to_dict(), "status": "In Progress", "updated": timestamp_now()})
                                st.rerun()
                        with bc2:
                            if st.button("Mark Complete", key=f"done_{i}"):
                                update_row("maintenance", int(i) + 2, {**row.to_dict(), "status": "Completed", "completed_date": str(date.today()), "updated": timestamp_now()})
                                st.rerun()
                        with bc3:
                            if st.button("Mark Critical", key=f"crit_{i}"):
                                update_row("maintenance", int(i) + 2, {**row.to_dict(), "priority": "Critical", "updated": timestamp_now()})
                                st.rerun()

    # --- Completed Tasks ---
    with tab2:
        if df.empty or "status" not in df.columns:
            st.info("No completed tasks yet.")
        else:
            completed = df[df["status"] == "Completed"]
            if completed.empty:
                st.info("No completed tasks yet.")
            else:
                st.subheader(f"Completed Tasks ({len(completed)})")
                display_cols = [c for c in ["task", "system", "priority", "completed_date", "assigned_to", "description"] if c in completed.columns]
                st.dataframe(completed[display_cols] if display_cols else completed, use_container_width=True, hide_index=True)

    # --- New Task ---
    with tab3:
        with st.form("new_maintenance", clear_on_submit=True):
            st.subheader("Log New Maintenance Task")
            tc1, tc2 = st.columns(2)
            with tc1:
                task = st.text_input("Task Name *", placeholder="e.g., Change rear end oil")
                system = st.selectbox("System", [
                    "Engine", "Transmission", "Rear End", "Suspension",
                    "Brakes", "Steering", "Electrical", "Cooling",
                    "Fuel System", "Body/Chassis", "Safety Equipment", "Other"
                ])
                priority = st.selectbox("Priority", ["Low", "Medium", "High", "Critical"])
            with tc2:
                due_date = st.date_input("Due Date", value=date.today())
                assigned_to = st.text_input("Assigned To")
                status = st.selectbox("Initial Status", ["Open", "In Progress"])

            description = st.text_area("Description / Notes", height=120, placeholder="Describe the work needed...")
            parts_needed = st.text_input("Parts Needed", placeholder="e.g., 2qt gear oil, gasket")
            estimated_time = st.text_input("Estimated Time", placeholder="e.g., 30 min")

            if st.form_submit_button("Add Maintenance Task", type="primary"):
                if not task:
                    st.error("Task name is required.")
                else:
                    append_row("maintenance", {
                        "task": task, "system": system, "priority": priority,
                        "due_date": str(due_date), "assigned_to": assigned_to,
                        "status": status, "description": description,
                        "parts_needed": parts_needed, "estimated_time": estimated_time,
                        "completed_date": "", "created": timestamp_now(),
                        "updated": timestamp_now(),
                    })
                    st.success(f"Maintenance task '{task}' added!")
                    st.rerun()
