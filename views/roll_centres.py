import streamlit as st
import pandas as pd
import math
from utils.gsheet_db import (
    read_sheet, append_row, delete_row, update_row,
    get_chassis_list, timestamp_now, _col_letter, get_worksheet
)

# -- All column headers for the roll_centres sheet --
ALL_HEADERS = [
    "chassis", "date", "track", "notes",
    # Front suspension inputs
    "f_lca_length", "f_uca_length",
    "f_lca_inner_height", "f_lca_outer_height",
    "f_uca_inner_height", "f_uca_outer_height",
    "f_spindle_height",
    # Rear suspension inputs
    "r_lca_length", "r_uca_length",
    "r_lca_inner_height", "r_lca_outer_height",
    "r_uca_inner_height", "r_uca_outer_height",
    "r_spindle_height",
    # Calculated results
    "front_rc_height", "rear_rc_height",
    "rc_height_diff",
]


def _ensure_headers():
    ws = get_worksheet("roll_centres")
    existing = ws.row_values(1)
    trimmed = [h for h in existing if h.strip()]
    missing = [h for h in ALL_HEADERS if h not in trimmed]
    if missing:
        new_headers = trimmed + missing
        end_col = _col_letter(len(new_headers))
        ws.update(f"A1:{end_col}1", [new_headers])


def _vf(data, key, default=0.0):
    val = data.get(key, "")
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _calc_rc_height(lca_len, uca_len, lca_inner_h, lca_outer_h, uca_inner_h, uca_outer_h, spindle_h):
    """
    Simplified roll centre height calculation using instant centre method.
    Returns roll centre height in inches.
    """
    try:
        # LCA angle
        if lca_len > 0:
            lca_angle = math.atan2(lca_outer_h - lca_inner_h, lca_len)
        else:
            return 0.0
        # UCA angle
        if uca_len > 0:
            uca_angle = math.atan2(uca_outer_h - uca_inner_h, uca_len)
        else:
            return 0.0
        # Instant centre: intersection of LCA and UCA lines
        # Using slope-intercept form from inner pivot points
        lca_slope = math.tan(lca_angle)
        uca_slope = math.tan(uca_angle)
        # If slopes are parallel, return 0
        if abs(lca_slope - uca_slope) < 1e-9:
            return 0.0
        # Instant centre X from car centreline
        ic_x = (uca_inner_h - lca_inner_h) / (lca_slope - uca_slope)
        ic_y = lca_inner_h + lca_slope * ic_x
        # Roll centre height: line from contact patch (0,0) through instant centre
        # to car centreline
        half_track = spindle_h if spindle_h > 0 else 30.0
        if ic_x + half_track != 0:
            rc_height = ic_y * half_track / (ic_x + half_track)
        else:
            rc_height = 0.0
        return round(rc_height, 3)
    except Exception:
        return 0.0


