import streamlit as st
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from utils.gsheet_db import read_sheet, append_row, delete_row, timestamp_now


def render():
    st.header("🚗 Chassis Profiles")

    tab1, tab2 = st.tabs(["View Chassis", "Add New Chassis"])

    with tab1:
        df = read_sheet("chassis")
        if not df.empty:
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.divider()
            del_name = st.selectbox("Select chassis to delete", df["chassis_name"].tolist())
            if st.button("🗑️ Delete Selected Chassis", type="secondary"):
                row_idx = df[df["chassis_name"] == del_name].index[0] + 2
                delete_row("chassis", row_idx)
                st.success(f"Deleted {del_name}")
                st.rerun()
        else:
            st.info("No chassis profiles yet. Add one below.")

    with tab2:
        with st.form("add_chassis", clear_on_submit=True):
            st.subheader("New Chassis")
            name = st.text_input("Chassis Name *")
            car_number = st.text_input("Car Number")
            car_class = st.selectbox("Class", ["Pro Late Model", "Super Stock", "Bone Stock", "Mini Stock", "Other"])
            year = st.text_input("Year / Make")
            notes = st.text_area("Notes")

            if st.form_submit_button("Save Chassis", type="primary"):
                if not name:
                    st.error("Chassis name is required.")
                else:
                    append_row("chassis", {
                        "chassis_name": name,
                        "car_number": car_number,
                        "car_class": car_class,
                        "year_make": year,
                        "notes": notes,
                        "created": timestamp_now(),
                    })
                    st.success(f"Chassis '{name}' added!")
                    st.rerun()
