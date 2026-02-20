import streamlit as st
from utils.gsheet_db import (
    read_sheet, append_row, delete_row, timestamp_now,
    update_row_partial, get_worksheet,
)

# -- All column headers the chassis sheet needs --
ALL_HEADERS = [
    "chassis_name", "car_number", "car_class", "year_make", "notes",
    # Corner weights
    "weight_lf", "weight_rf", "weight_lr", "weight_rr",
    # Ride heights
    "ride_height_lf", "ride_height_rf", "ride_height_lr", "ride_height_rr",
    # Springs
    "spring_lf", "spring_rf", "spring_lr", "spring_rr",
    # Shocks
    "shock_lf", "shock_rf", "shock_lr", "shock_rr",
    # Suspension geometry
    "camber_lf", "camber_rf", "camber_lr", "camber_rr",
    "caster_lf", "caster_rf",
    "toe_front", "toe_rear",
    # Sway bars
    "sway_bar_front", "sway_bar_rear",
    # Dimensions
    "wheelbase", "track_width_front", "track_width_rear",
    # Drivetrain
    "gear_ratio", "pinion_angle",
    "created",
]


def _ensure_headers():
    """Make sure chassis sheet has all required headers."""
    ws = get_worksheet("chassis")
    existing = ws.row_values(1)
    trimmed = [h for h in existing if h.strip()]
    missing = [h for h in ALL_HEADERS if h not in trimmed]
    if missing:
        new_headers = trimmed + missing
        from utils.gsheet_db import _col_letter
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


def _find_chassis(name):
    """Find a chassis row by name. Returns (row_index, row_dict) or (None, None)."""
    ws = get_worksheet("chassis")
    all_values = ws.get_all_values()
    if not all_values or len(all_values) < 2:
        return None, None
    headers = all_values[0]
    name_col = None
    for i, h in enumerate(headers):
        if h.strip().lower() == "chassis_name":
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


def _upsert_chassis(name, data):
    """Create or update a chassis row by name."""
    row_index, existing = _find_chassis(name)
    if row_index is not None:
        merged = {}
        if existing:
            merged.update(existing)
        merged.update(data)
        merged["chassis_name"] = name
        from utils.gsheet_db import update_row
        update_row("chassis", row_index, merged)
        return row_index
    else:
        data["chassis_name"] = name
        append_row("chassis", data)
        new_idx, _ = _find_chassis(name)
        return new_idx


