import streamlit as st
from utils.gsheet_db import read_sheet, append_row, get_chassis_list, timestamp_now

CORNERS = ["LF", "RF", "LR", "RR"]

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

            # --- Practice #1 Tires ---
            st.markdown("**Practice #1 — Tires**")
            p1t_cols = st.columns(6)
            with p1t_cols[0]:
                p1_tire_lf = st.text_input("Tire Size LF", key="p1_tire_lf")
            with p1t_cols[1]:
                p1_tire_rf = st.text_input("Tire Size RF", key="p1_tire_rf")
            with p1t_cols[2]:
                p1_stagger_f = st.text_input("Stagger (F)", key="p1_stagger_f")
            with p1t_cols[3]:
                p1_tire_lr = st.text_input("Tire Size LR", key="p1_tire_lr")
            with p1t_cols[4]:
                p1_tire_rr = st.text_input("Tire Size RR", key="p1_tire_rr")
            with p1t_cols[5]:
                p1_stagger_r = st.text_input("Stagger (R)", key="p1_stagger_r")
            p1p_cols = st.columns(4)
            with p1p_cols[0]:
                p1_pres_lf = st.text_input("Air Pres. LF", key="p1_pres_lf")
            with p1p_cols[1]:
                p1_pres_rf = st.text_input("Air Pres. RF", key="p1_pres_rf")
            with p1p_cols[2]:
                p1_pres_lr = st.text_input("Air Pres. LR", key="p1_pres_lr")
            with p1p_cols[3]:
                p1_pres_rr = st.text_input("Air Pres. RR", key="p1_pres_rr")

            practice_notes = st.text_area("Practice Notes")

            # --- Practice #2 Tires ---
            st.markdown("**Practice #2 — Tires**")
            p2t_cols = st.columns(6)
            with p2t_cols[0]:
                p2_tire_lf = st.text_input("Tire Size LF", key="p2_tire_lf")
            with p2t_cols[1]:
                p2_tire_rf = st.text_input("Tire Size RF", key="p2_tire_rf")
            with p2t_cols[2]:
                p2_stagger_f = st.text_input("Stagger (F)", key="p2_stagger_f")
            with p2t_cols[3]:
                p2_tire_lr = st.text_input("Tire Size LR", key="p2_tire_lr")
            with p2t_cols[4]:
                p2_tire_rr = st.text_input("Tire Size RR", key="p2_tire_rr")
            with p2t_cols[5]:
                p2_stagger_r = st.text_input("Stagger (R)", key="p2_stagger_r")
            p2p_cols = st.columns(4)
            with p2p_cols[0]:
                p2_pres_lf = st.text_input("Air Pres. LF", key="p2_pres_lf")
            with p2p_cols[1]:
                p2_pres_rf = st.text_input("Air Pres. RF", key="p2_pres_rf")
            with p2p_cols[2]:
                p2_pres_lr = st.text_input("Air Pres. LR", key="p2_pres_lr")
            with p2p_cols[3]:
                p2_pres_rr = st.text_input("Air Pres. RR", key="p2_pres_rr")

            practice2_notes = st.text_area("Practice #2 Notes")

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
                    "p1_tire_lf": p1_tire_lf, "p1_tire_rf": p1_tire_rf,
                    "p1_stagger_f": p1_stagger_f,
                    "p1_tire_lr": p1_tire_lr, "p1_tire_rr": p1_tire_rr,
                    "p1_stagger_r": p1_stagger_r,
                    "p1_pres_lf": p1_pres_lf, "p1_pres_rf": p1_pres_rf,
                    "p1_pres_lr": p1_pres_lr, "p1_pres_rr": p1_pres_rr,
                    "practice": practice_notes,
                    "p2_tire_lf": p2_tire_lf, "p2_tire_rf": p2_tire_rf,
                    "p2_stagger_f": p2_stagger_f,
                    "p2_tire_lr": p2_tire_lr, "p2_tire_rr": p2_tire_rr,
                    "p2_stagger_r": p2_stagger_r,
                    "p2_pres_lf": p2_pres_lf, "p2_pres_rf": p2_pres_rf,
                    "p2_pres_lr": p2_pres_lr, "p2_pres_rr": p2_pres_rr,
                    "practice2": practice2_notes,
                    "qualifying": qualifying_notes,
                    "heat_race": heat_notes, "feature": feature_notes,
                    "qual_position": qual_pos, "heat_finish": heat_finish,
                    "feature_finish": feature_finish,
                    "adjustments": adjustments, "notes": notes,
                    "created": timestamp_now(),
                })
                st.success("Race day log saved!")
                st.rerun()
