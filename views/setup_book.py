import streamlit as st
from utils.gsheet_db import (
    read_sheet, append_row, delete_row, timestamp_now,
    get_chassis_list, get_worksheet, update_row, _col_letter,
)
from utils.auth import can_edit, can_delete

CORNERS = ["LF", "RF", "LR", "RR"]

# -- All column headers the setups sheet needs --
ALL_HEADERS = [
    "chassis", "setup_name", "date",
    # Springs
    "spring_LF", "spring_RF", "spring_LR", "spring_RR",
    # Bump Springs
    "bump_spring_LF", "bump_spring_RF", "bump_spring_LR", "bump_spring_RR",
    # Shocks
    "shock_comp_LF", "shock_comp_RF", "shock_comp_LR", "shock_comp_RR",
    "shock_reb_LF", "shock_reb_RF", "shock_reb_LR", "shock_reb_RR",
    # Ride Heights
    "ride_height_LF", "ride_height_RF", "ride_height_LR", "ride_height_RR",
    # Alignment
    "camber_LF", "camber_RF", "camber_LR", "camber_RR",
    "caster_LF", "caster_RF",
    "toe",
    # Scale Weights
    "weight_LF", "weight_RF", "weight_LR", "weight_RR",
    "weight_left", "weight_rear", "weight_cross",
    # Chassis / Drivetrain
    "gear_ratio", "sway_bar", "track_bar",
    "panhard", "trailing_arm",
    "tire_pres_LF", "tire_pres_RF", "tire_pres_LR", "tire_pres_RR",
    "stagger",
    "notes",
]


def _ensure_headers():
    ws = get_worksheet("setups")
    existing = ws.row_values(1)
    trimmed = [h for h in existing if h.strip()]
    missing = [h for h in ALL_HEADERS if h not in trimmed]
    if missing:
        new_headers = trimmed + missing
        end_col = _col_letter(len(new_headers))
        ws.update(f"A1:{end_col}1", [new_headers])


def _v(data, key, default=""):
    val = data.get(key, default)
    return val if val else default


def _vf(data, key, default=0.0):
    val = data.get(key, "")
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _find_setup(name):
    ws = get_worksheet("setups")
    all_values = ws.get_all_values()
    if not all_values or len(all_values) < 2:
        return None, None
    headers = all_values[0]
    name_col = None
    for i, h in enumerate(headers):
        if h.strip().lower() == "setup_name":
            name_col = i
            break
    if name_col is None:
        return None, None
    for row_num, row in enumerate(all_values[1:], start=2):
        if len(row) > name_col and row[name_col].strip() == name:
            row_dict = {}
            for i, h in enumerate(headers):
                if h.strip() and i < len(row):
                    row_dict[h.strip()] = row[i]
            return row_num, row_dict
    return None, None


def _upsert_setup(name, data):
    row_index, existing = _find_setup(name)
    if row_index is not None:
        merged = {}
        if existing:
            merged.update(existing)
        merged.update(data)
        merged["setup_name"] = name
        update_row("setups", row_index, merged)
        return row_index
    else:
        data["setup_name"] = name
        append_row("setups", data)
        new_idx, _ = _find_setup(name)
        return new_idx