def _show_detail(data):
    """Read-only detail view for a selected chassis."""
    st.markdown(f"### {data.get('chassis_name', '')}")
    c1, c2, c3 = st.columns(3)
    c1.metric("Car Number", _v(data, 'car_number', '\u2014'))
    c2.metric("Class", _v(data, 'car_class', '\u2014'))
    c3.metric("Year / Make", _v(data, 'year_make', '\u2014'))
    st.divider()

    # Corner Weights
    wlf = _vf(data, 'weight_lf')
    wrf = _vf(data, 'weight_rf')
    wlr = _vf(data, 'weight_lr')
    wrr = _vf(data, 'weight_rr')
    total = wlf + wrf + wlr + wrr
    if total > 0:
        with st.expander("\u2696\ufe0f Corner Weights", expanded=True):
            w1, w2, w3, w4 = st.columns(4)
            w1.metric("\U0001f7e6 LF", f"{wlf:.0f} lbs")
            w2.metric("\U0001f7e5 RF", f"{wrf:.0f} lbs")
            w3.metric("\U0001f7e6 LR", f"{wlr:.0f} lbs")
            w4.metric("\U0001f7e5 RR", f"{wrr:.0f} lbs")
            cross = wrf + wlr
            left = wlf + wlr
            cross_pct = (cross / total * 100) if total else 0
            left_pct = (left / total * 100) if total else 0
            m1, m2, m3 = st.columns(3)
            m1.metric("Total Weight", f"{total:.0f} lbs")
            m2.metric("Cross Weight", f"{cross_pct:.1f}%")
            m3.metric("Left Side", f"{left_pct:.1f}%")

    # Ride Heights
    rh_any = any(_v(data, f'ride_height_{c}') for c in ['lf','rf','lr','rr'])
    if rh_any:
        with st.expander("\U0001f4cf Ride Heights", expanded=True):
            r1, r2, r3, r4 = st.columns(4)
            r1.metric("LF", _v(data, 'ride_height_lf', '\u2014'))
            r2.metric("RF", _v(data, 'ride_height_rf', '\u2014'))
            r3.metric("LR", _v(data, 'ride_height_lr', '\u2014'))
            r4.metric("RR", _v(data, 'ride_height_rr', '\u2014'))

    # Springs & Shocks
    sp_any = any(_v(data, f'spring_{c}') for c in ['lf','rf','lr','rr'])
    sh_any = any(_v(data, f'shock_{c}') for c in ['lf','rf','lr','rr'])
    if sp_any or sh_any:
        with st.expander("\U0001f9f2 Springs & Shocks", expanded=True):
            if sp_any:
                st.markdown("**Springs (lbs)**")
                s1, s2, s3, s4 = st.columns(4)
                s1.metric("LF", _v(data, 'spring_lf', '\u2014'))
                s2.metric("RF", _v(data, 'spring_rf', '\u2014'))
                s3.metric("LR", _v(data, 'spring_lr', '\u2014'))
                s4.metric("RR", _v(data, 'spring_rr', '\u2014'))
            if sh_any:
                st.markdown("**Shocks**")
                s1, s2, s3, s4 = st.columns(4)
                s1.metric("LF", _v(data, 'shock_lf', '\u2014'))
                s2.metric("RF", _v(data, 'shock_rf', '\u2014'))
                s3.metric("LR", _v(data, 'shock_lr', '\u2014'))
                s4.metric("RR", _v(data, 'shock_rr', '\u2014'))

    # Suspension Geometry
    geo_any = any(_v(data, k) for k in ['camber_lf','camber_rf','camber_lr','camber_rr','caster_lf','caster_rf','toe_front','toe_rear'])
    if geo_any:
        with st.expander("\U0001f4d0 Suspension Geometry", expanded=True):
            st.markdown("**Camber**")
            g1, g2, g3, g4 = st.columns(4)
            g1.metric("LF", _v(data, 'camber_lf', '\u2014'))
            g2.metric("RF", _v(data, 'camber_rf', '\u2014'))
            g3.metric("LR", _v(data, 'camber_lr', '\u2014'))
            g4.metric("RR", _v(data, 'camber_rr', '\u2014'))
            st.markdown("**Caster**")
            ca1, ca2 = st.columns(2)
            ca1.metric("LF Caster", _v(data, 'caster_lf', '\u2014'))
            ca2.metric("RF Caster", _v(data, 'caster_rf', '\u2014'))
            st.markdown("**Toe**")
            t1, t2 = st.columns(2)
            t1.metric("Front Toe", _v(data, 'toe_front', '\u2014'))
            t2.metric("Rear Toe", _v(data, 'toe_rear', '\u2014'))

    # Sway Bars
    sb_any = _v(data, 'sway_bar_front') or _v(data, 'sway_bar_rear')
    if sb_any:
        with st.expander("\U0001f517 Sway Bars", expanded=True):
            sb1, sb2 = st.columns(2)
            sb1.metric("Front", _v(data, 'sway_bar_front', '\u2014'))
            sb2.metric("Rear", _v(data, 'sway_bar_rear', '\u2014'))

    # Dimensions & Drivetrain
    dim_any = any(_v(data, k) for k in ['wheelbase','track_width_front','track_width_rear','gear_ratio','pinion_angle'])
    if dim_any:
        with st.expander("\U0001f4d0 Dimensions & Drivetrain", expanded=True):
            d1, d2, d3 = st.columns(3)
            d1.metric("Wheelbase", _v(data, 'wheelbase', '\u2014'))
            d2.metric("Front Track Width", _v(data, 'track_width_front', '\u2014'))
            d3.metric("Rear Track Width", _v(data, 'track_width_rear', '\u2014'))
            dr1, dr2 = st.columns(2)
            dr1.metric("Gear Ratio", _v(data, 'gear_ratio', '\u2014'))
            dr2.metric("Pinion Angle", _v(data, 'pinion_angle', '\u2014'))

    # Notes
    notes = _v(data, 'notes')
    if notes:
        with st.expander("\U0001f4dd Notes", expanded=False):
            st.write(notes)


