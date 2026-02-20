import streamlit as st
from utils.gsheet_db import read_sheet, append_row, get_chassis_list, timestamp_now


def tire_block(prefix, label):
    """Render tire size, stagger, air pressure, spring/bump in a clean layout."""
    st.markdown(f"**{label}**")

    # --- All 4 Tire Sizes in one row ---
    sz1, sz2, sz3, sz4 = st.columns(4)
    with sz1:
        st.markdown("**🔵 LF**")
        lf_size = st.text_input("Tire Size", key=f"{prefix}_tire_lf")
    with sz2:
        st.markdown("**🔴 RF**")
        rf_size = st.text_input("Tire Size", key=f"{prefix}_tire_rf")
    with sz3:
        st.markdown("**🔵 LR**")
        lr_size = st.text_input("Tire Size", key=f"{prefix}_tire_lr")
    with sz4:
        st.markdown("**🔴 RR**")
        rr_size = st.text_input("Tire Size", key=f"{prefix}_tire_rr")

    # --- Stagger row ---
    stg1, stg2 = st.columns(2)
    with stg1:
        stagger_f = st.text_input("Stagger Front (RF − LF)", key=f"{prefix}_stagger_f")
    with stg2:
        stagger_r = st.text_input("Stagger Rear (RR − LR)", key=f"{prefix}_stagger_r")

    # --- Front corner details: Air Pressure / Spring / Bump ---
    st.markdown("**Front Corners**")
    sf1, sf2 = st.columns(2)
    with sf1:
        st.markdown("*🔵 LF*")
        lf_pres   = st.text_input("Air Pressure",     key=f"{prefix}_pres_lf")
        lf_spring = st.text_input("Spring Rate (lbs)", key=f"{prefix}_spring_lf")
        lf_bump   = st.text_input("Bump Spring (lbs)", key=f"{prefix}_bump_lf")
    with sf2:
        st.markdown("*🔴 RF*")
        rf_pres   = st.text_input("Air Pressure",     key=f"{prefix}_pres_rf")
        rf_spring = st.text_input("Spring Rate (lbs)", key=f"{prefix}_spring_rf")
        rf_bump   = st.text_input("Bump Spring (lbs)", key=f"{prefix}_bump_rf")

    # --- Rear corner details: Air Pressure / Spring / Bump ---
    st.markdown("**Rear Corners**")
    sr1, sr2 = st.columns(2)
    with sr1:
        st.markdown("*🔵 LR*")
        lr_pres   = st.text_input("Air Pressure",     key=f"{prefix}_pres_lr")
        lr_spring = st.text_input("Spring Rate (lbs)", key=f"{prefix}_spring_lr")
        lr_bump   = st.text_input("Bump Spring (lbs)", key=f"{prefix}_bump_lr")
    with sr2:
        st.markdown("*🔴 RR*")
        rr_pres   = st.text_input("Air Pressure",     key=f"{prefix}_pres_rr")
        rr_spring = st.text_input("Spring Rate (lbs)", key=f"{prefix}_spring_rr")
        rr_bump   = st.text_input("Bump Spring (lbs)", key=f"{prefix}_bump_rr")

    return {
        f"{prefix}_tire_lf":   lf_size,
        f"{prefix}_pres_lf":   lf_pres,
        f"{prefix}_spring_lf": lf_spring,
        f"{prefix}_bump_lf":   lf_bump,
        f"{prefix}_tire_rf":   rf_size,
        f"{prefix}_pres_rf":   rf_pres,
        f"{prefix}_spring_rf": rf_spring,
        f"{prefix}_bump_rf":   rf_bump,
        f"{prefix}_stagger_f": stagger_f,
        f"{prefix}_tire_lr":   lr_size,
        f"{prefix}_pres_lr":   lr_pres,
        f"{prefix}_spring_lr": lr_spring,
        f"{prefix}_bump_lr":   lr_bump,
        f"{prefix}_tire_rr":   rr_size,
        f"{prefix}_pres_rr":   rr_pres,
        f"{prefix}_spring_rr": rr_spring,
        f"{prefix}_bump_rr":   rr_bump,
        f"{prefix}_stagger_r": stagger_r,
    }


def tire_temp_block(prefix, label):
    """Render tire temp inputs (Inner/Mid/Outer) for all 4 corners inside a form."""
    st.markdown(f"🌡️ **{label} — Tire Temps**")
    corners = ["LF", "RF", "LR", "RR"]
    temps = {}
    tc1, tc2, tc3, tc4 = st.columns(4)
    cols = [tc1, tc2, tc3, tc4]
    icons = ["🔵", "🔴", "🔵", "🔴"]
    for col, corner, icon in zip(cols, corners, icons):
        with col:
            st.markdown(f"**{icon} {corner}**")
            t_in  = st.text_input("Inner",  key=f"{prefix}_temp_{corner}_in")
            t_mid = st.text_input("Middle", key=f"{prefix}_temp_{corner}_mid")
            t_out = st.text_input("Outer",  key=f"{prefix}_temp_{corner}_out")
            temps[corner] = {"inner": t_in, "middle": t_mid, "outer": t_out}
    data = {}
    for corner in corners:
        data[f"{prefix}_temp_{corner}_in"]  = temps[corner]["inner"]
        data[f"{prefix}_temp_{corner}_mid"] = temps[corner]["middle"]
        data[f"{prefix}_temp_{corner}_out"] = temps[corner]["outer"]
    return data