def render():
    st.title("📐 Roll Centres")
    st.caption("Calculate and track front and rear roll centre heights for each chassis.")

    chassis_list = get_chassis_list()
    if not chassis_list:
        st.warning("No chassis found. Please add a chassis in Chassis Profiles first.")
        return

    _ensure_headers()

    tab_calc, tab_log = st.tabs(["🔢 Calculate", "📋 Log / History"])

    # ─── CALCULATE TAB ───
    with tab_calc:
        st.subheader("Roll Centre Calculator")
        st.markdown(
            "Enter suspension measurements below. "
            "The calculator uses the **instant centre method** to estimate "
            "front and rear roll centre heights."
        )

        col_chassis, col_track, col_date = st.columns(3)
        with col_chassis:
            chassis = st.selectbox("Chassis", chassis_list, key="rc_chassis")
        with col_track:
            track = st.text_input("Track / Event", key="rc_track")
        with col_date:
            date_val = st.text_input("Date", value=timestamp_now()[:10], key="rc_date")

        st.divider()

        # ── FRONT SUSPENSION ──
        st.markdown("### Front Suspension")
        f1, f2, f3 = st.columns(3)
        with f1:
            f_lca_len = st.number_input("LCA Length (in)", min_value=0.0, value=12.0, step=0.125, key="f_lca_len")
            f_uca_len = st.number_input("UCA Length (in)", min_value=0.0, value=10.0, step=0.125, key="f_uca_len")
        with f2:
            f_lca_inner_h = st.number_input("LCA Inner Height (in)", value=6.0, step=0.125, key="f_lca_inner_h")
            f_lca_outer_h = st.number_input("LCA Outer Height (in)", value=5.5, step=0.125, key="f_lca_outer_h")
        with f3:
            f_uca_inner_h = st.number_input("UCA Inner Height (in)", value=14.0, step=0.125, key="f_uca_inner_h")
            f_uca_outer_h = st.number_input("UCA Outer Height (in)", value=13.0, step=0.125, key="f_uca_outer_h")

        f_spindle_h = st.number_input(
            "Front Track Half-Width / Spindle Offset (in)",
            min_value=1.0, value=30.0, step=0.5, key="f_spindle_h",
            help="Half the front track width — distance from car centreline to front contact patch."
        )

        front_rc = _calc_rc_height(
            f_lca_len, f_uca_len,
            f_lca_inner_h, f_lca_outer_h,
            f_uca_inner_h, f_uca_outer_h,
            f_spindle_h
        )

        st.divider()

        # ── REAR SUSPENSION ──
        st.markdown("### Rear Suspension")
        r1, r2, r3 = st.columns(3)
        with r1:
            r_lca_len = st.number_input("LCA Length (in)", min_value=0.0, value=12.0, step=0.125, key="r_lca_len")
            r_uca_len = st.number_input("UCA Length (in)", min_value=0.0, value=10.0, step=0.125, key="r_uca_len")
        with r2:
            r_lca_inner_h = st.number_input("LCA Inner Height (in)", value=6.0, step=0.125, key="r_lca_inner_h")
            r_lca_outer_h = st.number_input("LCA Outer Height (in)", value=5.5, step=0.125, key="r_lca_outer_h")
        with r3:
            r_uca_inner_h = st.number_input("UCA Inner Height (in)", value=14.0, step=0.125, key="r_uca_inner_h")
            r_uca_outer_h = st.number_input("UCA Outer Height (in)", value=13.0, step=0.125, key="r_uca_outer_h")

        r_spindle_h = st.number_input(
            "Rear Track Half-Width / Spindle Offset (in)",
            min_value=1.0, value=30.0, step=0.5, key="r_spindle_h",
            help="Half the rear track width — distance from car centreline to rear contact patch."
        )

        rear_rc = _calc_rc_height(
            r_lca_len, r_uca_len,
            r_lca_inner_h, r_lca_outer_h,
            r_uca_inner_h, r_uca_outer_h,
            r_spindle_h
        )

        st.divider()

        # ── RESULTS ──
        rc_diff = round(rear_rc - front_rc, 3)
        st.markdown("### Calculated Roll Centre Heights")
        res1, res2, res3 = st.columns(3)
        with res1:
            st.metric("Front Roll Centre", f"{front_rc:.3f} in")
        with res2:
            st.metric("Rear Roll Centre", f"{rear_rc:.3f} in")
        with res3:
            delta_label = "Rear higher" if rc_diff > 0 else ("Front higher" if rc_diff < 0 else "Equal")
            st.metric("RC Diff (Rear − Front)", f"{rc_diff:.3f} in", delta=delta_label)

        st.divider()
        notes = st.text_area("Notes", key="rc_notes", placeholder="Setup notes, track conditions, etc.")

        if st.button("💾 Save to Log", type="primary", use_container_width=True):
            row = {
                "chassis": chassis,
                "date": date_val,
                "track": track,
                "notes": notes,
                "f_lca_length": f_lca_len,
                "f_uca_length": f_uca_len,
                "f_lca_inner_height": f_lca_inner_h,
                "f_lca_outer_height": f_lca_outer_h,
                "f_uca_inner_height": f_uca_inner_h,
                "f_uca_outer_height": f_uca_outer_h,
                "f_spindle_height": f_spindle_h,
                "r_lca_length": r_lca_len,
                "r_uca_length": r_uca_len,
                "r_lca_inner_height": r_lca_inner_h,
                "r_lca_outer_height": r_lca_outer_h,
                "r_uca_inner_height": r_uca_inner_h,
                "r_uca_outer_height": r_uca_outer_h,
                "r_spindle_height": r_spindle_h,
                "front_rc_height": front_rc,
                "rear_rc_height": rear_rc,
                "rc_height_diff": rc_diff,
            }
            append_row("roll_centres", row)
            st.success(f"Saved! Front RC: {front_rc:.3f} in | Rear RC: {rear_rc:.3f} in")
            st.rerun()

    # ─── LOG / HISTORY TAB ───
    with tab_log:
        st.subheader("Roll Centre Log")

        df = read_sheet("roll_centres")
        if df.empty:
            st.info("No roll centre entries logged yet. Use the Calculate tab to add your first entry.")
        else:
            # Filter by chassis
            chassis_filter = st.selectbox(
                "Filter by Chassis",
                ["All"] + chassis_list,
                key="rc_log_filter"
            )
            if chassis_filter != "All":
                df = df[df["chassis"] == chassis_filter]

            # Show summary table with key columns
            display_cols = [c for c in [
                "chassis", "date", "track",
                "front_rc_height", "rear_rc_height", "rc_height_diff",
                "notes"
            ] if c in df.columns]
            st.dataframe(df[display_cols], use_container_width=True, hide_index=True)

            st.divider()
            st.markdown("#### Delete Entry")
            row_nums = list(range(1, len(df) + 1))
            del_row = st.selectbox(
                "Select row number to delete",
                row_nums,
                format_func=lambda x: f"Row {x}: {df.iloc[x-1].get('chassis','') if 'chassis' in df.columns else ''} — {df.iloc[x-1].get('date','') if 'date' in df.columns else ''}",
                key="rc_del_row"
            )
            if st.button("🗑️ Delete Selected Entry", key="rc_del_btn"):
                # +1 for header row in sheet
                delete_row("roll_centres", del_row + 1)
                st.success("Entry deleted.")
                st.rerun()
