import streamlit as st
import pandas as pd
import math
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from utils.gsheet_db import (
    read_sheet, append_row, delete_row, update_row,
    get_chassis_list, timestamp_now, _col_letter, get_worksheet
)

ALL_HEADERS = [
    "chassis", "date", "track", "notes",
    "f_lca_length", "f_uca_length",
    "f_lca_inner_height", "f_lca_outer_height",
    "f_uca_inner_height", "f_uca_outer_height",
    "f_spindle_height",
    "r_trailing_arm_length",
    "r_trailing_arm_frame_height",
    "r_trailing_arm_axle_height",
    "r_upper_link_length",
    "r_upper_link_frame_height",
    "r_upper_link_axle_height",
    "r_upper_link_frame_offset",
    "r_upper_link_axle_offset",
    "r_rear_track_half",
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


def _calc_front_rc_height(lca_len, uca_len, lca_inner_h, lca_outer_h,
                          uca_inner_h, uca_outer_h, spindle_h):
    try:
        if lca_len > 0:
            lca_angle = math.atan2(lca_outer_h - lca_inner_h, lca_len)
        else:
            return 0.0
        if uca_len > 0:
            uca_angle = math.atan2(uca_outer_h - uca_inner_h, uca_len)
        else:
            return 0.0
        lca_slope = math.tan(lca_angle)
        uca_slope = math.tan(uca_angle)
        if abs(lca_slope - uca_slope) < 1e-9:
            return 0.0
        ic_x = (uca_inner_h - lca_inner_h) / (lca_slope - uca_slope)
        ic_y = lca_inner_h + lca_slope * ic_x
        half_track = spindle_h if spindle_h > 0 else 30.0
        if ic_x + half_track != 0:
            rc_height = ic_y * half_track / (ic_x + half_track)
        else:
            rc_height = 0.0
        return round(rc_height, 3)
    except Exception:
        return 0.0


def _calc_rear_rc_height(upper_frame_h, upper_axle_h,
                         upper_frame_offset, upper_axle_offset):
    try:
        dx = upper_axle_offset - upper_frame_offset
        if abs(dx) < 0.001:
            return round((upper_frame_h + upper_axle_h) / 2.0, 3)
        slope = (upper_axle_h - upper_frame_h) / dx
        rc_height = upper_frame_h - slope * upper_frame_offset
        return round(rc_height, 3)
    except Exception:
        return 0.0


def _draw_rc_diagram(front_rc, rear_rc):
    """Draw a side-view roll centre diagram with car silhouette."""
    bg = "#0e1117"
    card_bg = "#1a1e2e"
    ground_color = "#3a3f4b"
    car_color = "#cc0000"
    car_outline = "#ff3333"
    front_color = "#00d4ff"
    rear_color = "#ff6b35"
    axis_color = "#ffd700"
    text_color = "#e0e0e0"
    grid_color = "#2a2e3a"

    wheelbase = 108  # inches (typical late model)
    fig, ax = plt.subplots(figsize=(10, 4.5))
    fig.patch.set_facecolor(bg)
    ax.set_facecolor(card_bg)

    # Ground line
    ax.axhline(y=0, color=ground_color, linewidth=2.5, zorder=1)
    ax.fill_between([-15, wheelbase + 15], -2, 0,
                    color=ground_color, alpha=0.15, zorder=0)

    # Grid
    max_h = max(abs(front_rc), abs(rear_rc), 10) + 5
    for h in range(0, int(max_h) + 5, 5):
        if h > 0:
            ax.axhline(y=h, color=grid_color, linewidth=0.5,
                       linestyle="--", alpha=0.4, zorder=0)

    # Wheels
    wheel_r = 5
    for wx in [0, wheelbase]:
        circle = plt.Circle((wx, wheel_r), wheel_r,
                            fill=False, color="#666", linewidth=2, zorder=3)
        ax.add_patch(circle)
        inner = plt.Circle((wx, wheel_r), 2.5,
                           fill=True, color="#444", linewidth=1, zorder=3)
        ax.add_patch(inner)

    # Car body silhouette
    body_y = wheel_r * 2
    body = patches.FancyBboxPatch(
        (-5, body_y), wheelbase + 10, 10,
        boxstyle="round,pad=2",
        facecolor=car_color, edgecolor=car_outline,
        alpha=0.25, linewidth=1.5, zorder=2
    )
    ax.add_patch(body)

    # Roll centre markers
    ax.plot(0, front_rc, "o", color=front_color, markersize=14,
            zorder=5, markeredgecolor="white", markeredgewidth=1.5)
    ax.plot(wheelbase, rear_rc, "o", color=rear_color, markersize=14,
            zorder=5, markeredgecolor="white", markeredgewidth=1.5)

    # Roll axis line
    ax.plot([0, wheelbase], [front_rc, rear_rc],
            color=axis_color, linewidth=2.5, linestyle="-",
            zorder=4, alpha=0.9)
    # Dashed extension
    extend = 15
    if wheelbase > 0:
        slope = (rear_rc - front_rc) / wheelbase
        ax.plot([-extend, 0], [front_rc - slope * extend, front_rc],
                color=axis_color, linewidth=1, linestyle=":",
                alpha=0.4, zorder=4)
        ax.plot([wheelbase, wheelbase + extend],
                [rear_rc, rear_rc + slope * extend],
                color=axis_color, linewidth=1, linestyle=":",
                alpha=0.4, zorder=4)

    # Vertical reference lines from ground to RC
    ax.plot([0, 0], [0, front_rc], color=front_color,
            linewidth=1.2, linestyle="--", alpha=0.5, zorder=4)
    ax.plot([wheelbase, wheelbase], [0, rear_rc], color=rear_color,
            linewidth=1.2, linestyle="--", alpha=0.5, zorder=4)

    # Labels
    f_offset = 2.5 if front_rc >= 0 else -3.5
    r_offset = 2.5 if rear_rc >= 0 else -3.5
    ax.annotate(
        f"FRONT RC\n{front_rc:.3f}\"",
        xy=(0, front_rc), xytext=(-12, front_rc + f_offset),
        fontsize=9, fontweight="bold", color=front_color,
        ha="center", va="bottom",
        arrowprops=dict(arrowstyle="->", color=front_color,
                        lw=1.2, connectionstyle="arc3,rad=0.2"),
        zorder=6,
        bbox=dict(boxstyle="round,pad=0.3", facecolor=card_bg,
                  edgecolor=front_color, alpha=0.85)
    )
    ax.annotate(
        f"REAR RC\n{rear_rc:.3f}\"",
        xy=(wheelbase, rear_rc),
        xytext=(wheelbase + 12, rear_rc + r_offset),
        fontsize=9, fontweight="bold", color=rear_color,
        ha="center", va="bottom",
        arrowprops=dict(arrowstyle="->", color=rear_color,
                        lw=1.2, connectionstyle="arc3,rad=-0.2"),
        zorder=6,
        bbox=dict(boxstyle="round,pad=0.3", facecolor=card_bg,
                  edgecolor=rear_color, alpha=0.85)
    )

    # Roll axis label at midpoint
    mid_x = wheelbase / 2
    mid_y = (front_rc + rear_rc) / 2
    angle_deg = math.degrees(math.atan2(rear_rc - front_rc, wheelbase))
    ax.text(
        mid_x, mid_y + 3,
        f"ROLL AXIS  ({abs(rear_rc - front_rc):.3f}\" diff)",
        fontsize=8, color=axis_color, ha="center", va="bottom",
        fontstyle="italic", fontweight="bold",
        bbox=dict(boxstyle="round,pad=0.25", facecolor=card_bg,
                  edgecolor=axis_color, alpha=0.7),
        zorder=6
    )

    # Axis labels
    ax.text(0, -3.5, "FRONT", fontsize=9, color=text_color,
            ha="center", fontweight="bold", zorder=6)
    ax.text(wheelbase, -3.5, "REAR", fontsize=9, color=text_color,
            ha="center", fontweight="bold", zorder=6)
    ax.text(-15, -0.3, "GROUND", fontsize=7, color=ground_color,
            ha="left", va="top", fontstyle="italic", zorder=6)

    ax.set_xlim(-25, wheelbase + 25)
    y_lo = min(front_rc, rear_rc, 0) - 6
    y_hi = max(front_rc, rear_rc, max_h) + 8
    ax.set_ylim(y_lo, y_hi)
    ax.set_aspect("auto")
    ax.set_xlabel("Side View (inches)", color=text_color, fontsize=8)
    ax.set_ylabel("Height (inches)", color=text_color, fontsize=8)
    ax.tick_params(colors=text_color, labelsize=7)
    for spine in ax.spines.values():
        spine.set_color(grid_color)

    plt.tight_layout()
    return fig


def render():
    st.title("📐 Roll Centres")
    st.caption("Calculate and track front and rear roll centre heights for each chassis.")
    chassis_list = get_chassis_list()
    if not chassis_list:
        st.warning("No chassis found. Please add a chassis in Chassis Profiles first.")
        return
    _ensure_headers()
    tab_calc, tab_log = st.tabs(["🔢 Calculate", "📋 Log / History"])
    with tab_calc:
        st.subheader("Roll Centre Calculator")
        st.markdown(
            "Front uses the **instant centre method** (double A-arm). "
            "Rear uses **upper link projection** (trailing arms + upper link)."
        )
        col_chassis, col_track, col_date = st.columns(3)
        with col_chassis:
            chassis = st.selectbox("Chassis", chassis_list, key="rc_chassis")
        with col_track:
            track = st.text_input("Track / Event", key="rc_track")
        with col_date:
            date_val = st.text_input("Date", value=timestamp_now()[:10], key="rc_date")
        st.divider()
        st.markdown("### Front Suspension")
        st.caption("Double A-Arm")
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
            help="Half the front track width."
        )
        front_rc = _calc_front_rc_height(
            f_lca_len, f_uca_len,
            f_lca_inner_h, f_lca_outer_h,
            f_uca_inner_h, f_uca_outer_h,
            f_spindle_h
        )
        st.divider()
        st.markdown("### Rear Suspension")
        st.caption("Trailing Arms + Upper Link")
        r1, r2, r3 = st.columns(3)
        with r1:
            st.markdown("**Trailing Arms**")
            r_ta_length = st.number_input(
                "Trailing Arm Length (in)", min_value=0.0, value=28.0,
                step=0.25, key="r_ta_len",
                help="Length of trailing arm from frame pivot to axle mount"
            )
            r_ta_frame_h = st.number_input(
                "Frame Mount Height (in)", value=8.0,
                step=0.25, key="r_ta_frame_h",
                help="Height of trailing arm frame pivot from ground"
            )
            r_ta_axle_h = st.number_input(
                "Axle Mount Height (in)", value=8.0,
                step=0.25, key="r_ta_axle_h",
                help="Height of trailing arm mount on axle housing from ground"
            )
        with r2:
            st.markdown("**Upper Link**")
            r_ul_length = st.number_input(
                "Upper Link Length (in)", min_value=0.0, value=12.0,
                step=0.25, key="r_ul_len",
                help="Length of the upper link / 3rd link / pull bar"
            )
            r_ul_frame_h = st.number_input(
                "Frame Mount Height (in)", value=18.0,
                step=0.25, key="r_ul_frame_h",
                help="Height of upper link chassis-side mount from ground"
            )
            r_ul_axle_h = st.number_input(
                "Axle Mount Height (in)", value=16.0,
                step=0.25, key="r_ul_axle_h",
                help="Height of upper link axle-side mount from ground"
            )
        with r3:
            st.markdown("**Lateral Position**")
            r_ul_frame_offset = st.number_input(
                "Frame Mount Offset from CL (in)", value=2.0,
                step=0.25, key="r_ul_frame_x",
                help="Lateral distance of chassis mount from car centreline"
            )
            r_ul_axle_offset = st.number_input(
                "Axle Mount Offset from CL (in)", value=6.0,
                step=0.25, key="r_ul_axle_x",
                help="Lateral distance of axle mount from car centreline"
            )
            r_track_half = st.number_input(
                "Rear Track Half-Width (in)", min_value=1.0, value=30.0,
                step=0.5, key="r_half_track",
                help="Half the rear track width"
            )
        rear_rc = _calc_rear_rc_height(
            r_ul_frame_h, r_ul_axle_h,
            r_ul_frame_offset, r_ul_axle_offset
        )
        st.divider()
        rc_diff = round(rear_rc - front_rc, 3)
        st.markdown("### Calculated Roll Centre Heights")
        res1, res2, res3 = st.columns(3)
        with res1:
            st.metric("Front Roll Centre", f"{front_rc:.3f} in")
        with res2:
            st.metric("Rear Roll Centre", f"{rear_rc:.3f} in")
        with res3:
            delta_label = "Rear higher" if rc_diff > 0 else ("Front higher" if rc_diff < 0 else "Equal")
            st.metric("RC Diff (Rear - Front)", f"{rc_diff:.3f} in", delta=delta_label)
        # --- Roll Centre Diagram ---
        st.divider()
        st.markdown("### Roll Centre Diagram")
        fig = _draw_rc_diagram(front_rc, rear_rc)
        st.pyplot(fig)
        plt.close(fig)
        st.divider()
        notes = st.text_area("Notes", key="rc_notes", placeholder="Setup notes, track conditions, etc.")
        if st.button("Save to Log", type="primary", use_container_width=True):
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
                "r_trailing_arm_length": r_ta_length,
                "r_trailing_arm_frame_height": r_ta_frame_h,
                "r_trailing_arm_axle_height": r_ta_axle_h,
                "r_upper_link_length": r_ul_length,
                "r_upper_link_frame_height": r_ul_frame_h,
                "r_upper_link_axle_height": r_ul_axle_h,
                "r_upper_link_frame_offset": r_ul_frame_offset,
                "r_upper_link_axle_offset": r_ul_axle_offset,
                "r_rear_track_half": r_track_half,
                "front_rc_height": front_rc,
                "rear_rc_height": rear_rc,
                "rc_height_diff": rc_diff,
            }
            append_row("roll_centres", row)
            st.success(f"Saved! Front RC: {front_rc:.3f} in | Rear RC: {rear_rc:.3f} in")
            st.rerun()
    with tab_log:
        st.subheader("Roll Centre Log")
        df = read_sheet("roll_centres")
        if df.empty:
            st.info("No roll centre entries logged yet. Use the Calculate tab to add your first entry.")
        else:
            chassis_filter = st.selectbox(
                "Filter by Chassis", ["All"] + chassis_list, key="rc_log_filter"
            )
            if chassis_filter != "All":
                df = df[df["chassis"] == chassis_filter]
            display_cols = [c for c in [
                "chassis", "date", "track",
                "front_rc_height", "rear_rc_height", "rc_height_diff", "notes"
            ] if c in df.columns]
            st.dataframe(df[display_cols], use_container_width=True, hide_index=True)
            st.divider()
            st.markdown("#### Delete Entry")
            row_nums = list(range(1, len(df) + 1))
            del_row = st.selectbox(
                "Select row number to delete",
                row_nums,
                format_func=lambda x: (
                    f"Row {x}: "
                    f"{df.iloc[x-1].get('chassis','') if 'chassis' in df.columns else ''}"
                    f" - {df.iloc[x-1].get('date','') if 'date' in df.columns else ''}"
                ),
                key="rc_del_row"
            )
            if st.button("Delete Selected Entry", key="rc_del_btn"):
                delete_row("roll_centres", del_row + 1)
                st.success("Entry deleted.")
                st.rerun()