def render():
    st.header("📋 Race Day Log")
    chassis_list = get_chassis_list()

    tab1, tab2, tab3 = st.tabs(["View Logs", "New Race Day Entry", "Tire Temp"])

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

            # Practice #1
            p1 = tire_block("p1", "Practice #1 — Tires & Springs")
            practice_notes = st.text_area("Practice Notes", key="practice_notes")
            p1_temps = tire_temp_block("p1", "Practice #1")
            st.markdown("---")

            # Practice #2
            p2 = tire_block("p2", "Practice #2 — Tires & Springs")
            practice2_notes = st.text_area("Practice #2 Notes", key="practice2_notes")
            p2_temps = tire_temp_block("p2", "Practice #2")
            st.markdown("---")

            qualifying_notes = st.text_area("Qualifying")

            # Heat Race
            st.markdown("---")
            heat = tire_block("heat", "Heat Race — Tires & Springs")
            heat_notes = st.text_area("Heat Race Notes", key="heat_notes")
            heat_temps = tire_temp_block("heat", "Heat Race")

            # Feature
            st.markdown("---")
            feat = tire_block("feat", "Feature — Tires & Springs")
            feature_notes = st.text_area("Feature Notes", key="feature_notes")
            feat_temps = tire_temp_block("feat", "Feature")

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
                    "date": str(race_date),
                    "track": track,
                    "chassis": chassis,
                    "weather": weather,
                    "track_condition": track_condition,
                    "air_temp": air_temp,
                    "practice": practice_notes,
                    "practice2": practice2_notes,
                    "qualifying": qualifying_notes,
                    "heat_race": heat_notes,
                    "feature": feature_notes,
                    "qual_position": qual_pos,
                    "heat_finish": heat_finish,
                    "feature_finish": feature_finish,
                    "adjustments": adjustments,
                    "notes": notes,
                    "created": timestamp_now(),
                }
                row.update(p1)
                row.update(p2)
                row.update(heat)
                row.update(feat)
                row.update(p1_temps)
                row.update(p2_temps)
                row.update(heat_temps)
                row.update(feat_temps)
                append_row("race_day", row)
                st.success("Race day log saved!")
                st.rerun()

    # ==============================================
    # TAB 3 -- Tire Temp (Camber Analysis)
    # ==============================================
    with tab3:
        st.subheader("Tire Temperature Analysis")
        st.caption("Enter tire temps (Inner, Middle, Outer) for each corner. The app will analyze camber based on the temperature spread.")

        corners = ["LF", "RF", "LR", "RR"]
        temps = {}
        for corner in corners:
            with st.expander(f"\U0001f321 {corner} Temps", expanded=True):
                tc1, tc2, tc3 = st.columns(3)
                with tc1:
                    t_in = st.number_input(f"{corner} Inner", min_value=0.0, max_value=500.0, value=0.0, step=1.0, key=f"rdl_{corner}_in")
                with tc2:
                    t_mid = st.number_input(f"{corner} Middle", min_value=0.0, max_value=500.0, value=0.0, step=1.0, key=f"rdl_{corner}_mid")
                with tc3:
                    t_out = st.number_input(f"{corner} Outer", min_value=0.0, max_value=500.0, value=0.0, step=1.0, key=f"rdl_{corner}_out")
                temps[corner] = {"inner": t_in, "middle": t_mid, "outer": t_out}

        st.divider()
        st.subheader("Camber Analysis Results")
        any_data = any(t["inner"] > 0 or t["outer"] > 0 for t in temps.values())
        if not any_data:
            st.info("Enter tire temperatures above to see camber analysis.")
        else:
            for corner in corners:
                t = temps[corner]
                t_in = t["inner"]
                t_out = t["outer"]
                t_mid = t["middle"]
                if t_in == 0 and t_out == 0:
                    continue
                camber_delta = t_in - t_out
                if camber_delta > 10:
                    camber_status = "Too much negative camber"
                    camber_advice = "Reduce negative camber on this corner."
                    icon = "\u26a0\ufe0f"
                elif camber_delta < -10:
                    camber_status = "Not enough negative camber"
                    camber_advice = "Add negative camber or increase roll resistance on this corner."
                    icon = "\u26a0\ufe0f"
                else:
                    camber_status = "Camber OK"
                    camber_advice = "Camber close; adjust only for fine balance."
                    icon = "\u2705"
                with st.container():
                    rc1, rc2 = st.columns([1, 3])
                    with rc1:
                        st.metric(f"{corner} Delta", f"{camber_delta:+.1f}\u00b0")
                    with rc2:
                        st.markdown(f"{icon} **{camber_status}**")
                        st.caption(camber_advice)
                    st.caption(f"Inner: {t_in}\u00b0 | Mid: {t_mid}\u00b0 | Outer: {t_out}\u00b0")
                st.markdown("---")
