import streamlit as st
from utils.gsheet_db import (
    read_sheet, get_chassis_list, timestamp_now,
    find_race_day, upsert_race_day, ensure_race_day_headers,
)

# ── All column headers the race_day sheet needs ──
ALL_HEADERS = [
    "date", "track", "chassis", "weather", "track_condition", "air_temp",
    "practice", "practice2", "qualifying", "heat_race", "feature",
    "qual_position", "heat_finish", "feature_finish",
    "adjustments", "notes", "created",
]
_SESSIONS = ["p1", "p2", "heat", "feat"]
_CORNERS  = ["LF", "RF", "LR", "RR"]
for s in _SESSIONS:
    for field in ["tire", "pres", "spring", "bump"]:
        for c in _CORNERS:
            ALL_HEADERS.append(f"{s}_{field}_{c.lower()}")
    ALL_HEADERS.append(f"{s}_stagger_f")
    ALL_HEADERS.append(f"{s}_stagger_r")
    for c in _CORNERS:
        for zone in ["in", "mid", "out"]:
            ALL_HEADERS.append(f"{s}_temp_{c}_{zone}")


def _v(data, key, default=""):
    """Get a value from a dict, returning default if missing or empty."""
    val = data.get(key, default)
    return val if val else default


def _vf(data, key, default=0.0):
    """Get a float value from a dict."""
    val = data.get(key, "")
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def tire_block(prefix, label, data):
    """Tire size, stagger, air pressure, spring/bump inside a form."""
    st.markdown(f"**{label}**")
    sz1, sz2, sz3, sz4 = st.columns(4)
    with sz1:
        st.markdown("**🔵 LF**")
        lf_sz = st.text_input("Tire Size", value=_v(data, f"{prefix}_tire_lf"), key=f"{prefix}_tire_lf")
    with sz2:
        st.markdown("**🔴 RF**")
        rf_sz = st.text_input("Tire Size", value=_v(data, f"{prefix}_tire_rf"), key=f"{prefix}_tire_rf")
    with sz3:
        st.markdown("**🔵 LR**")
        lr_sz = st.text_input("Tire Size", value=_v(data, f"{prefix}_tire_lr"), key=f"{prefix}_tire_lr")
    with sz4:
        st.markdown("**🔴 RR**")
        rr_sz = st.text_input("Tire Size", value=_v(data, f"{prefix}_tire_rr"), key=f"{prefix}_tire_rr")
    sg1, sg2 = st.columns(2)
    with sg1:
        stg_f = st.text_input("Stagger Front (RF − LF)", value=_v(data, f"{prefix}_stagger_f"), key=f"{prefix}_stagger_f")
    with sg2:
        stg_r = st.text_input("Stagger Rear (RR − LR)", value=_v(data, f"{prefix}_stagger_r"), key=f"{prefix}_stagger_r")
    st.markdown("**Front Corners**")
    sf1, sf2 = st.columns(2)
    with sf1:
        st.markdown("*🔵 LF*")
        lf_pr = st.text_input("Air Pressure", value=_v(data, f"{prefix}_pres_lf"), key=f"{prefix}_pres_lf")
        lf_sp = st.text_input("Spring Rate (lbs)", value=_v(data, f"{prefix}_spring_lf"), key=f"{prefix}_spring_lf")
        lf_bu = st.text_input("Bump Spring (lbs)", value=_v(data, f"{prefix}_bump_lf"), key=f"{prefix}_bump_lf")
    with sf2:
        st.markdown("*🔴 RF*")
        rf_pr = st.text_input("Air Pressure", value=_v(data, f"{prefix}_pres_rf"), key=f"{prefix}_pres_rf")
        rf_sp = st.text_input("Spring Rate (lbs)", value=_v(data, f"{prefix}_spring_rf"), key=f"{prefix}_spring_rf")
        rf_bu = st.text_input("Bump Spring (lbs)", value=_v(data, f"{prefix}_bump_rf"), key=f"{prefix}_bump_rf")
    st.markdown("**Rear Corners**")
    sr1, sr2 = st.columns(2)
    with sr1:
        st.markdown("*🔵 LR*")
        lr_pr = st.text_input("Air Pressure", value=_v(data, f"{prefix}_pres_lr"), key=f"{prefix}_pres_lr")
        lr_sp = st.text_input("Spring Rate (lbs)", value=_v(data, f"{prefix}_spring_lr"), key=f"{prefix}_spring_lr")
        lr_bu = st.text_input("Bump Spring (lbs)", value=_v(data, f"{prefix}_bump_lr"), key=f"{prefix}_bump_lr")
    with sr2:
        st.markdown("*🔴 RR*")
        rr_pr = st.text_input("Air Pressure", value=_v(data, f"{prefix}_pres_rr"), key=f"{prefix}_pres_rr")
        rr_sp = st.text_input("Spring Rate (lbs)", value=_v(data, f"{prefix}_spring_rr"), key=f"{prefix}_spring_rr")
        rr_bu = st.text_input("Bump Spring (lbs)", value=_v(data, f"{prefix}_bump_rr"), key=f"{prefix}_bump_rr")
    return {
        f"{prefix}_tire_lf": lf_sz, f"{prefix}_pres_lf": lf_pr, f"{prefix}_spring_lf": lf_sp, f"{prefix}_bump_lf": lf_bu,
        f"{prefix}_tire_rf": rf_sz, f"{prefix}_pres_rf": rf_pr, f"{prefix}_spring_rf": rf_sp, f"{prefix}_bump_rf": rf_bu,
        f"{prefix}_tire_lr": lr_sz, f"{prefix}_pres_lr": lr_pr, f"{prefix}_spring_lr": lr_sp, f"{prefix}_bump_lr": lr_bu,
        f"{prefix}_tire_rr": rr_sz, f"{prefix}_pres_rr": rr_pr, f"{prefix}_spring_rr": rr_sp, f"{prefix}_bump_rr": rr_bu,
        f"{prefix}_stagger_f": stg_f, f"{prefix}_stagger_r": stg_r,
    }


