import streamlit as st
import pandas as pd
from datetime import datetime, date
from utils.gsheet_db import read_sheet, append_row, update_row, timestamp_now


# --------------- Weekly Checklist Template ---------------
WEEKLY_CHECKLIST = {
    "1. Fluids & Engine": [
        "Engine oil level / change if due",
        "Cut oil filter, inspect for metal",
        "Coolant level & leaks",
        "Power steering fluid & leaks",
        "Fuel lines, fittings, pumps, cell - leaks/damage",
    ],
    "2. Driveline & Rear End": [
        "Rear end oil level & magnet check",
        "Driveshaft, yokes, U-joints - play/cracks",
        "Driveshaft safety loop secure",
        "Rear hub bearings - play/spin/grease",
        "Axle splines & drive plates - wear/cracks",
    ],
    "3. Suspension, Steering, Shocks": [
        "Full nut-and-bolt on suspension & heims",
        "Steering rack/box, tie rods, heims, shaft joints",
        "Bilstein AS2 shocks - leaks/shafts/rod ends",
        "Bump sticks - gaps/packers measured & logged",
        "Springs - damage, seated, perches free",
    ],
    "4. Brakes & Wheels": [
        "Rotors - cracks/heat checking",
        "Pads - thickness & taper",
        "Caliper mounts, bolts, lines, fittings",
        "Pedal feel / free play / re-bleed if needed",
        "Wheels - cracks, studs, lug nuts",
    ],
    "5. Chassis, Body, Safety": [
        "Chassis rails & cage joints - cracks/bends",
        "Suspension & steering mounts - cracks",
        "Body mounts, nose, fenders, quarters secure",
        "Seat, belts, window net, steering QR",
        "Fire system - bottle pressure & cables",
        "Battery mount, terminals, master switch",
    ],
    "6. Tires, Alignment, Setup": [
        "Log tire pressures & temps",
        "Inspect tire wear patterns",
        "Check/reset toe, camber, caster",
        "Check/reset ride heights & crossweight",
        "Verify bump stop gaps all four corners",
        "Wheel spacers, beadlocks, valve stems",
    ],
    "7. Electrical & Data": [
        "Fans, pumps, radio, transponder, dash",
        "Wiring - chafing, loose plugs, grounds",
        "Download & review data / notes",
    ],
    "8. Cleaning & Notes": [
        "Full wash - body, chassis, suspension",
        "Note issues found & parts to order",
        "Record final setup for next event",
    ],
}


def _render_weekly_checklist():
    """Render the Weekly Pro Late Model Maintenance Checklist tab."""
    st.subheader("Weekly Pro Late Model Maintenance")
    st.markdown("Check off each item as you complete your weekly maintenance. "
                "Save the checklist when done to keep a dated record.")

    # Load previous checklists
    try:
        history_df = read_sheet("weekly_checklist")
    except Exception:
        history_df = pd.DataFrame()

    st.markdown("---")

    # Date selection for this checklist
    checklist_date = st.date_input("Checklist Date", value=date.today(), key="wc_date")

    # Build flat list of all items for tracking
    all_items = []
    for category, items in WEEKLY_CHECKLIST.items():
        for item in items:
            all_items.append((category, item))

    total_items = len(all_items)

    # Checklist with checkboxes
    checked_items = []
    for category, items in WEEKLY_CHECKLIST.items():
        st.markdown(f"**{category}**")
        for item in items:
            key = f"wc_{category}_{item}"
            val = st.checkbox(item, key=key)
            if val:
                checked_items.append(item)
        st.markdown("")

    # Progress bar
    done_count = len(checked_items)
    progress = done_count / total_items if total_items > 0 else 0
    st.progress(progress, text=f"{done_count} / {total_items} items checked")

    # Save checklist
    col_save, col_reset = st.columns(2)
    with col_save:
        if st.button("Save Checklist", type="primary", use_container_width=True):
            if done_count == 0:
                st.warning("No items checked. Check off completed items before saving.")
            else:
                record = {
                    "timestamp": timestamp_now(),
                    "week_of": str(checklist_date),
                    "items_checked": done_count,
                    "items_total": total_items,
                    "pct_complete": f"{progress * 100:.0f}%",
                }
                for category, items in WEEKLY_CHECKLIST.items():
                    cat_key = category.split(". ", 1)[1] if ". " in category else category
                    cat_checked = [i for i in items if i in checked_items]
                    record[cat_key] = f"{len(cat_checked)}/{len(items)}"

                unchecked = [item for _, item in all_items if item not in checked_items]
                if unchecked:
                    record["skipped_items"] = "; ".join(unchecked[:10])
                else:
                    record["skipped_items"] = ""

                append_row("weekly_checklist", record)
                if done_count == total_items:
                    st.success("All items complete! Checklist saved.")
                    st.balloons()
                else:
                    st.success(f"Checklist saved ({done_count}/{total_items} complete).")

    with col_reset:
        if st.button("Clear All", use_container_width=True):
            st.rerun()

    # Checklist History
    st.markdown("---")
    st.subheader("Checklist History")
    if history_df.empty:
        st.info("No checklists saved yet. Complete your first weekly check above!")
    else:
        display_cols = [c for c in ["week_of", "pct_complete", "items_checked", "items_total",
                                     "Fluids & Engine", "Driveline & Rear End",
                                     "Suspension, Steering, Shocks", "Brakes & Wheels",
                                     "Chassis, Body, Safety", "Tires, Alignment, Setup",
                                     "Electrical & Data", "Cleaning & Notes",
                                     "skipped_items"] if c in history_df.columns]
        if display_cols:
            st.dataframe(
                history_df[display_cols].iloc[::-1],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.dataframe(history_df.iloc[::-1], use_container_width=True, hide_index=True)


def render():
    st.header("Maintenance Log")
    st.markdown("Track all maintenance tasks, schedules, and service history.")

    df = read_sheet("maintenance")

    tab1, tab2, tab3, tab4 = st.tabs(["Active Tasks", "Completed", "New Task", "Weekly Checklist"])

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
                    pri_color = {"Critical": "red", "High": "orange", "Medium": "gold", "Low": "green"}.get(priority, "white")

                    with st.expander(f"{row.get('task', 'Untitled')} - {row.get('system', 'General')}"):
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

    # --- Weekly Checklist ---
    with tab4:
        _render_weekly_checklist()
