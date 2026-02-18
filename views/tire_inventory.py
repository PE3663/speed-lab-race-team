import streamlit as st
from utils.gsheet_db import read_sheet, append_row, delete_row, get_chassis_list, timestamp_now


def render():
    st.header("🛞 Tire Inventory")

    tab1, tab2 = st.tabs(["View Tires", "Add New Tire"])

    with tab1:
        df = read_sheet("tires")
        if not df.empty:
            # Filters
            fc1, fc2, fc3 = st.columns(3)
            with fc1:
                status_filt = st.selectbox("Status", ["All", "New", "In Use", "Used", "Scrapped"])
            with fc2:
                pos_filt = st.selectbox("Position", ["All", "LF", "RF", "LR", "RR", "Spare"])
            with fc3:
                compound_filt = st.text_input("Compound Filter")

            filtered = df.copy()
            if status_filt != "All" and "status" in filtered.columns:
                filtered = filtered[filtered["status"] == status_filt]
            if pos_filt != "All" and "position" in filtered.columns:
                filtered = filtered[filtered["position"] == pos_filt]
            if compound_filt and "compound" in filtered.columns:
                filtered = filtered[filtered["compound"].str.contains(compound_filt, case=False, na=False)]

            st.dataframe(filtered, use_container_width=True, hide_index=True)

            st.divider()
            st.subheader("Quick Stats")
            sc1, sc2, sc3, sc4 = st.columns(4)
            with sc1:
                st.metric("Total", len(df))
            with sc2:
                st.metric("New", len(df[df["status"] == "New"]) if "status" in df.columns else 0)
            with sc3:
                st.metric("In Use", len(df[df["status"] == "In Use"]) if "status" in df.columns else 0)
            with sc4:
                st.metric("Used", len(df[df["status"] == "Used"]) if "status" in df.columns else 0)
        else:
            st.info("No tires in inventory. Add your first tire below.")

    with tab2:
        chassis_list = get_chassis_list()
        with st.form("add_tire", clear_on_submit=True):
            st.subheader("New Tire Entry")

            c1, c2 = st.columns(2)
            with c1:
                tire_number = st.text_input("Tire Number / Serial *")
                brand = st.text_input("Brand (e.g. Hoosier)")
                compound = st.text_input("Compound (e.g. LM20, LM40, D800)")
                size = st.text_input("Size (e.g. 90/11-15)")
            with c2:
                position = st.selectbox("Position", ["LF", "RF", "LR", "RR", "Spare"])
                status = st.selectbox("Status", ["New", "In Use", "Used", "Scrapped"])
                assigned_chassis = st.selectbox("Assigned Chassis", [""] + chassis_list)
                date_purchased = st.date_input("Date Purchased")

            st.markdown("---")
            c3, c4 = st.columns(2)
            with c3:
                durometer = st.text_input("Durometer Reading")
                circumference = st.text_input("Circumference / Rollout")
            with c4:
                laps_run = st.number_input("Laps Run", min_value=0, value=0)
                races_run = st.number_input("Races Run", min_value=0, value=0)

            notes = st.text_area("Notes (heat cycles, shaving, etc.)")

            if st.form_submit_button("Save Tire", type="primary"):
                if not tire_number:
                    st.error("Tire number is required.")
                else:
                    append_row("tires", {
                        "tire_number": tire_number, "brand": brand,
                        "compound": compound, "size": size,
                        "position": position, "status": status,
                        "assigned_chassis": assigned_chassis,
                        "date_purchased": str(date_purchased),
                        "durometer": durometer, "circumference": circumference,
                        "laps_run": laps_run, "races_run": races_run,
                        "notes": notes, "created": timestamp_now(),
                    })
                    st.success(f"Tire '{tire_number}' added!")
                    st.rerun()