def render():
    st.header("\U0001f697 Chassis Profiles")
    _ensure_headers()

    tab_view, tab_edit, tab_delete = st.tabs(["View Chassis", "Add / Edit Chassis", "Delete Chassis"])

    # ========================
    # TAB 1 -- View Chassis
    # ========================
    with tab_view:
        df = read_sheet("chassis")
        if not df.empty:
            names = df["chassis_name"].tolist()
            selected = st.selectbox("Select a chassis to view", names, key="view_chassis_select")
            _, full_data = _find_chassis(selected)
            if full_data:
                _show_detail(full_data)
            else:
                st.warning("Could not load details.")
        else:
            st.info("No chassis profiles yet. Add one in the next tab.")

    # ========================
    # TAB 2 -- Add / Edit
    # ========================
    with tab_edit:
        df = read_sheet("chassis")
        existing_names = df["chassis_name"].tolist() if not df.empty else []
        mode = st.radio("Mode", ["Add New Chassis", "Edit Existing"], horizontal=True, key="chassis_mode")

        if mode == "Edit Existing" and existing_names:
            edit_name = st.selectbox("Select chassis to edit", existing_names, key="edit_chassis_select")
            _, data = _find_chassis(edit_name)
            if not data:
                data = {}
        elif mode == "Edit Existing":
            st.info("No chassis to edit. Add one first.")
            return
        else:
            data = {}

        with st.form("chassis_form", clear_on_submit=False):
            st.subheader("Basic Info")
            bc1, bc2 = st.columns(2)
            with bc1:
                name = st.text_input("Chassis Name *", value=_v(data, 'chassis_name'), key="cf_name")
                car_number = st.text_input("Car Number", value=_v(data, 'car_number'), key="cf_number")
            with bc2:
                car_class = st.selectbox("Class", ["Pro Late Model", "Super Stock", "Bone Stock", "Mini Stock", "Other"],
                    index=["Pro Late Model","Super Stock","Bone Stock","Mini Stock","Other"].index(_v(data,'car_class','Pro Late Model')),
                    key="cf_class")
                year = st.text_input("Year / Make", value=_v(data, 'year_make'), key="cf_year")

            st.divider()
            st.subheader("\u2696\ufe0f Corner Weights (lbs)")
            cw1, cw2, cw3, cw4 = st.columns(4)
            with cw1:
                wlf = st.text_input("LF Weight", value=_v(data, 'weight_lf'), key="cf_wlf")
            with cw2:
                wrf = st.text_input("RF Weight", value=_v(data, 'weight_rf'), key="cf_wrf")
            with cw3:
                wlr = st.text_input("LR Weight", value=_v(data, 'weight_lr'), key="cf_wlr")
            with cw4:
                wrr = st.text_input("RR Weight", value=_v(data, 'weight_rr'), key="cf_wrr")

            st.divider()
            st.subheader("\U0001f4cf Ride Heights")
            rh1, rh2, rh3, rh4 = st.columns(4)
            with rh1:
                rh_lf = st.text_input("LF Ride Height", value=_v(data, 'ride_height_lf'), key="cf_rhlf")
            with rh2:
                rh_rf = st.text_input("RF Ride Height", value=_v(data, 'ride_height_rf'), key="cf_rhrf")
            with rh3:
                rh_lr = st.text_input("LR Ride Height", value=_v(data, 'ride_height_lr'), key="cf_rhlr")
            with rh4:
                rh_rr = st.text_input("RR Ride Height", value=_v(data, 'ride_height_rr'), key="cf_rhrr")

            st.divider()
            st.subheader("\U0001f9f2 Springs & Shocks")
            st.markdown("**Springs (lbs)")
            sp1, sp2, sp3, sp4 = st.columns(4)
            with sp1:
                s_lf = st.text_input("LF Spring", value=_v(data, 'spring_lf'), key="cf_slf")
            with sp2:
                s_rf = st.text_input("RF Spring", value=_v(data, 'spring_rf'), key="cf_srf")
            with sp3:
                s_lr = st.text_input("LR Spring", value=_v(data, 'spring_lr'), key="cf_slr")
            with sp4:
                s_rr = st.text_input("RR Spring", value=_v(data, 'spring_rr'), key="cf_srr")
            st.markdown("**Shocks**")
            sh1, sh2, sh3, sh4 = st.columns(4)
            with sh1:
                sk_lf = st.text_input("LF Shock", value=_v(data, 'shock_lf'), key="cf_sklf")
            with sh2:
                sk_rf = st.text_input("RF Shock", value=_v(data, 'shock_rf'), key="cf_skrf")
            with sh3:
                sk_lr = st.text_input("LR Shock", value=_v(data, 'shock_lr'), key="cf_sklr")
            with sh4:
                sk_rr = st.text_input("RR Shock", value=_v(data, 'shock_rr'), key="cf_skrr")

            st.divider()
            st.subheader("\U0001f4d0 Suspension Geometry")
            st.markdown("**Camber**")
            cam1, cam2, cam3, cam4 = st.columns(4)
            with cam1:
                cam_lf = st.text_input("LF Camber", value=_v(data, 'camber_lf'), key="cf_camlf")
            with cam2:
                cam_rf = st.text_input("RF Camber", value=_v(data, 'camber_rf'), key="cf_camrf")
            with cam3:
                cam_lr = st.text_input("LR Camber", value=_v(data, 'camber_lr'), key="cf_camlr")
            with cam4:
                cam_rr = st.text_input("RR Camber", value=_v(data, 'camber_rr'), key="cf_camrr")
            st.markdown("**Caster**")
            cas1, cas2 = st.columns(2)
            with cas1:
                cas_lf = st.text_input("LF Caster", value=_v(data, 'caster_lf'), key="cf_caslf")
            with cas2:
                cas_rf = st.text_input("RF Caster", value=_v(data, 'caster_rf'), key="cf_casrf")
            st.markdown("**Toe**")
            toe1, toe2 = st.columns(2)
            with toe1:
                toe_f = st.text_input("Front Toe", value=_v(data, 'toe_front'), key="cf_toef")
            with toe2:
                toe_r = st.text_input("Rear Toe", value=_v(data, 'toe_rear'), key="cf_toer")

            st.divider()
            st.subheader("\U0001f517 Sway Bars")
            swb1, swb2 = st.columns(2)
            with swb1:
                sw_f = st.text_input("Front Sway Bar", value=_v(data, 'sway_bar_front'), key="cf_swf")
            with swb2:
                sw_r = st.text_input("Rear Sway Bar", value=_v(data, 'sway_bar_rear'), key="cf_swr")

            st.divider()
            st.subheader("\U0001f4d0 Dimensions & Drivetrain")
            dm1, dm2, dm3 = st.columns(3)
            with dm1:
                wb = st.text_input("Wheelbase", value=_v(data, 'wheelbase'), key="cf_wb")
            with dm2:
                tw_f = st.text_input("Front Track Width", value=_v(data, 'track_width_front'), key="cf_twf")
            with dm3:
                tw_r = st.text_input("Rear Track Width", value=_v(data, 'track_width_rear'), key="cf_twr")
            dt1, dt2 = st.columns(2)
            with dt1:
                gr = st.text_input("Gear Ratio", value=_v(data, 'gear_ratio'), key="cf_gr")
            with dt2:
                pa = st.text_input("Pinion Angle", value=_v(data, 'pinion_angle'), key="cf_pa")

            st.divider()
            notes = st.text_area("Notes", value=_v(data, 'notes'), key="cf_notes")

            if st.form_submit_button("\U0001f4be Save Chassis", type="primary"):
                if not name:
                    st.error("Chassis name is required.")
                else:
                    save = {
                        "chassis_name": name,
                        "car_number": car_number,
                        "car_class": car_class,
                        "year_make": year,
                        "notes": notes,
                        "weight_lf": wlf, "weight_rf": wrf,
                        "weight_lr": wlr, "weight_rr": wrr,
                        "ride_height_lf": rh_lf, "ride_height_rf": rh_rf,
                        "ride_height_lr": rh_lr, "ride_height_rr": rh_rr,
                        "spring_lf": s_lf, "spring_rf": s_rf,
                        "spring_lr": s_lr, "spring_rr": s_rr,
                        "shock_lf": sk_lf, "shock_rf": sk_rf,
                        "shock_lr": sk_lr, "shock_rr": sk_rr,
                        "camber_lf": cam_lf, "camber_rf": cam_rf,
                        "camber_lr": cam_lr, "camber_rr": cam_rr,
                        "caster_lf": cas_lf, "caster_rf": cas_rf,
                        "toe_front": toe_f, "toe_rear": toe_r,
                        "sway_bar_front": sw_f, "sway_bar_rear": sw_r,
                        "wheelbase": wb,
                        "track_width_front": tw_f, "track_width_rear": tw_r,
                        "gear_ratio": gr, "pinion_angle": pa,
                        "created": timestamp_now(),
                    }
                    _upsert_chassis(name, save)
                    st.success(f"Chassis '{name}' saved!")
                    st.rerun()

    # ========================
    # TAB 3 -- Delete Chassis
    # ========================
    with tab_delete:
        df = read_sheet("chassis")
        if not df.empty:
            del_name = st.selectbox("Select chassis to delete", df["chassis_name"].tolist(), key="del_chassis_select")
            if st.button("\U0001f5d1 Delete Selected Chassis", type="secondary"):
                row_idx = df[df["chassis_name"] == del_name].index[0] + 2
                delete_row("chassis", row_idx)
                st.success(f"Deleted {del_name}")
                st.rerun()
        else:
            st.info("No chassis profiles to delete.")
