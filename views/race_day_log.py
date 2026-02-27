import streamlit as st
from utils.gsheet_db import (
    read_sheet, get_chassis_list, timestamp_now,
    find_race_day, upsert_race_day, ensure_race_day_headers, delete_row,
)
from utils.auth import can_edit, can_delete

# -- All column headers the race_day sheet needs --
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

_SESSION_MAP = {
    "p1":   ("Practice #1", "practice"),
    "p2":   ("Practice #2", "practice2"),
    "heat": ("Heat Race",   "heat_race"),
    "feat": ("Feature",     "feature"),
}

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


# ── Read-only detail view for a selected race day ──
def _show_detail(data):
    """Display all saved info for one race day in a clean read-only layout."""
    # Header card
    st.markdown(f"### {data.get('date', '')}  —  {data.get('track', '')}")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Chassis", _v(data, 'chassis', '—'))
    c2.metric("Weather", _v(data, 'weather', '—'))
    c3.metric("Track Condition", _v(data, 'track_condition', '—'))
    c4.metric("Air Temp", _v(data, 'air_temp', '—'))
    st.divider()

    # Results card
    r1, r2, r3 = st.columns(3)
    r1.metric("🏁 Qualifying Position", _v(data, 'qual_position', '—'))
    r2.metric("🏁 Heat Finish", _v(data, 'heat_finish', '—'))
    r3.metric("🏆 Feature Finish", _v(data, 'feature_finish', '—'))
    st.divider()

    # Session detail blocks
    for prefix, (label, notes_key) in _SESSION_MAP.items():
        _show_session_detail(prefix, label, notes_key, data)

    # Qualifying notes (no tire data)
    qual_notes = _v(data, 'qualifying')
    if qual_notes:
        with st.expander("📝 Qualifying Notes", expanded=False):
            st.write(qual_notes)

    # Adjustments & general notes
    adj = _v(data, 'adjustments')
    gen = _v(data, 'notes')
    if adj or gen:
        with st.expander("📝 Adjustments & General Notes", expanded=False):
            if adj:
                st.markdown("**Adjustments Made During Night**")
                st.write(adj)
            if gen:
                st.markdown("**General Notes**")
                st.write(gen)


def _show_session_detail(prefix, label, notes_key, data):
    """Show one session's tires, springs, temps & notes in an expander."""
    # Check if session has any data at all
    has_data = False
    for field in ["tire", "pres", "spring", "bump"]:
        for c in ["lf", "rf", "lr", "rr"]:
            if _v(data, f"{prefix}_{field}_{c}"):
                has_data = True
                break
        if has_data:
            break
    if not has_data:
        if _v(data, notes_key):
            has_data = True
    if not has_data:
        for c in _CORNERS:
            for z in ["in", "mid", "out"]:
                if _v(data, f"{prefix}_temp_{c}_{z}"):
                    has_data = True
                    break
            if has_data:
                break
    if not has_data:
        return

    with st.expander(f"🏎️ {label}", expanded=True):
        # Tire sizes row
        sz1, sz2, sz3, sz4 = st.columns(4)
        sz1.metric("🟦 LF Tire", _v(data, f"{prefix}_tire_lf", "—"))
        sz2.metric("🟥 RF Tire", _v(data, f"{prefix}_tire_rf", "—"))
        sz3.metric("🟦 LR Tire", _v(data, f"{prefix}_tire_lr", "—"))
        sz4.metric("🟥 RR Tire", _v(data, f"{prefix}_tire_rr", "—"))

        # Stagger
        sg1, sg2 = st.columns(2)
        sg1.metric("Stagger Front", _v(data, f"{prefix}_stagger_f", "—"))
        sg2.metric("Stagger Rear", _v(data, f"{prefix}_stagger_r", "—"))

        # Pressure / Spring / Bump  (two rows: front then rear)
        st.markdown("**Front Corners**")
        f1, f2 = st.columns(2)
        with f1:
            st.caption("🟦 LF")
            st.markdown(f"Pressure: **{_v(data, f'{prefix}_pres_lf', '—')}** | "
                        f"Spring: **{_v(data, f'{prefix}_spring_lf', '—')}** | "
                        f"Bump: **{_v(data, f'{prefix}_bump_lf', '—')}**")
        with f2:
            st.caption("🟥 RF")
            st.markdown(f"Pressure: **{_v(data, f'{prefix}_pres_rf', '—')}** | "
                        f"Spring: **{_v(data, f'{prefix}_spring_rf', '—')}** | "
                        f"Bump: **{_v(data, f'{prefix}_bump_rf', '—')}**")

        st.markdown("**Rear Corners**")
        r1, r2 = st.columns(2)
        with r1:
            st.caption("🟦 LR")
            st.markdown(f"Pressure: **{_v(data, f'{prefix}_pres_lr', '—')}** | "
                        f"Spring: **{_v(data, f'{prefix}_spring_lr', '—')}** | "
                        f"Bump: **{_v(data, f'{prefix}_bump_lr', '—')}**")
        with r2:
            st.caption("🟥 RR")
            st.markdown(f"Pressure: **{_v(data, f'{prefix}_pres_rr', '—')}** | "
                        f"Spring: **{_v(data, f'{prefix}_spring_rr', '—')}** | "
                        f"Bump: **{_v(data, f'{prefix}_bump_rr', '—')}**")

        # Tire temps
        has_temps = False
        for c in _CORNERS:
            for z in ["in", "mid", "out"]:
                val = _v(data, f"{prefix}_temp_{c}_{z}")
                if val and val not in ("0", "0.0", "0.00"):
                    has_temps = True
                    break
            if has_temps:
                break
        if has_temps:
            st.markdown("🌡️ **Tire Temps**")
            for c in _CORNERS:
                t_in  = _vf(data, f"{prefix}_temp_{c}_in")
                t_mid = _vf(data, f"{prefix}_temp_{c}_mid")
                t_out = _vf(data, f"{prefix}_temp_{c}_out")
                if t_in == 0 and t_mid == 0 and t_out == 0:
                    continue
                delta = t_in - t_out
                if delta > 10:
                    icon, status = "⚠️", "Too much negative camber"
                elif delta < -10:
                    icon, status = "⚠️", "Not enough negative camber"
                else:
                    icon, status = "✅", "Camber OK"
                tc1, tc2 = st.columns([1, 3])
                with tc1:
                    st.metric(f"{c} Delta", f"{delta:+.1f}°")
                with tc2:
                    st.markdown(f"{icon} **{status}**")
                    st.caption(f"Inner: {t_in}° | Mid: {t_mid}° | Outer: {t_out}°")

        # Session notes
        session_notes = _v(data, notes_key)
        if session_notes:
            st.markdown("**Notes**")
            st.write(session_notes)


