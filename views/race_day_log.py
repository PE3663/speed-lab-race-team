import streamlit as st
from utils.gsheet_db import read_sheet, append_row, get_chassis_list, timestamp_now

def tire_block(prefix, label):
    """Render a 2-col corner layout: [LF, RF] stagger, [LR, RR] stagger. Mobile friendly."""
    st.markdown(f"**{label}**")

    # --- Front row: LF | RF ---
    f1, f2 = st.columns(2)
    with f1:
        st.markdown("**🔵 LF**")
        lf_size = st.text_input("Tire Size", key=f"{prefix}_tire_lf")
    with f2:
        st.markdown("**🔴 RF**")
        rf_size = st.text_input("Tire Size", key=f"{prefix}_tire_rf")

    stagger_f = st.text_input("Stagger Front (RF - LF)", key=f"{prefix}_stagger_f")

    sf1, sf2 = st.columns(2)
    with sf1:
        lf_pres = st.text_input("Air Pressure", key=f"{prefix}_pres_lf")
        lf_spring = st.text_input("Spring Rate (lbs)", key=f"{prefix}_spring_lf")
        lf_bump = st.text_input("Bump Spring (lbs)", key=f"{prefix}_bump_lf")
    with sf2:
        rf_pres = st.text_input("Air Pressure", key=f"{prefix}_pres_rf")
        rf_spring = st.text_input("Spring Rate (lbs)", key=f"{prefix}_spring_rf")
        rf_bump = st.text_input("Bump Spring (lbs)", key=f"{prefix}_bump_rf")

    # --- Rear row: LR | RR ---
    r1, r2 = st.columns(2)
    with r1:
        st.markdown("**🔵 LR**")
        lr_size = st.text_input("Tire Size", key=f"{prefix}_tire_lr")
    with r2:
        st.markdown("**🔴 RR**")
        rr_size = st.text_input("Tire Size", key=f"{prefix}_tire_rr")

    stagger_r = st.text_input("Stagger Rear (RR - LR)", key=f"{prefix}_stagger_r")

    sr1, sr2 = st.columns(2)
    with sr1:
        lr_pres = st.text_input("Air Pressure", key=f"{prefix}_pres_lr")
        lr_spring = st.text_input("Spring Rate (lbs)", key=f"{prefix}_spring_lr")
        lr_bump = st.text_input("Bump Spring (lbs)", key=f"{prefix}_bump_lr")
    with sr2:
        rr_pres = st.text_input("Air Pressure", key=f"{prefix}_pres_rr")
        rr_spring = st.text_input("Spring Rate (lbs)", key=f"{prefix}_spring_rr")
        rr_bump = st.text_input("Bump Spring (lbs)", key=f"{prefix}_bump_rr")

    return {
        f"{prefix}_tire_lf": lf_size, f"{prefix}_pres_lf": lf_pres,
        f"{prefix}_spring_lf": lf_spring, f"{prefix}_bump_lf": lf_bump,
        f"{prefix}_tire_rf": rf_size, f"{prefix}_pres_rf": rf_pres,
        f"{prefix}_spring_rf": rf_spring, f"{prefix}_bump_rf": rf_bump,
        f"{prefix}_stagger_f": stagger_f,
        f"{prefix}_tire_lr": lr_size, f"{prefix}_pres_lr": lr_pres,
        f"{prefix}_spring_lr": lr_spring, f"{prefix}_bump_lr": lr_bump,
        f"{prefix}_tire_rr": rr_size, f"{prefix}_pres_rr": rr_pres,
        f"{prefix}_spring_rr": rr_spring, f"{prefix}_bump_rr": rr_bump,
        f"{prefix}_stagger_r": stagger_r,
    }

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

            # Practice #1 tires
            p1 = tire_block("p1", "Practice #1 — Tires & Springs")
            practice_notes = st.text_area("Practice Notes", key="practice_notes")
            st.markdown("---")

            # Practice #2 tires
            p2 = tire_block("p2", "Practice #2 — Tires & Springs")
            practice2_notes = st.text_area("Practice #2 Notes", key="practice2_notes")
            st.markdown("---")

            qualifying_notes = st.text_area("Qualifying")

            # Heat Race tires
            st.markdown("---")
            heat = tire_block("heat", "Heat Race — Tires & Springs")
            heat_notes = st.text_area("Heat Race Notes", key="heat_notes")

            # Feature tires
            st.markdown("---")
            feat = tire_block("feat", "Feature — Tires & Springs")
            feature_notes = st.text_area("Feature Notes", key="feature_notes")

            st.markdown("---")
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
                row = {
                    "date": str(race_date), "track": track, "chassis": chassis,
                    "weather": weather, "track_condition": track_condition, "air_temp": air_temp,
                    "practice": practice_notes,
                    "practice2": practice2_notes,
                    "qualifying": qualifying_notes,
                    "heat_race": heat_notes, "feature": feature_notes,
                    "qual_position": qual_pos, "heat_finish": heat_finish,
                    "feature_finish": feature_finish,
                    "adjustments": adjustments, "notes": notes,
                    "created": timestamp_now(),
                }
                row.update(p1)
                row.update(p2)
                row.update(heat)
                row.update(feat)
                append_row("race_day", row)
                st.success("Race day log saved!")
                st.rerun()
