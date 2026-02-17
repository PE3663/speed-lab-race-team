import streamlit as st
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from utils.gsheet_db import read_sheet, append_row, get_chassis_list, timestamp_now


def render():
    st.header("📋 Race Day Log")
    chassis_list = get_chassis_list()

    tab1, tab2 = st.tabs(["View Logs", "New Race Day Entry"])

    with tab1:
        df = read_sheet("race_day")
        if not df.empty:
            st.dataframe(df.iloc[::-1], use_container_width=True, hide_index=True)
        else:
            st.info("No race day logs yet.")

    with tab2:
        with st.form("add_race_day", clear_on_submit=True):
            st.subheader("New Race Day Note")
            c1, c2 = st.columns(2)
            with c1:
                track = st.selectbox("Track", ["Sauble Speedway", "Flamboro Speedway", "Delaware Speedway", "Other"])
                race_date = st.date_input("Date")
                chassis = st.selectbox("Chassis", chassis_list if chassis_list else [""])
            with c2:
                weather = st.text_input("Weather (temp, humidity, wind)")
                track_condition = st.selectbox("Track Condition", ["Dry", "Damp", "Wet", "Dusty", "Tacky"])
                air_temp = st.text_input("Air Temp")

            st.markdown("---")
            st.subheader("Session Notes")
            practice_notes = st.text_area("Practice")
            qualifying_notes = st.text_area("Qualifying")
            heat_notes = st.text_area("Heat Race")
            feature_notes = st.text_area("Feature")

            st.subheader("Results")
            rc1, rc2, rc3 = st.columns(3)
            with rc1:
                qual_pos = st.text_input("Qualifying Position")
            with rc2:
                heat_finish = st.text_input("Heat Finish")
            with rc3:
                feature_finish = st.text_input("Feature Finish")

            adjustments = st.text_area("Adjustments Made During Night")
            notes = st.text_area("General Notes")

            if st.form_submit_button("Save Race Day Log", type="primary"):
                append_row("race_day", {
                    "date": str(race_date), "track": track, "chassis": chassis,
                    "weather": weather, "track_condition": track_condition, "air_temp": air_temp,
                    "practice": practice_notes, "qualifying": qualifying_notes,
                    "heat_race": heat_notes, "feature": feature_notes,
                    "qual_position": qual_pos, "heat_finish": heat_finish,
                    "feature_finish": feature_finish, "adjustments": adjustments,
                    "notes": notes, "created": timestamp_now(),
                })
                st.success("Race day log saved!")
                st.rerun()