def _show_detail(data):
    st.markdown(f"### {data.get('setup_name', '')}")
    c1, c2, c3 = st.columns(3)
    c1.metric("Chassis", _v(data, 'chassis', '\u2014'))
    c2.metric("Date", _v(data, 'date', '\u2014'))
    c3.metric("Gear Ratio", _v(data, 'gear_ratio', '\u2014'))
    st.divider()

    # Springs
    sp_any = any(_v(data, f'spring_{c}') for c in CORNERS)
    bump_any = any(_v(data, f'bump_spring_{c}') for c in CORNERS)
    if sp_any or bump_any:
        with st.expander("\U0001f9f2 Springs", expanded=True):
            if sp_any:
                st.markdown("**Main Springs (lbs)**")
                s1, s2, s3, s4 = st.columns(4)
                s1.metric("LF", _v(data, 'spring_LF', '\u2014'))
                s2.metric("RF", _v(data, 'spring_RF', '\u2014'))
                s3.metric("LR", _v(data, 'spring_LR', '\u2014'))
                s4.metric("RR", _v(data, 'spring_RR', '\u2014'))
            if bump_any:
                st.markdown("**Bump Springs (lbs)**")
                b1, b2, b3, b4 = st.columns(4)
                b1.metric("LF", _v(data, 'bump_spring_LF', '\u2014'))
                b2.metric("RF", _v(data, 'bump_spring_RF', '\u2014'))
                b3.metric("LR", _v(data, 'bump_spring_LR', '\u2014'))
                b4.metric("RR", _v(data, 'bump_spring_RR', '\u2014'))

    # Shocks
    comp_any = any(_v(data, f'shock_comp_{c}') for c in CORNERS)
    reb_any = any(_v(data, f'shock_reb_{c}') for c in CORNERS)
    if comp_any or reb_any:
        with st.expander("\U0001f50c Shocks", expanded=True):
            if comp_any:
                st.markdown("**Compression**")
                sc1, sc2, sc3, sc4 = st.columns(4)
                sc1.metric("LF", _v(data, 'shock_comp_LF', '\u2014'))
                sc2.metric("RF", _v(data, 'shock_comp_RF', '\u2014'))
                sc3.metric("LR", _v(data, 'shock_comp_LR', '\u2014'))
                sc4.metric("RR", _v(data, 'shock_comp_RR', '\u2014'))
            if reb_any:
                st.markdown("**Rebound**")
                sr1, sr2, sr3, sr4 = st.columns(4)
                sr1.metric("LF", _v(data, 'shock_reb_LF', '\u2014'))
                sr2.metric("RF", _v(data, 'shock_reb_RF', '\u2014'))
                sr3.metric("LR", _v(data, 'shock_reb_LR', '\u2014'))
                sr4.metric("RR", _v(data, 'shock_reb_RR', '\u2014'))

    # Ride Heights
    rh_any = any(_v(data, f'ride_height_{c}') for c in CORNERS)
    if rh_any:
        with st.expander("\U0001f4cf Ride Heights", expanded=True):
            r1, r2, r3, r4 = st.columns(4)
            r1.metric("LF", _v(data, 'ride_height_LF', '\u2014'))
            r2.metric("RF", _v(data, 'ride_height_RF', '\u2014'))
            r3.metric("LR", _v(data, 'ride_height_LR', '\u2014'))
            r4.metric("RR", _v(data, 'ride_height_RR', '\u2014'))

    # Alignment
    geo_any = any(_v(data, k) for k in ['camber_LF','camber_RF','camber_LR','camber_RR','caster_LF','caster_RF','toe'])
    if geo_any:
        with st.expander("\U0001f4d0 Alignment", expanded=True):
            st.markdown("**Camber**")
            g1, g2, g3, g4 = st.columns(4)
            g1.metric("LF", _v(data, 'camber_LF', '\u2014'))
            g2.metric("RF", _v(data, 'camber_RF', '\u2014'))
            g3.metric("LR", _v(data, 'camber_LR', '\u2014'))
            g4.metric("RR", _v(data, 'camber_RR', '\u2014'))
            st.markdown("**Caster**")
            ca1, ca2 = st.columns(2)
            ca1.metric("LF Caster", _v(data, 'caster_LF', '\u2014'))
            ca2.metric("RF Caster", _v(data, 'caster_RF', '\u2014'))
            st.metric("Toe (total)", _v(data, 'toe', '\u2014'))

    # Scale Weights
    wlf = _vf(data, 'weight_LF')
    wrf = _vf(data, 'weight_RF')
    wlr = _vf(data, 'weight_LR')
    wrr = _vf(data, 'weight_RR')
    total = wlf + wrf + wlr + wrr
    if total > 0:
        with st.expander("\u2696\ufe0f Scale Weights", expanded=True):
            w1, w2, w3, w4 = st.columns(4)
            w1.metric("LF", f"{wlf:.0f} lbs")
            w2.metric("RF", f"{wrf:.0f} lbs")
            w3.metric("LR", f"{wlr:.0f} lbs")
            w4.metric("RR", f"{wrr:.0f} lbs")
            cross = wrf + wlr
            left = wlf + wlr
            cross_pct = (cross / total * 100) if total else 0
            left_pct = (left / total * 100) if total else 0
            m1, m2, m3 = st.columns(3)
            m1.metric("Total Weight", f"{total:.0f} lbs")
            m2.metric("Cross Weight", f"{cross_pct:.1f}%")
            m3.metric("Left Side", f"{left_pct:.1f}%")

    # Chassis / Drivetrain
    dt_keys = ['gear_ratio','sway_bar','track_bar','panhard','trailing_arm','stagger']
    dt_any = any(_v(data, k) for k in dt_keys)
    if dt_any:
        with st.expander("\U0001f3ce\ufe0f Chassis & Drivetrain", expanded=True):
            d1, d2, d3 = st.columns(3)
            d1.metric("Sway Bar", _v(data, 'sway_bar', '\u2014'))
            d2.metric("Track Bar", _v(data, 'track_bar', '\u2014'))
            d3.metric("Panhard", _v(data, 'panhard', '\u2014'))
            e1, e2 = st.columns(2)
            e1.metric("Trailing Arm", _v(data, 'trailing_arm', '\u2014'))
            e2.metric("Stagger", _v(data, 'stagger', '\u2014'))

    # Tire Pressures
    tp_any = any(_v(data, f'tire_pres_{c}') for c in CORNERS)
    if tp_any:
        with st.expander("\U0001f3ce\ufe0f Tire Pressures", expanded=True):
            tp1, tp2, tp3, tp4 = st.columns(4)
            tp1.metric("LF", _v(data, 'tire_pres_LF', '\u2014'))
            tp2.metric("RF", _v(data, 'tire_pres_RF', '\u2014'))
            tp3.metric("LR", _v(data, 'tire_pres_LR', '\u2014'))
            tp4.metric("RR", _v(data, 'tire_pres_RR', '\u2014'))

    # Notes
    notes = _v(data, 'notes')
    if notes:
        with st.expander("\U0001f4dd Notes", expanded=False):
            st.write(notes)


