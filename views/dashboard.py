import streamlit as st
from utils.gsheet_db import read_sheet, get_chassis_list, find_race_day


def _v(data, key, default=""):
    val = data.get(key, default)
    return val if val else default


def _vf(data, key, default=0.0):
    val = data.get(key, "")
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


_SESSIONS = ["p1", "p2", "heat", "feat"]
_CORNERS = ["LF", "RF", "LR", "RR"]
_SESSION_MAP = {
    "p1":   ("Practice #1",  "practice"),
    "p2":   ("Practice #2",  "practice2"),
    "heat": ("Heat Race",    "heat_race"),
    "feat": ("Feature",      "feature"),
}


def _show_race_day_detail(data):
    """Compact read-only detail view for a selected race day."""
    st.markdown(f"### {data.get('date', '')} \u2014 {data.get('track', '')}")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Chassis", _v(data, 'chassis', '\u2014'))
    c2.metric("Weather", _v(data, 'weather', '\u2014'))
    c3.metric("Track Condition", _v(data, 'track_condition', '\u2014'))
    c4.metric("Air Temp", _v(data, 'air_temp', '\u2014'))
    st.divider()

    r1, r2, r3 = st.columns(3)
    r1.metric("\U0001f3c1 Qualifying Position", _v(data, 'qual_position', '\u2014'))
    r2.metric("\U0001f3c1 Heat Finish", _v(data, 'heat_finish', '\u2014'))
    r3.metric("\U0001f3c6 Feature Finish", _v(data, 'feature_finish', '\u2014'))
    st.divider()

    for prefix, (label, notes_key) in _SESSION_MAP.items():
        _show_session_detail(prefix, label, notes_key, data)

    qual_notes = _v(data, 'qualifying')
    if qual_notes:
        with st.expander("\U0001f4dd Qualifying Notes", expanded=False):
            st.write(qual_notes)

    adj = _v(data, 'adjustments')
    gen = _v(data, 'notes')
    if adj or gen:
        with st.expander("\U0001f4dd Adjustments & General Notes", expanded=False):
            if adj:
                st.markdown("**Adjustments Made During Night**")
                st.write(adj)
            if gen:
                st.markdown("**General Notes**")
                st.write(gen)


def _show_session_detail(prefix, label, notes_key, data):
    """Show one session's tires, springs, temps & notes in an expander."""
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

    with st.expander(f"\U0001f3ce\ufe0f {label}", expanded=True):
        sz1, sz2, sz3, sz4 = st.columns(4)
        sz1.metric("\U0001f7e6 LF Tire", _v(data, f"{prefix}_tire_lf", "\u2014"))
        sz2.metric("\U0001f7e5 RF Tire", _v(data, f"{prefix}_tire_rf", "\u2014"))
        sz3.metric("\U0001f7e6 LR Tire", _v(data, f"{prefix}_tire_lr", "\u2014"))
        sz4.metric("\U0001f7e5 RR Tire", _v(data, f"{prefix}_tire_rr", "\u2014"))

        sg1, sg2 = st.columns(2)
        sg1.metric("Stagger Front", _v(data, f"{prefix}_stagger_f", "\u2014"))
        sg2.metric("Stagger Rear", _v(data, f"{prefix}_stagger_r", "\u2014"))

        st.markdown("**Front Corners**")
        f1, f2 = st.columns(2)
        with f1:
            st.caption("\U0001f7e6 LF")
            st.markdown(f"Pressure: **{_v(data, f'{prefix}_pres_lf', '\u2014')}** | "
                        f"Spring: **{_v(data, f'{prefix}_spring_lf', '\u2014')}** | "
                        f"Bump: **{_v(data, f'{prefix}_bump_lf', '\u2014')}**")
        with f2:
            st.caption("\U0001f7e5 RF")
            st.markdown(f"Pressure: **{_v(data, f'{prefix}_pres_rf', '\u2014')}** | "
                        f"Spring: **{_v(data, f'{prefix}_spring_rf', '\u2014')}** | "
                        f"Bump: **{_v(data, f'{prefix}_bump_rf', '\u2014')}**")

        st.markdown("**Rear Corners**")
        r1, r2 = st.columns(2)
        with r1:
            st.caption("\U0001f7e6 LR")
            st.markdown(f"Pressure: **{_v(data, f'{prefix}_pres_lr', '\u2014')}** | "
                        f"Spring: **{_v(data, f'{prefix}_spring_lr', '\u2014')}** | "
                        f"Bump: **{_v(data, f'{prefix}_bump_lr', '\u2014')}**")
        with r2:
            st.caption("\U0001f7e5 RR")
            st.markdown(f"Pressure: **{_v(data, f'{prefix}_pres_rr', '\u2014')}** | "
                        f"Spring: **{_v(data, f'{prefix}_spring_rr', '\u2014')}** | "
                        f"Bump: **{_v(data, f'{prefix}_bump_rr', '\u2014')}**")

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
            st.markdown("\U0001f321\ufe0f **Tire Temps**")
            for c in _CORNERS:
                t_in = _vf(data, f"{prefix}_temp_{c}_in")
                t_mid = _vf(data, f"{prefix}_temp_{c}_mid")
                t_out = _vf(data, f"{prefix}_temp_{c}_out")
                if t_in == 0 and t_mid == 0 and t_out == 0:
                    continue
                delta = t_in - t_out
                if delta > 10:
                    icon, status = "\u26a0\ufe0f", "Too much negative camber"
                elif delta < -10:
                    icon, status = "\u26a0\ufe0f", "Not enough negative camber"
                else:
                    icon, status = "\u2705", "Camber OK"
                tc1, tc2 = st.columns([1, 3])
                with tc1:
                    st.metric(f"{c} Delta", f"{delta:+.1f}\u00b0")
                with tc2:
                    st.markdown(f"{icon} **{status}**")
                    st.caption(f"Inner: {t_in}\u00b0 | Mid: {t_mid}\u00b0 | Outer: {t_out}\u00b0")

        session_notes = _v(data, notes_key)
        if session_notes:
            st.markdown("**Notes**")
            st.write(session_notes)