def tire_temp_block(prefix, label, data):
    """Tire temps with expanders + inline camber analysis (matches Tire Temp tab)."""
    st.markdown(f"\U0001f321\ufe0f **{label} \u2014 Tire Temps**")
    corners = ["LF", "RF", "LR", "RR"]
    temps = {}
    result = {}
    for corner in corners:
        with st.expander(f"\U0001f321 {corner} Temps", expanded=True):
            tc1, tc2, tc3 = st.columns(3)
            with tc1:
                t_in = st.number_input(f"{corner} Inner", min_value=0.0, max_value=500.0, value=_vf(data, f"{prefix}_temp_{corner}_in"), step=1.0, key=f"{prefix}_temp_{corner}_in")
            with tc2:
                t_mid = st.number_input(f"{corner} Middle", min_value=0.0, max_value=500.0, value=_vf(data, f"{prefix}_temp_{corner}_mid"), step=1.0, key=f"{prefix}_temp_{corner}_mid")
            with tc3:
                t_out = st.number_input(f"{corner} Outer", min_value=0.0, max_value=500.0, value=_vf(data, f"{prefix}_temp_{corner}_out"), step=1.0, key=f"{prefix}_temp_{corner}_out")
            temps[corner] = {"inner": t_in, "middle": t_mid, "outer": t_out}
            result[f"{prefix}_temp_{corner}_in"] = t_in
            result[f"{prefix}_temp_{corner}_mid"] = t_mid
            result[f"{prefix}_temp_{corner}_out"] = t_out
    # Inline camber analysis
    any_data = any(t["inner"] > 0 or t["outer"] > 0 for t in temps.values())
    if any_data:
        st.markdown("**Camber Analysis**")
        for corner in corners:
            t = temps[corner]
            if t["inner"] == 0 and t["outer"] == 0:
                continue
            delta = t["inner"] - t["outer"]
            if delta > 10:
                icon, status = "\u26a0\ufe0f", "Too much negative camber"
            elif delta < -10:
                icon, status = "\u26a0\ufe0f", "Not enough negative camber"
            else:
                icon, status = "\u2705", "Camber OK"
            rc1, rc2 = st.columns([1, 3])
            with rc1:
                st.metric(f"{corner} Delta", f"{delta:+.1f}\u00b0")
            with rc2:
                st.markdown(f"{icon} **{status}**")
                st.caption(f"Inner: {t['inner']}\u00b0 | Mid: {t['middle']}\u00b0 | Outer: {t['outer']}\u00b0")
    return result


def session_form(prefix, session_label, notes_key, data, date_str, track):
    """Render a full session form with its own Save button."""
    with st.form(f"form_{prefix}", clear_on_submit=False):
        setup_data = tire_block(prefix, f"{session_label} \u2014 Tires & Springs", data)
        notes_val = st.text_area(f"{session_label} Notes", value=_v(data, notes_key), key=f"{prefix}_notes_input")
        temp_data = tire_temp_block(prefix, session_label, data)
        if st.form_submit_button(f"\U0001f4be Save {session_label}", type="primary"):
            save = {notes_key: notes_val, "created": timestamp_now()}
            save.update(setup_data)
            save.update(temp_data)
            upsert_race_day(date_str, track, save)
            st.success(f"{session_label} saved!")
            st.rerun()