# -- Editable form helpers (used in Race Day Entry tab) --
def tire_block(prefix, label, data):
    """Tire size, stagger, air pressure, spring/bump inside a form."""
    st.markdown(f"**{label}**")
    sz1, sz2, sz3, sz4 = st.columns(4)
    with sz1:
        st.markdown("**🟦 LF**")
        lf_sz = st.text_input("Tire Size", value=_v(data, f"{prefix}_tire_lf"), key=f"{prefix}_tire_lf")
    with sz2:
        st.markdown("**🟥 RF**")
        rf_sz = st.text_input("Tire Size", value=_v(data, f"{prefix}_tire_rf"), key=f"{prefix}_tire_rf")
    with sz3:
        st.markdown("**🟦 LR**")
        lr_sz = st.text_input("Tire Size", value=_v(data, f"{prefix}_tire_lr"), key=f"{prefix}_tire_lr")
    with sz4:
        st.markdown("**🟥 RR**")
        rr_sz = st.text_input("Tire Size", value=_v(data, f"{prefix}_tire_rr"), key=f"{prefix}_tire_rr")
    sg1, sg2 = st.columns(2)
    with sg1:
        stg_f = st.text_input("Stagger Front (RF − LF)", value=_v(data, f"{prefix}_stagger_f"), key=f"{prefix}_stagger_f")
    with sg2:
        stg_r = st.text_input("Stagger Rear (RR − LR)", value=_v(data, f"{prefix}_stagger_r"), key=f"{prefix}_stagger_r")
    st.markdown("**Front Corners**")
    sf1, sf2 = st.columns(2)
    with sf1:
        st.markdown("*🟦 LF*")
        lf_pr = st.text_input("Air Pressure", value=_v(data, f"{prefix}_pres_lf"), key=f"{prefix}_pres_lf")
        lf_sp = st.text_input("Spring Rate (lbs)", value=_v(data, f"{prefix}_spring_lf"), key=f"{prefix}_spring_lf")
        lf_bu = st.text_input("Bump Spring (lbs)", value=_v(data, f"{prefix}_bump_lf"), key=f"{prefix}_bump_lf")
    with sf2:
        st.markdown("*🟥 RF*")
        rf_pr = st.text_input("Air Pressure", value=_v(data, f"{prefix}_pres_rf"), key=f"{prefix}_pres_rf")
        rf_sp = st.text_input("Spring Rate (lbs)", value=_v(data, f"{prefix}_spring_rf"), key=f"{prefix}_spring_rf")
        rf_bu = st.text_input("Bump Spring (lbs)", value=_v(data, f"{prefix}_bump_rf"), key=f"{prefix}_bump_rf")
    st.markdown("**Rear Corners**")
    sr1, sr2 = st.columns(2)
    with sr1:
        st.markdown("*🟦 LR*")
        lr_pr = st.text_input("Air Pressure", value=_v(data, f"{prefix}_pres_lr"), key=f"{prefix}_pres_lr")
        lr_sp = st.text_input("Spring Rate (lbs)", value=_v(data, f"{prefix}_spring_lr"), key=f"{prefix}_spring_lr")
        lr_bu = st.text_input("Bump Spring (lbs)", value=_v(data, f"{prefix}_bump_lr"), key=f"{prefix}_bump_lr")
    with sr2:
        st.markdown("*🟥 RR*")
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
        with st.expander(f"\U0001f321 {corner} Temps", expanded=False):
            tc1, tc2, tc3 = st.columns(3)
            with tc1:
                t_in = st.number_input(f"{corner} Inner", min_value=0.0, max_value=500.0,
                    value=_vf(data, f"{prefix}_temp_{corner}_in"), step=1.0, key=f"{prefix}_temp_{corner}_in")
            with tc2:
                t_mid = st.number_input(f"{corner} Middle", min_value=0.0, max_value=500.0,
                    value=_vf(data, f"{prefix}_temp_{corner}_mid"), step=1.0, key=f"{prefix}_temp_{corner}_mid")
            with tc3:
                t_out = st.number_input(f"{corner} Outer", min_value=0.0, max_value=500.0,
                    value=_vf(data, f"{prefix}_temp_{corner}_out"), step=1.0, key=f"{prefix}_temp_{corner}_out")
            temps[corner] = {"inner": t_in, "middle": t_mid, "outer": t_out}
            result[f"{prefix}_temp_{corner}_in"]  = t_in
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
        notes_val = st.text_area(f"{session_label} Notes",
            value=_v(data, notes_key), key=f"{prefix}_notes_input")
        temp_data = tire_temp_block(prefix, session_label, data)
        if st.form_submit_button(f"\U0001f4be Save {session_label}", type="primary"):
            save = {notes_key: notes_val, "created": timestamp_now()}
            save.update(setup_data)
            save.update(temp_data)
            upsert_race_day(date_str, track, save)
            st.success(f"{session_label} saved!")
            st.rerun()