def render():
    st.header("\U0001f3e0 Dashboard")
    st.markdown("Welcome to the **Speed Lab Race Team** setup book and manager.")

    # Quick stats
    col1, col2, col3, col4 = st.columns(4)

    chassis_list = get_chassis_list()
    with col1:
        st.metric("Chassis", len(chassis_list))

    try:
        tires_df = read_sheet("tires")
        active_tires = len(tires_df[tires_df["status"] == "In Use"]) if not tires_df.empty and "status" in tires_df.columns else 0
        total_tires = len(tires_df) if not tires_df.empty else 0
    except Exception:
        active_tires = 0
        total_tires = 0
    with col2:
        st.metric("Active Tires", active_tires)
    with col3:
        st.metric("Total Tires", total_tires)

    try:
        maint_df = read_sheet("maintenance")
        due_count = len(maint_df[maint_df["status"] == "Due"]) if not maint_df.empty and "status" in maint_df.columns else 0
    except Exception:
        due_count = 0
    with col4:
        st.metric("Maintenance Due", due_count, delta_color="inverse")

    st.divider()

    # Recent race day logs with dropdown detail
    st.subheader("\U0001f4cb Recent Race Day Logs")
    try:
        race_df = read_sheet("race_day")
        if not race_df.empty:
            df_display = race_df.iloc[::-1].reset_index(drop=True)
            options = []
            for _, row in df_display.iterrows():
                date_val = row.get("date", "")
                track_val = row.get("track", "")
                chassis_val = row.get("chassis", "")
                feat_val = row.get("feature_finish", "")
                lbl = f"{date_val} | {track_val}"
                if chassis_val:
                    lbl += f" | {chassis_val}"
                if feat_val:
                    lbl += f" | Finished: {feat_val}"
                options.append(lbl)
            selected = st.selectbox("Select a race day to view details", options, key="dash_log_select")
            sel_idx = options.index(selected)
            sel_row = df_display.iloc[sel_idx]
            sel_date = sel_row.get("date", "")
            sel_track = sel_row.get("track", "")
            _, full_data = find_race_day(sel_date, sel_track)
            if full_data:
                _show_race_day_detail(full_data)
            else:
                st.warning("Could not load details for this race day.")
        else:
            st.info("No race day logs yet. Go to Race Day Log to add your first entry.")
    except Exception:
        st.info("No race day logs yet. Connect your Google Sheet to get started.")

    # Quick links
    st.divider()
    st.subheader("\u26a1 Quick Actions")
    qc1, qc2, qc3 = st.columns(3)
    with qc1:
        st.markdown("\U0001f527 **Setup Book** \u2014 View and edit chassis setups")
    with qc2:
        st.markdown("\U0001f6de **Tire Inventory** \u2014 Track tire numbers and wear")
    with qc3:
        st.markdown("\U0001f6e0\ufe0f **Maintenance** \u2014 Check upcoming tasks")