def render():
    st.header("📋 Race Day Log")
    chassis_list = get_chassis_list()
    ensure_race_day_headers(ALL_HEADERS)

    tab_log, tab_entry, tab_temp = st.tabs(["View Logs", "Race Day Entry", "Tire Temp"])

    # ========================
    # TAB 1 -- View Logs
    # ========================
    with tab_log:
        df = read_sheet("race_day")
        if not df.empty:
            st.dataframe(df.iloc[::-1], use_container_width=True, hide_index=True)
        else:
            st.info("No race day logs yet.")

    # ========================
    # TAB 2 -- Race Day Entry
    # ========================
    with tab_entry:
        st.subheader("Select Race Day")
        hc1, hc2 = st.columns(2)
        with hc1:
            track = st.selectbox("Track", ["Sauble Speedway", "Flamboro Speedway", "Delaware Speedway", "Other"], key="rd_track")
            race_date = st.date_input("Date", key="rd_date")
        with hc2:
            chassis = st.selectbox("Chassis", chassis_list if chassis_list else [""], key="rd_chassis")

        date_str = str(race_date)
        _, existing = find_race_day(date_str, track)
        data = existing if existing else {}

        if data:
            st.success(f"\u2705 Loaded existing race day: {track} \u2014 {date_str}")
        else:
            st.info("\U0001f195 New race day. Fill in sessions below and save as you go.")

        # Race Day Info form
        with st.form("form_header", clear_on_submit=False):
            st.subheader("Race Day Info")
            ic1, ic2, ic3 = st.columns(3)
            with ic1:
                weather = st.text_input("Weather (temp, humidity, wind)", value=_v(data, "weather"), key="rd_weather")
            with ic2:
                track_condition = st.selectbox("Track Condition", ["Dry", "Damp", "Wet", "Dusty", "Tacky"], index=["Dry", "Damp", "Wet", "Dusty", "Tacky"].index(_v(data, "track_condition", "Dry")), key="rd_condition")
            with ic3:
                air_temp = st.text_input("Air Temp", value=_v(data, "air_temp"), key="rd_air_temp")
            if st.form_submit_button("\U0001f4be Save Race Day Info", type="primary"):
                save = {
                    "chassis": chassis,
                    "weather": weather,
                    "track_condition": track_condition,
                    "air_temp": air_temp,
                    "created": timestamp_now(),
                }
                upsert_race_day(date_str, track, save)
                st.success("Race day info saved!")
                st.rerun()

        st.markdown("---")
        st.subheader("Session Notes")
        st.caption("Each session saves independently \u2014 fill in and save as you go throughout the day.")

        # Practice #1
        session_form("p1", "Practice #1", "practice", data, date_str, track)
        st.markdown("---")

        # Practice #2
        session_form("p2", "Practice #2", "practice2", data, date_str, track)
        st.markdown("---")

        # Qualifying
        with st.form("form_qual", clear_on_submit=False):
            qual_notes = st.text_area("Qualifying Notes", value=_v(data, "qualifying"), key="qual_notes_input")
            if st.form_submit_button("\U0001f4be Save Qualifying", type="primary"):
                upsert_race_day(date_str, track, {"qualifying": qual_notes, "created": timestamp_now()})
                st.success("Qualifying saved!")
                st.rerun()
        st.markdown("---")

        # Heat Race
        session_form("heat", "Heat Race", "heat_race", data, date_str, track)
        st.markdown("---")

        # Feature
        session_form("feat", "Feature", "feature", data, date_str, track)
        st.markdown("---")

        # Results
        with st.form("form_results", clear_on_submit=False):
            st.subheader("Results")
            rc1, rc2, rc3 = st.columns(3)
            with rc1:
                qual_pos = st.text_input("Qualifying Position", value=_v(data, "qual_position"), key="rd_qual_pos")
            with rc2:
                heat_fin = st.text_input("Heat Finish", value=_v(data, "heat_finish"), key="rd_heat_fin")
            with rc3:
                feat_fin = st.text_input("Feature Finish", value=_v(data, "feature_finish"), key="rd_feat_fin")
            adjustments = st.text_area("Adjustments Made During Night", value=_v(data, "adjustments"), key="rd_adjustments")
            notes = st.text_area("General Notes", value=_v(data, "notes"), key="rd_notes")
            if st.form_submit_button("\U0001f4be Save Results & Notes", type="primary"):
                save = {
                    "qual_position": qual_pos,
                    "heat_finish": heat_fin,
                    "feature_finish": feat_fin,
                    "adjustments": adjustments,
                    "notes": notes,
                    "created": timestamp_now(),
                }
                upsert_race_day(date_str, track, save)
                st.success("Results & notes saved!")
                st.rerun()

    # ========================
    # TAB 3 -- Tire Temp Calculator
    # ========================
    with tab_temp:
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
                if t["inner"] == 0 and t["outer"] == 0:
                    continue
                delta = t["inner"] - t["outer"]
                if delta > 10:
                    icon, status, advice = "\u26a0\ufe0f", "Too much negative camber", "Reduce negative camber on this corner."
                elif delta < -10:
                    icon, status, advice = "\u26a0\ufe0f", "Not enough negative camber", "Add negative camber or increase roll resistance on this corner."
                else:
                    icon, status, advice = "\u2705", "Camber OK", "Camber close; adjust only for fine balance."
                with st.container():
                    rc1, rc2 = st.columns([1, 3])
                    with rc1:
                        st.metric(f"{corner} Delta", f"{delta:+.1f}\u00b0")
                    with rc2:
                        st.markdown(f"{icon} **{status}**")
                        st.caption(advice)
                    st.caption(f"Inner: {t['inner']}\u00b0 | Mid: {t['middle']}\u00b0 | Outer: {t['outer']}\u00b0")
                st.markdown("---")