# ========================
# Main render
# ========================
def render():
    st.header("\U0001f4cb Race Day Log")
    chassis_list = get_chassis_list()
    ensure_race_day_headers(ALL_HEADERS)

    tab_labels = ["View Logs"]
    if can_edit():
        tab_labels.append("Race Day Entry")
    tab_labels.append("Tire Temp")
    tabs = st.tabs(tab_labels)
    tab_idx = 0

    # ========================
    # TAB 1 -- View Logs (always visible)
    # ========================
    with tabs[tab_idx]:
        df = read_sheet("race_day")
        if df.empty:
            st.info("No race day logs yet.")
        else:
            # Build summary list (newest first)
            df_display = df.iloc[::-1].reset_index(drop=True)
            options = []
            for _, row in df_display.iterrows():
                date_val = row.get("date", "")
                track_val = row.get("track", "")
                chassis_val = row.get("chassis", "")
                feat_val = row.get("feature_finish", "")
                label = f"{date_val}  |  {track_val}"
                if chassis_val:
                    label += f"  |  {chassis_val}"
                if feat_val:
                    label += f"  |  Finished: {feat_val}"
                options.append(label)

            selected = st.selectbox("Select a race day to view details", options, key="view_log_select")
            sel_idx = options.index(selected)
            sel_row = df_display.iloc[sel_idx]
            sel_date = sel_row.get("date", "")
            sel_track = sel_row.get("track", "")

            # Fetch full row data via find_race_day for complete dict
            _, full_data = find_race_day(sel_date, sel_track)
            if full_data:
                _show_detail(full_data)
            else:
                st.warning("Could not load details for this race day.")

            # Delete race day (admin only)
            if can_delete():
                st.divider()
                st.markdown("**Danger Zone**")
                if st.button("\U0001f5d1\ufe0f Delete This Race Day", type="secondary", key="delete_race_day"):
                    st.session_state["confirm_delete"] = True
                if st.session_state.get("confirm_delete"):
                    st.warning(f"Are you sure you want to delete {sel_date} \u2014 {sel_track}? This cannot be undone.")
                    c_yes, c_no = st.columns(2)
                    with c_yes:
                        if st.button("\u2705 Yes, Delete", type="primary", key="confirm_del_yes"):
                            row_idx, _ = find_race_day(sel_date, sel_track)
                            if row_idx is not None:
                                delete_row("race_day", row_idx)
                            st.session_state.pop("confirm_delete", None)
                            st.success("Race day deleted!")
                            st.rerun()
                    with c_no:
                        if st.button("\u274c Cancel", key="confirm_del_no"):
                            st.session_state.pop("confirm_delete", None)
                            st.rerun()

    # ========================
    # TAB 2 -- Race Day Entry (only if can_edit)
    # ========================
    if can_edit():
        tab_idx += 1
        with tabs[tab_idx]:
            st.subheader("Select Race Day")
            hc1, hc2 = st.columns(2)
            with hc1:
                DEFAULT_TRACKS = ["Sauble Speedway", "Flamboro Speedway", "Delaware Speedway", "Sunset Speedway", "Peterborough Speedway", "Jukasa Motor Speedway"]
                # Build track list from previous race days + defaults
                try:
                    all_races = read_sheet("race_day")
                    saved_tracks = all_races["track"].unique().tolist() if not all_races.empty and "track" in all_races.columns else []
                except Exception:
                    saved_tracks = []
                track_options = sorted(set(DEFAULT_TRACKS + saved_tracks))
                track = st.selectbox("Track", track_options + ["Other (type below)"], key="rd_track")
                if track == "Other (type below)":
                    track = st.text_input("Enter track name", key="rd_track_custom")
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
                    weather = st.text_input("Weather (temp, humidity, wind)",
                        value=_v(data, "weather"), key="rd_weather")
                with ic2:
                    track_condition = st.selectbox("Track Condition",
                        ["Dry", "Damp", "Wet", "Dusty", "Tacky"],
                        index=["Dry", "Damp", "Wet", "Dusty", "Tacky"].index(_v(data, "track_condition", "Dry")),
                        key="rd_condition")
                with ic3:
                    air_temp = st.text_input("Air Temp", value=_v(data, "air_temp"), key="rd_air_temp")
                if st.form_submit_button("\U0001f4be Save Race Day Info", type="primary"):
                    save = {
                        "chassis": chassis, "weather": weather,
                        "track_condition": track_condition, "air_temp": air_temp,
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
                qual_notes = st.text_area("Qualifying Notes",
                    value=_v(data, "qualifying"), key="qual_notes_input")
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
                    qual_pos = st.text_input("Qualifying Position",
                        value=_v(data, "qual_position"), key="rd_qual_pos")
                with rc2:
                    heat_fin = st.text_input("Heat Finish",
                        value=_v(data, "heat_finish"), key="rd_heat_fin")
                with rc3:
                    feat_fin = st.text_input("Feature Finish",
                        value=_v(data, "feature_finish"), key="rd_feat_fin")
                adjustments = st.text_area("Adjustments Made During Night",
                    value=_v(data, "adjustments"), key="rd_adjustments")
                notes = st.text_area("General Notes",
                    value=_v(data, "notes"), key="rd_notes")
                if st.form_submit_button("\U0001f4be Save Results & Notes", type="primary"):
                    save = {
                        "qual_position": qual_pos, "heat_finish": heat_fin,
                        "feature_finish": feat_fin, "adjustments": adjustments,
                        "notes": notes, "created": timestamp_now(),
                    }
                    upsert_race_day(date_str, track, save)
                    st.success("Results & notes saved!")
                    st.rerun()

    # ========================
    # TAB 3 -- Tire Temp (always visible)
    # ========================
    tab_idx += 1
    with tabs[tab_idx]:
        st.subheader("Tire Temperature Analysis")
        st.caption("Enter tire temps (Inner, Middle, Outer) for each corner. The app will analyze camber based on the temperature spread.")
        corners = ["LF", "RF", "LR", "RR"]
        temps = {}
        for corner in corners:
            with st.expander(f"\U0001f321 {corner} Temps", expanded=False):
                tc1, tc2, tc3 = st.columns(3)
                with tc1:
                    t_in = st.number_input(f"{corner} Inner", min_value=0.0, max_value=500.0,
                        value=0.0, step=1.0, key=f"rdl_{corner}_in")
                with tc2:
                    t_mid = st.number_input(f"{corner} Middle", min_value=0.0, max_value=500.0,
                        value=0.0, step=1.0, key=f"rdl_{corner}_mid")
                with tc3:
                    t_out = st.number_input(f"{corner} Outer", min_value=0.0, max_value=500.0,
                        value=0.0, step=1.0, key=f"rdl_{corner}_out")
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