def _auto_calc_weights(wlf_s, wrf_s, wlr_s, wrr_s):
    """Return (total, cross_pct, left_pct) from corner weight strings."""
    try:
        wlf = float(wlf_s) if wlf_s else 0.0
        wrf = float(wrf_s) if wrf_s else 0.0
        wlr = float(wlr_s) if wlr_s else 0.0
        wrr = float(wrr_s) if wrr_s else 0.0
    except (ValueError, TypeError):
        return "", "", ""
    total = wlf + wrf + wlr + wrr
    if total == 0:
        return "", "", ""
    cross_pct = (wrf + wlr) / total * 100
    left_pct = (wlf + wlr) / total * 100
    return f"{total:.0f}", f"{cross_pct:.1f}", f"{left_pct:.1f}"


def _setup_form(data, chassis_list, form_key):
    """Reusable form for add/edit with collapsible sections and Quick Entry mode."""
    # Quick Entry toggle (outside form so it controls what shows)
    quick_mode = st.toggle("\u26a1 Quick Entry (essentials only)", value=False, key=f"{form_key}_quick")
    if quick_mode:
        st.caption("Showing only: Springs, Shocks, Ride Heights, Tire Pressures, Sway Bar, Track Bar")

    with st.form(form_key, clear_on_submit=False):
        st.subheader("Basic Info")
        bc1, bc2 = st.columns(2)
        with bc1:
            chassis = st.selectbox("Chassis", chassis_list,
                index=chassis_list.index(_v(data,'chassis',chassis_list[0])) if _v(data,'chassis') in chassis_list else 0,
                key=f"{form_key}_chassis")
            setup_name = st.text_input("Setup Name *", value=_v(data, 'setup_name'), key=f"{form_key}_name")
        with bc2:
            from datetime import datetime, date as dt_date
            default_date_str = _v(data, 'date', '')
            try:
                default_date = datetime.strptime(default_date_str[:10], "%Y-%m-%d").date() if default_date_str else dt_date.today()
            except (ValueError, TypeError):
                default_date = dt_date.today()
            setup_date = st.date_input("Date", value=default_date, key=f"{form_key}_date")

        # ── Springs ──
        spr = {}
        with st.expander("\U0001f9f2 Springs", expanded=False):
            st.markdown("**Main Springs (lbs)**")
            sp1, sp2, sp3, sp4 = st.columns(4)
            with sp1:
                spr['spring_LF'] = st.text_input("LF Spring (lbs)", value=_v(data, 'spring_LF'), key=f"{form_key}_slf")
            with sp2:
                spr['spring_RF'] = st.text_input("RF Spring (lbs)", value=_v(data, 'spring_RF'), key=f"{form_key}_srf")
            with sp3:
                spr['spring_LR'] = st.text_input("LR Spring (lbs)", value=_v(data, 'spring_LR'), key=f"{form_key}_slr")
            with sp4:
                spr['spring_RR'] = st.text_input("RR Spring (lbs)", value=_v(data, 'spring_RR'), key=f"{form_key}_srr")

            st.markdown("**Bump Springs (lbs)**")
            bp1, bp2, bp3, bp4 = st.columns(4)
            with bp1:
                spr['bump_spring_LF'] = st.text_input("LF Bump (lbs)", value=_v(data, 'bump_spring_LF'), key=f"{form_key}_blf")
            with bp2:
                spr['bump_spring_RF'] = st.text_input("RF Bump (lbs)", value=_v(data, 'bump_spring_RF'), key=f"{form_key}_brf")
            with bp3:
                spr['bump_spring_LR'] = st.text_input("LR Bump (lbs)", value=_v(data, 'bump_spring_LR'), key=f"{form_key}_blr")
            with bp4:
                spr['bump_spring_RR'] = st.text_input("RR Bump (lbs)", value=_v(data, 'bump_spring_RR'), key=f"{form_key}_brr")

        # ── Shocks ──
        comp = {}
        reb = {}
        with st.expander("\U0001f50c Shocks", expanded=False):
            st.markdown("**Compression**")
            sc1, sc2, sc3, sc4 = st.columns(4)
            with sc1:
                comp['shock_comp_LF'] = st.text_input("Comp LF", value=_v(data, 'shock_comp_LF'), key=f"{form_key}_sclf")
            with sc2:
                comp['shock_comp_RF'] = st.text_input("Comp RF", value=_v(data, 'shock_comp_RF'), key=f"{form_key}_scrf")
            with sc3:
                comp['shock_comp_LR'] = st.text_input("Comp LR", value=_v(data, 'shock_comp_LR'), key=f"{form_key}_sclr")
            with sc4:
                comp['shock_comp_RR'] = st.text_input("Comp RR", value=_v(data, 'shock_comp_RR'), key=f"{form_key}_scrr")
            st.markdown("**Rebound**")
            sr1, sr2, sr3, sr4 = st.columns(4)
            with sr1:
                reb['shock_reb_LF'] = st.text_input("Reb LF", value=_v(data, 'shock_reb_LF'), key=f"{form_key}_srlf")
            with sr2:
                reb['shock_reb_RF'] = st.text_input("Reb RF", value=_v(data, 'shock_reb_RF'), key=f"{form_key}_srrf")
            with sr3:
                reb['shock_reb_LR'] = st.text_input("Reb LR", value=_v(data, 'shock_reb_LR'), key=f"{form_key}_srlr")
            with sr4:
                reb['shock_reb_RR'] = st.text_input("Reb RR", value=_v(data, 'shock_reb_RR'), key=f"{form_key}_srrr")

        # ── Ride Heights ──
        rh = {}
        with st.expander("\U0001f4cf Ride Heights (in)", expanded=False):
            rh1, rh2, rh3, rh4 = st.columns(4)
            with rh1:
                rh['ride_height_LF'] = st.text_input("LF Height (in)", value=_v(data, 'ride_height_LF'), key=f"{form_key}_rhlf")
            with rh2:
                rh['ride_height_RF'] = st.text_input("RF Height (in)", value=_v(data, 'ride_height_RF'), key=f"{form_key}_rhrf")
            with rh3:
                rh['ride_height_LR'] = st.text_input("LR Height (in)", value=_v(data, 'ride_height_LR'), key=f"{form_key}_rhlr")
            with rh4:
                rh['ride_height_RR'] = st.text_input("RR Height (in)", value=_v(data, 'ride_height_RR'), key=f"{form_key}_rhrr")

        # ── Alignment (skip in Quick Entry) ──
        align = {}
        toe = _v(data, 'toe')
        if not quick_mode:
            with st.expander("\U0001f4d0 Alignment", expanded=False):
                st.markdown("**Camber (\u00b0)**")
                ac1, ac2, ac3, ac4 = st.columns(4)
                with ac1:
                    align['camber_LF'] = st.text_input("LF Camber (\u00b0)", value=_v(data, 'camber_LF'), key=f"{form_key}_clf")
                with ac2:
                    align['camber_RF'] = st.text_input("RF Camber (\u00b0)", value=_v(data, 'camber_RF'), key=f"{form_key}_crf")
                with ac3:
                    align['camber_LR'] = st.text_input("LR Camber (\u00b0)", value=_v(data, 'camber_LR'), key=f"{form_key}_clr")
                with ac4:
                    align['camber_RR'] = st.text_input("RR Camber (\u00b0)", value=_v(data, 'camber_RR'), key=f"{form_key}_crr")
                st.markdown("**Caster (\u00b0)**")
                cas1, cas2 = st.columns(2)
                with cas1:
                    align['caster_LF'] = st.text_input("LF Caster (\u00b0)", value=_v(data, 'caster_LF'), key=f"{form_key}_caslf")
                with cas2:
                    align['caster_RF'] = st.text_input("RF Caster (\u00b0)", value=_v(data, 'caster_RF'), key=f"{form_key}_casrf")
                toe = st.text_input("Toe \u2014 total (in)", value=_v(data, 'toe'), key=f"{form_key}_toe")

        # ── Scale Weights (auto-calc) ──
        wt = {}
        if not quick_mode:
            with st.expander("\u2696\ufe0f Scale Weights", expanded=False):
                st.caption("Enter the four corner weights. Total, Cross %, and Left % are calculated automatically.")
                wc1, wc2, wc3, wc4 = st.columns(4)
                with wc1:
                    wt['weight_LF'] = st.text_input("LF Weight (lbs)", value=_v(data, 'weight_LF'), key=f"{form_key}_wlf")
                with wc2:
                    wt['weight_RF'] = st.text_input("RF Weight (lbs)", value=_v(data, 'weight_RF'), key=f"{form_key}_wrf")
                with wc3:
                    wt['weight_LR'] = st.text_input("LR Weight (lbs)", value=_v(data, 'weight_LR'), key=f"{form_key}_wlr")
                with wc4:
                    wt['weight_RR'] = st.text_input("RR Weight (lbs)", value=_v(data, 'weight_RR'), key=f"{form_key}_wrr")
                # Auto-calculated read-only display
                total_s, cross_s, left_s = _auto_calc_weights(
                    wt.get('weight_LF', ''), wt.get('weight_RF', ''),
                    wt.get('weight_LR', ''), wt.get('weight_RR', ''))
                if total_s:
                    ac1, ac2, ac3 = st.columns(3)
                    ac1.metric("Total Weight", f"{total_s} lbs")
                    ac2.metric("Cross Weight", f"{cross_s}%")
                    ac3.metric("Left Side", f"{left_s}%")
                else:
                    st.info("Enter corner weights above to see totals.")

        # ── Chassis & Drivetrain ──
        gear_ratio = _v(data, 'gear_ratio')
        panhard = _v(data, 'panhard')
        trailing_arm = _v(data, 'trailing_arm')
        stagger = _v(data, 'stagger')
        with st.expander("\U0001f3ce\ufe0f Chassis & Drivetrain", expanded=False):
            cc1, cc2, cc3 = st.columns(3)
            with cc1:
                gear_ratio = st.text_input("Gear Ratio", value=_v(data, 'gear_ratio'), key=f"{form_key}_gr")
            with cc2:
                sway_bar = st.text_input("Sway Bar", value=_v(data, 'sway_bar'), key=f"{form_key}_sw")
            with cc3:
                track_bar = st.text_input("Track Bar Height", value=_v(data, 'track_bar'), key=f"{form_key}_tb")
            if not quick_mode:
                tc1, tc2 = st.columns(2)
                with tc1:
                    panhard = st.text_input("Panhard Bar", value=_v(data, 'panhard'), key=f"{form_key}_pan")
                    trailing_arm = st.text_input("Trailing Arm Angle", value=_v(data, 'trailing_arm'), key=f"{form_key}_ta")
                with tc2:
                    stagger = st.text_input("Stagger", value=_v(data, 'stagger'), key=f"{form_key}_stag")

        # ── Tire Pressures ──
        tp_vals = {}
        with st.expander("\U0001f3ce\ufe0f Tire Pressures (psi)", expanded=False):
            tp1, tp2, tp3, tp4 = st.columns(4)
            with tp1:
                tp_vals['tire_pres_LF'] = st.text_input("LF Pressure (psi)", value=_v(data, 'tire_pres_LF'), key=f"{form_key}_tp_lf")
            with tp2:
                tp_vals['tire_pres_RF'] = st.text_input("RF Pressure (psi)", value=_v(data, 'tire_pres_RF'), key=f"{form_key}_tp_rf")
            with tp3:
                tp_vals['tire_pres_LR'] = st.text_input("LR Pressure (psi)", value=_v(data, 'tire_pres_LR'), key=f"{form_key}_tp_lr")
            with tp4:
                tp_vals['tire_pres_RR'] = st.text_input("RR Pressure (psi)", value=_v(data, 'tire_pres_RR'), key=f"{form_key}_tp_rr")

        notes = st.text_area("Setup Notes", value=_v(data, 'notes'), key=f"{form_key}_notes")

        submitted = st.form_submit_button("\U0001f4be Save Setup", type="primary")

    # Build the save dict — auto-calc weight fields
    total_s, cross_s, left_s = _auto_calc_weights(
        wt.get('weight_LF', ''), wt.get('weight_RF', ''),
        wt.get('weight_LR', ''), wt.get('weight_RR', ''))

    return submitted, {
        "chassis": chassis, "setup_name": setup_name, "date": str(setup_date),
        **spr, **comp, **reb, **rh, **align,
        "toe": toe, **wt,
        "weight_left": left_s, "weight_rear": "", "weight_cross": cross_s,
        "gear_ratio": gear_ratio, "sway_bar": sway_bar, "track_bar": track_bar,
        "panhard": panhard, "trailing_arm": trailing_arm,
        **tp_vals, "stagger": stagger,
        "notes": notes,
    }



def render():
    st.header("\U0001f527 Setup Book")
    chassis_list = get_chassis_list()
    if not chassis_list:
        st.warning("Add a chassis profile first.")
        return

    _ensure_headers()

    tab_labels = ["View Setups", "Compare Setups"]
    if can_edit():
        tab_labels.append("Add / Edit Setup")
    if can_delete():
        tab_labels.append("Delete Setup")
    tabs = st.tabs(tab_labels)
    tab_idx = 0

    # ========================
    # TAB 1 -- View Setups (always visible)
    # ========================
    with tabs[tab_idx]:
        df = read_sheet("setups")
        if not df.empty:
            filt = st.selectbox("Filter by Chassis", ["All"] + chassis_list, key="view_filt")
            if filt != "All":
                df = df[df["chassis"] == filt]
            names = df["setup_name"].tolist() if "setup_name" in df.columns else []
            if names:
                selected = st.selectbox("Select a setup to view", names, key="view_setup_select")
                _, full_data = _find_setup(selected)
                if full_data:
                    _show_detail(full_data)
                else:
                    st.warning("Could not load details.")
            else:
                st.info("No setups match this filter.")
        else:
            st.info("No setups saved yet. Add one in the Add / Edit Setup tab.")

    # ========================
    # TAB 2 -- Compare Setups (always visible)
    # ========================
    tab_idx += 1
    with tabs[tab_idx]:
        df = read_sheet("setups")
        if not df.empty and "setup_name" in df.columns:
            all_names = df["setup_name"].tolist()
            if len(all_names) < 2:
                st.info("Need at least 2 setups to compare.")
            else:
                cc1, cc2 = st.columns(2)
                with cc1:
                    setup_a = st.selectbox("Setup A", all_names, index=0, key="cmp_a")
                with cc2:
                    setup_b = st.selectbox("Setup B", all_names, index=min(1, len(all_names)-1), key="cmp_b")

                _, data_a = _find_setup(setup_a)
                _, data_b = _find_setup(setup_b)

                if data_a and data_b:
                    compare_keys = [
                        ("Springs", [f"spring_{c}" for c in CORNERS]),
                        ("Bump Springs", [f"bump_spring_{c}" for c in CORNERS]),
                        ("Shock Comp", [f"shock_comp_{c}" for c in CORNERS]),
                        ("Shock Reb", [f"shock_reb_{c}" for c in CORNERS]),
                        ("Ride Heights", [f"ride_height_{c}" for c in CORNERS]),
                        ("Camber", [f"camber_{c}" for c in CORNERS]),
                        ("Caster", ["caster_LF", "caster_RF"]),
                        ("Toe", ["toe"]),
                        ("Weights", [f"weight_{c}" for c in CORNERS]),
                        ("Chassis", ["gear_ratio", "sway_bar", "track_bar", "panhard", "trailing_arm", "stagger"]),
                    ]
                    for section, keys in compare_keys:
                        has_data = any(_v(data_a, k) or _v(data_b, k) for k in keys)
                        if has_data:
                            with st.expander(section, expanded=True):
                                cols_hdr = st.columns([2, 3, 3])
                                cols_hdr[0].markdown("**Field**")
                                cols_hdr[1].markdown(f"**{setup_a}**")
                                cols_hdr[2].markdown(f"**{setup_b}**")
                                for k in keys:
                                    va = _v(data_a, k, '\u2014')
                                    vb = _v(data_b, k, '\u2014')
                                    row_cols = st.columns([2, 3, 3])
                                    label = k.replace('_', ' ').title()
                                    row_cols[0].write(label)
                                    diff = va != vb and va != '\u2014' and vb != '\u2014'
                                    row_cols[1].markdown(f"{'**' if diff else ''}{va}{'**' if diff else ''}")
                                    row_cols[2].markdown(f"{'**' if diff else ''}{vb}{'**' if diff else ''}")
        else:
            st.info("No setups to compare yet.")

    # ========================
    # TAB 3 -- Add / Edit Setup (only if can_edit)
    # ========================
    if can_edit():
        tab_idx += 1
        with tabs[tab_idx]:
            df = read_sheet("setups")
            existing_names = df["setup_name"].tolist() if not df.empty and "setup_name" in df.columns else []
            mode = st.radio("Mode", ["Add New Setup", "Edit Existing"], horizontal=True, key="setup_mode")

            if mode == "Edit Existing" and existing_names:
                edit_name = st.selectbox("Select setup to edit", existing_names, key="edit_setup_select")
                _, data = _find_setup(edit_name)
                if not data:
                    data = {}
            elif mode == "Edit Existing":
                st.info("No setups to edit. Add one first.")
                st.stop()
            else:
                data = {}

            submitted, row = _setup_form(data, chassis_list, "setup_form")
            if submitted:
                if not row["setup_name"]:
                    st.error("Setup name is required.")
                else:
                    _upsert_setup(row["setup_name"], row)
                    st.success(f"Setup '{row['setup_name']}' saved!")
                    st.rerun()

    # ========================
    # TAB 4 -- Delete Setup (only if can_delete)
    # ========================
    if can_delete():
        tab_idx += 1
        with tabs[tab_idx]:
            df = read_sheet("setups")
            if not df.empty and "setup_name" in df.columns:
                del_name = st.selectbox("Select setup to delete", df["setup_name"].tolist(), key="del_setup_select")
                if st.button("\U0001f5d1 Delete Selected Setup", type="secondary"):
                    st.session_state["confirm_delete_setup"] = del_name
                if st.session_state.get("confirm_delete_setup") == del_name:
                    st.warning(f"Are you sure you want to delete **{del_name}**? This cannot be undone.")
                    c_yes, c_no = st.columns(2)
                    with c_yes:
                        if st.button("\u2705 Yes, Delete", type="primary", key="confirm_del_setup_yes"):
                            row_idx = df[df["setup_name"] == del_name].index[0] + 2
                            delete_row("setups", row_idx)
                            st.session_state.pop("confirm_delete_setup", None)
                            st.success(f"Deleted {del_name}")
                            st.rerun()
                    with c_no:
                        if st.button("\u274c Cancel", key="confirm_del_setup_no"):
                            st.session_state.pop("confirm_delete_setup", None)
                            st.rerun()
            else:
                st.info("No setups to delete.")
