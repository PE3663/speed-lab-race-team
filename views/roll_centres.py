import streamlit as st
import pandas as pd
import math
import numpy as np
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


# ---------------------------------------------------------------------------
#  FRONT GEOMETRY  (double A-arm, front-view instant-centre method)
# ---------------------------------------------------------------------------

def _front_view_ic(lca_len, uca_len, lca_inner_h, lca_outer_h,
                   uca_inner_h, uca_outer_h, half_track, bump_in=0.0):
    """Compute the front-view Instant Centre from A-arm geometry.

    The inner pivots sit at x = INNER_X from the centreline (frame rail width).
    The outer pivots sit at x = half_track (centre of the tire contact patch).
    Returns dict with ic_x, ic_y, rc_y, fvsa, camber, lca_outer_h, uca_outer_h.
    """
    INNER_X = 4.0                       # frame-rail half-width (inches)
    outer_x = half_track

    lo_h = lca_outer_h + bump_in
    uo_h = uca_outer_h + bump_in * 0.85  # UCA moves less due to shorter arm

    # Direction vectors for each arm  (inner -> outer)
    lca_dx = outer_x - INNER_X
    lca_dy = lo_h - lca_inner_h
    uca_dx = outer_x - INNER_X          # same horizontal span
    uca_dy = uo_h - uca_inner_h

    # Because both arms share the same dx, the lines are:
    #   LCA:  y = lca_inner_h + (lca_dy/lca_dx)*(x - INNER_X)
    #   UCA:  y = uca_inner_h + (uca_dy/uca_dx)*(x - INNER_X)
    # They intersect where lca_dy/lca_dx == uca_dy/uca_dx  => parallel (no IC).
    # Otherwise solve for x:
    #   lca_inner_h + m_lca*(x-INNER_X) = uca_inner_h + m_uca*(x-INNER_X)
    #   (m_lca - m_uca)*(x - INNER_X) = uca_inner_h - lca_inner_h

    ic_x = ic_y = rc_y = fvsa = camber_deg = None

    if abs(lca_dx) < 1e-9:
        return dict(ic_x=None, ic_y=None, rc_y=None, fvsa=None,
                    camber=0.0, lca_outer_h=lo_h, uca_outer_h=uo_h)

    m_lca = lca_dy / lca_dx
    m_uca = uca_dy / uca_dx

    slope_diff = m_lca - m_uca
    if abs(slope_diff) < 1e-9:          # parallel arms => IC at infinity
        return dict(ic_x=None, ic_y=None, rc_y=0.0, fvsa=None,
                    camber=0.0, lca_outer_h=lo_h, uca_outer_h=uo_h)

    ic_x = INNER_X + (uca_inner_h - lca_inner_h) / slope_diff
    ic_y = lca_inner_h + m_lca * (ic_x - INNER_X)

    # Roll Centre: line from tire contact patch (half_track, 0) through IC
    # to the centreline (x = 0).
    contact_x = half_track
    dx_ic = ic_x - contact_x
    dy_ic = ic_y - 0.0
    if abs(dx_ic) > 1e-9:
        t_cl = (0.0 - contact_x) / dx_ic
        rc_y = 0.0 + t_cl * dy_ic
    else:
        rc_y = ic_y  # IC directly above contact patch

    # FVSA length  (contact patch to IC)
    fvsa = math.sqrt(dx_ic ** 2 + dy_ic ** 2)

    # Camber angle (difference between arm angles)
    lca_angle = math.atan2(lca_dy, lca_dx)
    uca_angle = math.atan2(uca_dy, uca_dx)
    camber_deg = round(math.degrees(uca_angle - lca_angle), 3)

    return dict(
        ic_x=round(ic_x, 2), ic_y=round(ic_y, 2),
        rc_y=round(rc_y, 3),
        fvsa=round(fvsa, 2) if fvsa else None,
        camber=camber_deg,
        lca_outer_h=lo_h, uca_outer_h=uo_h,
    )


def _calc_front_rc_height(lca_len, uca_len, lca_inner_h, lca_outer_h,
                          uca_inner_h, uca_outer_h, half_track):
    """Return front roll-centre height using the same IC method as the diagram."""
    geo = _front_view_ic(lca_len, uca_len, lca_inner_h, lca_outer_h,
                         uca_inner_h, uca_outer_h, half_track, bump_in=0.0)
    if geo["rc_y"] is not None:
        return geo["rc_y"]
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


def _calc_spring_rate(weight_on_wheel, desired_freq, motion_ratio=1.0):
    try:
        if weight_on_wheel <= 0 or desired_freq <= 0:
            return 0.0
        mass = weight_on_wheel / 386.4
        k_wheel = (2 * math.pi * desired_freq) ** 2 * mass
        k_spring = k_wheel / (motion_ratio ** 2) if motion_ratio > 0 else k_wheel
        return round(k_spring, 1)
    except Exception:
        return 0.0


def _calc_wheel_rate(spring_rate, motion_ratio=1.0):
    try:
        return round(spring_rate * (motion_ratio ** 2), 1)
    except Exception:
        return 0.0


def _calc_ride_frequency(spring_rate, weight_on_wheel, motion_ratio=1.0):
    try:
        if weight_on_wheel <= 0 or spring_rate <= 0:
            return 0.0
        mass = weight_on_wheel / 386.4
        k_wheel = spring_rate * (motion_ratio ** 2)
        freq = (1 / (2 * math.pi)) * math.sqrt(k_wheel / mass)
        return round(freq, 2)
    except Exception:
        return 0.0


def _calc_camber_gain(lca_len, uca_len, lca_inner_h, lca_outer_h,
                     uca_inner_h, uca_outer_h, half_track,
                     travel_range=3.0, steps=13):
    """Return list of (travel, camber_change) using the unified IC function."""
    results = []
    try:
        base = _front_view_ic(lca_len, uca_len, lca_inner_h, lca_outer_h,
                              uca_inner_h, uca_outer_h, half_track, bump_in=0.0)
        base_camber = base["camber"] or 0.0
        for i in range(steps):
            travel = -travel_range + (2 * travel_range * i / (steps - 1))
            geo = _front_view_ic(lca_len, uca_len, lca_inner_h, lca_outer_h,
                                 uca_inner_h, uca_outer_h, half_track,
                                 bump_in=travel)
            new_camber = geo["camber"] or 0.0
            camber_change = round(new_camber - base_camber, 3)
            results.append((round(travel, 2), camber_change))
    except Exception:
        results = [(0, 0)]
    return results


# ---------------------------------------------------------------------------
#  DIAGRAM: Side-view Roll Centre + Roll Axis
# ---------------------------------------------------------------------------

def _draw_rc_diagram(front_rc, rear_rc, roll_deg=0.0, dive_deg=0.0):
    bg = "#0e1117"; card_bg = "#1a1e2e"; ground_color = "#3a3f4b"
    car_color = "#cc0000"; car_outline = "#ff3333"
    front_color = "#00d4ff"; rear_color = "#ff6b35"
    axis_color = "#ffd700"; text_color = "#e0e0e0"; grid_color = "#2a2e3a"
    wheelbase = 108

    fig, ax = plt.subplots(figsize=(10, 4.5))
    fig.patch.set_facecolor(bg); ax.set_facecolor(card_bg)
    ax.axhline(y=0, color=ground_color, linewidth=2.5, zorder=1)
    ax.fill_between([-15, wheelbase + 15], -2, 0,
                    color=ground_color, alpha=0.15, zorder=0)

    max_h = max(abs(front_rc), abs(rear_rc), 10) + 5
    for h in range(0, int(max_h) + 5, 5):
        if h > 0:
            ax.axhline(y=h, color=grid_color, linewidth=0.5,
                       linestyle="--", alpha=0.4, zorder=0)

    wheel_r = 5
    for wx in [0, wheelbase]:
        circle = plt.Circle((wx, wheel_r), wheel_r, fill=False,
                            color="#666", linewidth=2, zorder=3)
        ax.add_patch(circle)
        inner = plt.Circle((wx, wheel_r), 2.5, fill=True,
                           color="#444", linewidth=1, zorder=3)
        ax.add_patch(inner)

    body_y = wheel_r * 2
    body = patches.FancyBboxPatch((-5, body_y), wheelbase + 10, 10,
                                  boxstyle="round,pad=2",
                                  facecolor=car_color, edgecolor=car_outline,
                                  alpha=0.25, linewidth=1.5, zorder=2)
    ax.add_patch(body)

    dive_shift_front = dive_deg * 0.3
    dive_shift_rear = -dive_deg * 0.3
    roll_shift = roll_deg * 0.15
    eff_front_rc = front_rc + dive_shift_front + roll_shift
    eff_rear_rc = rear_rc + dive_shift_rear - roll_shift

    ax.plot(0, eff_front_rc, "o", color=front_color, markersize=14, zorder=5,
            markeredgecolor="white", markeredgewidth=1.5)
    ax.plot(wheelbase, eff_rear_rc, "o", color=rear_color, markersize=14,
            zorder=5, markeredgecolor="white", markeredgewidth=1.5)
    ax.plot([0, wheelbase], [eff_front_rc, eff_rear_rc],
            color=axis_color, linewidth=2.5, linestyle="-", zorder=4, alpha=0.9)

    extend = 15
    if wheelbase > 0:
        slope = (eff_rear_rc - eff_front_rc) / wheelbase
        ax.plot([-extend, 0],
                [eff_front_rc - slope * extend, eff_front_rc],
                color=axis_color, linewidth=1, linestyle=":", alpha=0.4, zorder=4)
        ax.plot([wheelbase, wheelbase + extend],
                [eff_rear_rc, eff_rear_rc + slope * extend],
                color=axis_color, linewidth=1, linestyle=":", alpha=0.4, zorder=4)

    ax.plot([0, 0], [0, eff_front_rc],
            color=front_color, linewidth=1.2, linestyle="--", alpha=0.5, zorder=4)
    ax.plot([wheelbase, wheelbase], [0, eff_rear_rc],
            color=rear_color, linewidth=1.2, linestyle="--", alpha=0.5, zorder=4)

    f_offset = 2.5 if eff_front_rc >= 0 else -3.5
    r_offset = 2.5 if eff_rear_rc >= 0 else -3.5
    ax.annotate(f"FRONT RC\n{eff_front_rc:.3f}\"",
                xy=(0, eff_front_rc),
                xytext=(-12, eff_front_rc + f_offset),
                fontsize=9, fontweight="bold", color=front_color,
                ha="center", va="bottom",
                arrowprops=dict(arrowstyle="->", color=front_color, lw=1.2,
                                connectionstyle="arc3,rad=0.2"),
                zorder=6,
                bbox=dict(boxstyle="round,pad=0.3", facecolor=card_bg,
                          edgecolor=front_color, alpha=0.85))
    ax.annotate(f"REAR RC\n{eff_rear_rc:.3f}\"",
                xy=(wheelbase, eff_rear_rc),
                xytext=(wheelbase + 12, eff_rear_rc + r_offset),
                fontsize=9, fontweight="bold", color=rear_color,
                ha="center", va="bottom",
                arrowprops=dict(arrowstyle="->", color=rear_color, lw=1.2,
                                connectionstyle="arc3,rad=-0.2"),
                zorder=6,
                bbox=dict(boxstyle="round,pad=0.3", facecolor=card_bg,
                          edgecolor=rear_color, alpha=0.85))

    mid_x = wheelbase / 2
    mid_y = (eff_front_rc + eff_rear_rc) / 2
    ax.text(mid_x, mid_y + 3,
            f"ROLL AXIS ({abs(eff_rear_rc - eff_front_rc):.3f}\" diff)",
            fontsize=8, color=axis_color, ha="center", va="bottom",
            fontstyle="italic", fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.25", facecolor=card_bg,
                      edgecolor=axis_color, alpha=0.7), zorder=6)

    ax.text(0, -3.5, "FRONT", fontsize=9, color=text_color,
            ha="center", fontweight="bold", zorder=6)
    ax.text(wheelbase, -3.5, "REAR", fontsize=9, color=text_color,
            ha="center", fontweight="bold", zorder=6)
    ax.text(-15, -0.3, "GROUND", fontsize=7, color=ground_color,
            ha="left", va="top", fontstyle="italic", zorder=6)

    if abs(dive_deg) > 0.01 or abs(roll_deg) > 0.01:
        info = []
        if abs(dive_deg) > 0.01:
            info.append(f"Dive: {dive_deg:+.1f}")
        if abs(roll_deg) > 0.01:
            info.append(f"Roll: {roll_deg:+.1f}")
        ax.text(wheelbase + 20, -3.5, " | ".join(info),
                fontsize=7, color="#888", ha="right", va="top",
                fontstyle="italic", zorder=6)

    ax.set_xlim(-25, wheelbase + 25)
    y_lo = min(eff_front_rc, eff_rear_rc, 0) - 6
    y_hi = max(eff_front_rc, eff_rear_rc, max_h) + 8
    ax.set_ylim(y_lo, y_hi); ax.set_aspect("auto")
    ax.set_xlabel("Side View (inches)", color=text_color, fontsize=8)
    ax.set_ylabel("Height (inches)", color=text_color, fontsize=8)
    ax.tick_params(colors=text_color, labelsize=7)
    for spine in ax.spines.values():
        spine.set_color(grid_color)
    plt.tight_layout()
    return fig


# ---------------------------------------------------------------------------
#  DIAGRAM: Front-view IC + RC construction
# ---------------------------------------------------------------------------

def _draw_front_view_rc(lca_len, uca_len, lca_inner_h, lca_outer_h,
                        uca_inner_h, uca_outer_h, half_track,
                        front_rc, bump_in=0.0):
    bg = "#0e1117"; card_bg = "#1a1e2e"; ground_color = "#3a3f4b"
    lca_color = "#00d4ff"; uca_color = "#ff6b35"; ic_color = "#ffd700"
    rc_color = "#00ff88"; text_color = "#e0e0e0"; grid_color = "#2a2e3a"
    tire_color = "#555555"; fvsa_color = "#ff55ff"

    INNER_X = 4.0
    outer_x = half_track
    geo = _front_view_ic(lca_len, uca_len, lca_inner_h, lca_outer_h,
                         uca_inner_h, uca_outer_h, half_track, bump_in)
    lo_h = geo["lca_outer_h"]; uo_h = geo["uca_outer_h"]

    fig, ax = plt.subplots(figsize=(10, 7))
    fig.patch.set_facecolor(bg); ax.set_facecolor(card_bg)
    ax.axhline(y=0, color=ground_color, linewidth=2.5, zorder=1)

    max_h = max(uca_inner_h, uo_h, 20) + 5
    for h in range(0, int(max_h) + 5, 5):
        if h > 0:
            ax.axhline(y=h, color=grid_color, linewidth=0.5,
                       linestyle="--", alpha=0.3, zorder=0)
    ax.axvline(x=0, color=grid_color, linewidth=1, linestyle="-.",
               alpha=0.5, zorder=1)
    ax.text(0.5, max_h - 1, "CL", fontsize=8, color=grid_color,
            ha="left", va="top", fontstyle="italic", zorder=6)

    # Tires
    tire_w = 4; tire_h = 10
    tire_x = half_track - tire_w / 2
    for sign in [1, -1]:
        tx = tire_x * sign if sign == 1 else -tire_x - tire_w
        tire = patches.FancyBboxPatch((tx, 0), tire_w, tire_h,
                                      boxstyle="round,pad=0.5",
                                      facecolor=tire_color, edgecolor="#777",
                                      alpha=0.5, linewidth=1.5, zorder=2)
        ax.add_patch(tire)

    # Frame box
    frame_w = INNER_X * 2 + 4; frame_h = uca_inner_h - lca_inner_h + 4
    frame = patches.FancyBboxPatch((-frame_w / 2, lca_inner_h - 2),
                                    frame_w, frame_h,
                                    boxstyle="round,pad=1",
                                    facecolor="#cc0000", edgecolor="#ff3333",
                                    alpha=0.2, linewidth=1.5, zorder=2)
    ax.add_patch(frame)

    # Right-side arms
    ax.plot([INNER_X, outer_x], [lca_inner_h, lo_h],
            color=lca_color, linewidth=2.5, zorder=4, label="LCA")
    ax.plot(INNER_X, lca_inner_h, "o", color=lca_color, markersize=8, zorder=5,
            markeredgecolor="white", markeredgewidth=1)
    ax.plot(outer_x, lo_h, "o", color=lca_color, markersize=8, zorder=5,
            markeredgecolor="white", markeredgewidth=1)

    ax.plot([INNER_X, outer_x], [uca_inner_h, uo_h],
            color=uca_color, linewidth=2.5, zorder=4, label="UCA")
    ax.plot(INNER_X, uca_inner_h, "o", color=uca_color, markersize=8, zorder=5,
            markeredgecolor="white", markeredgewidth=1)
    ax.plot(outer_x, uo_h, "o", color=uca_color, markersize=8, zorder=5,
            markeredgecolor="white", markeredgewidth=1)

    # Left-side arms (mirrored, dimmed)
    ax.plot([-INNER_X, -outer_x], [lca_inner_h, lo_h],
            color=lca_color, linewidth=2.5, alpha=0.4, zorder=4)
    ax.plot([-INNER_X, -outer_x], [uca_inner_h, uo_h],
            color=uca_color, linewidth=2.5, alpha=0.4, zorder=4)
    for px, py in [(-INNER_X, lca_inner_h), (-outer_x, lo_h),
                   (-INNER_X, uca_inner_h), (-outer_x, uo_h)]:
        ax.plot(px, py, "o", color="#888", markersize=6, alpha=0.4, zorder=5)

    # IC construction + FVSA
    ic_x = geo["ic_x"]; ic_y = geo["ic_y"]; rc_y = geo["rc_y"]
    fvsa = geo["fvsa"]

    if ic_x is not None:
        ax.plot([INNER_X, ic_x], [lca_inner_h, ic_y],
                color=lca_color, linewidth=1, linestyle="--", alpha=0.5, zorder=3)
        ax.plot([INNER_X, ic_x], [uca_inner_h, ic_y],
                color=uca_color, linewidth=1, linestyle="--", alpha=0.5, zorder=3)

        ax.plot(ic_x, ic_y, "D", color=ic_color, markersize=12, zorder=6,
                markeredgecolor="white", markeredgewidth=1.5)
        ax.annotate(f"IC\n({ic_x:.1f}, {ic_y:.1f})",
                    xy=(ic_x, ic_y),
                    xytext=(ic_x - 10, ic_y + 3),
                    fontsize=8, fontweight="bold", color=ic_color,
                    ha="center", va="bottom",
                    arrowprops=dict(arrowstyle="->", color=ic_color, lw=1),
                    zorder=7,
                    bbox=dict(boxstyle="round,pad=0.3", facecolor=card_bg,
                              edgecolor=ic_color, alpha=0.85))

        # FVSA line (contact patch to IC)
        contact_x = half_track
        fvsa_label = f"FVSA ({fvsa:.1f} in)" if fvsa else "FVSA"
        ax.plot([contact_x, ic_x], [0, ic_y],
                color=fvsa_color, linewidth=2, linestyle="-",
                alpha=0.6, zorder=4, label=fvsa_label)

        # Line from contact patch through IC to centreline
        ax.plot([contact_x, 0], [0, rc_y],
                color=rc_color, linewidth=2, linestyle="-",
                alpha=0.8, zorder=4)

        # RC marker
        ax.plot(0, rc_y, "o", color=rc_color, markersize=14, zorder=6,
                markeredgecolor="white", markeredgewidth=2)
        ax.annotate(f"ROLL CENTRE\n{rc_y:.3f}\"",
                    xy=(0, rc_y),
                    xytext=(-12, rc_y + 4),
                    fontsize=9, fontweight="bold", color=rc_color,
                    ha="center", va="bottom",
                    arrowprops=dict(arrowstyle="->", color=rc_color, lw=1.2,
                                    connectionstyle="arc3,rad=0.2"),
                    zorder=7,
                    bbox=dict(boxstyle="round,pad=0.3", facecolor=card_bg,
                              edgecolor=rc_color, alpha=0.85))
    else:
        ax.plot(0, 0, "o", color=rc_color, markersize=14, zorder=6,
                markeredgecolor="white", markeredgewidth=2)
        ax.text(-12, 2, "RC at ground (parallel arms)", fontsize=8,
                color=rc_color, ha="center", zorder=7)

    # Contact patches
    for side_key in ["R", "L"]:
        cx = half_track if side_key == "R" else -half_track
        ax.plot(cx, 0, "^", color="#aaa", markersize=10, zorder=5,
                markeredgecolor="white", markeredgewidth=1)
        ax.text(cx, -1.5, "Contact\nPatch", fontsize=7, color="#aaa",
                ha="center", va="top", zorder=6)

    # Bump info
    if abs(bump_in) > 0.001:
        ax.text(0, -3.5, f"Bump: {bump_in:+.2f}\"",
                fontsize=8, color="#ffaa00", ha="center",
                fontstyle="italic", fontweight="bold", zorder=6)
    else:
        ax.text(0, -3.5, "VIEW: Looking from behind front wheels",
                fontsize=8, color=text_color, ha="center",
                fontstyle="italic", zorder=6)

    ax.legend(loc="upper right", facecolor=card_bg, edgecolor=grid_color,
              labelcolor=text_color, fontsize=8)

    margin = 8
    ax.set_xlim(-half_track - margin, half_track + margin)
    y_lo = -5; y_hi_val = max_h + 5
    if ic_y is not None:
        y_hi_val = max(y_hi_val, ic_y + 8)
    ax.set_ylim(y_lo, y_hi_val); ax.set_aspect("equal")
    ax.set_xlabel("Lateral Position (inches)", color=text_color, fontsize=8)
    ax.set_ylabel("Height (inches)", color=text_color, fontsize=8)
    ax.set_title("Front View \u2014 Instant Centre Construction",
                 color=text_color, fontsize=11, fontweight="bold")
    ax.tick_params(colors=text_color, labelsize=7)
    for spine in ax.spines.values():
        spine.set_color(grid_color)
    plt.tight_layout()
    return fig, geo


# ---------------------------------------------------------------------------
#  RENDER
# ---------------------------------------------------------------------------

def render():
    st.title("Roll Centres")
    st.caption("Calculate and track front and rear roll centre heights for each chassis.")

    chassis_list = get_chassis_list()
    if not chassis_list:
        st.warning("No chassis found. Please add a chassis in Chassis Profiles first.")
        return

    _ensure_headers()

    tab_calc, tab_springs, tab_camber, tab_compare, tab_log = st.tabs([
        "Calculate", "Spring Rates", "Camber Gain", "Compare Setups", "Log / History"
    ])

    # ================================================================
    #  CALCULATE TAB
    # ================================================================
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
            f_lca_len = st.number_input("LCA Length (in)", min_value=0.0, value=12.0,
                step=0.125, key="f_lca_len",
                help="Length of the lower control arm from inner pivot (frame) to outer ball joint (spindle)")
            f_uca_len = st.number_input("UCA Length (in)", min_value=0.0, value=10.0,
                step=0.125, key="f_uca_len",
                help="Length of the upper control arm from inner pivot (frame) to outer ball joint (spindle)")
        with f2:
            f_lca_inner_h = st.number_input("LCA Inner Height (in)", value=6.0,
                step=0.125, key="f_lca_inner_h",
                help="Height of the LCA frame-side pivot point measured from the ground")
            f_lca_outer_h = st.number_input("LCA Outer Height (in)", value=5.5,
                step=0.125, key="f_lca_outer_h",
                help="Height of the LCA spindle-side ball joint measured from the ground")
        with f3:
            f_uca_inner_h = st.number_input("UCA Inner Height (in)", value=14.0,
                step=0.125, key="f_uca_inner_h",
                help="Height of the UCA frame-side pivot point measured from the ground")
            f_uca_outer_h = st.number_input("UCA Outer Height (in)", value=13.0,
                step=0.125, key="f_uca_outer_h",
                help="Height of the UCA spindle-side ball joint measured from the ground")

        f_spindle_h = st.number_input(
            "Front Track Half-Width / Spindle Offset (in)",
            min_value=1.0, value=30.0, step=0.5, key="f_spindle_h",
            help="Half the front track width. Distance from car centreline to the centre of the tire contact patch.")

        front_rc = _calc_front_rc_height(
            f_lca_len, f_uca_len,
            f_lca_inner_h, f_lca_outer_h,
            f_uca_inner_h, f_uca_outer_h,
            f_spindle_h)

        st.divider()
        st.markdown("### Rear Suspension")
        st.caption("Trailing Arms + Upper Link")

        r1, r2, r3 = st.columns(3)
        with r1:
            st.markdown("**Trailing Arms**")
            r_ta_length = st.number_input("Trailing Arm Length (in)",
                min_value=0.0, value=28.0, step=0.25, key="r_ta_len",
                help="Length of trailing arm from frame pivot to axle mount")
            r_ta_frame_h = st.number_input("Frame Mount Height (in)",
                value=8.0, step=0.25, key="r_ta_frame_h",
                help="Height of trailing arm frame pivot from ground")
            r_ta_axle_h = st.number_input("Axle Mount Height (in)",
                value=8.0, step=0.25, key="r_ta_axle_h",
                help="Height of trailing arm mount on axle housing from ground")
        with r2:
            st.markdown("**Upper Link**")
            r_ul_length = st.number_input("Upper Link Length (in)",
                min_value=0.0, value=12.0, step=0.25, key="r_ul_len",
                help="Length of the upper link / 3rd link / pull bar")
            r_ul_frame_h = st.number_input("Frame Mount Height (in)",
                value=18.0, step=0.25, key="r_ul_frame_h",
                help="Height of upper link chassis-side mount from ground")
            r_ul_axle_h = st.number_input("Axle Mount Height (in)",
                value=16.0, step=0.25, key="r_ul_axle_h",
                help="Height of upper link axle-side mount from ground")
        with r3:
            st.markdown("**Lateral Position**")
            r_ul_frame_offset = st.number_input(
                "Frame Mount Offset from CL (in)", value=2.0, step=0.25,
                key="r_ul_frame_x",
                help="Lateral distance of chassis mount from car centreline")
            r_ul_axle_offset = st.number_input(
                "Axle Mount Offset from CL (in)", value=6.0, step=0.25,
                key="r_ul_axle_x",
                help="Lateral distance of axle mount from car centreline")
            r_track_half = st.number_input("Rear Track Half-Width (in)",
                min_value=1.0, value=30.0, step=0.5, key="r_half_track",
                help="Half the rear track width")

        rear_rc = _calc_rear_rc_height(
            r_ul_frame_h, r_ul_axle_h,
            r_ul_frame_offset, r_ul_axle_offset)

        st.divider()
        rc_diff = round(rear_rc - front_rc, 3)

        st.markdown("### Calculated Roll Centre Heights")
        res1, res2, res3 = st.columns(3)
        with res1:
            st.metric("Front Roll Centre", f"{front_rc:.3f} in")
        with res2:
            st.metric("Rear Roll Centre", f"{rear_rc:.3f} in")
        with res3:
            delta_label = ("Rear higher" if rc_diff > 0
                           else ("Front higher" if rc_diff < 0 else "Equal"))
            st.metric("RC Diff (Rear - Front)", f"{rc_diff:.3f} in",
                      delta=delta_label)

        # -- Dive / Roll sliders --
        st.divider()
        st.markdown("### Dive / Roll Simulation")
        st.caption("Use the sliders to visualise how body dive (braking) "
                   "and roll (cornering) shift the effective roll centre positions.")
        sl1, sl2 = st.columns(2)
        with sl1:
            dive_deg = st.slider("Body Dive Angle", min_value=-5.0,
                max_value=5.0, value=0.0, step=0.25, key="rc_dive",
                help="Positive = nose down (braking). Negative = nose up (acceleration).")
        with sl2:
            roll_deg = st.slider("Body Roll Angle", min_value=-5.0,
                max_value=5.0, value=0.0, step=0.25, key="rc_roll",
                help="Positive = roll right. Negative = roll left.")

        # -- Side-view diagram --
        st.divider()
        st.markdown("### Roll Centre Diagram")
        fig = _draw_rc_diagram(front_rc, rear_rc,
                               roll_deg=roll_deg, dive_deg=dive_deg)
        st.pyplot(fig); plt.close(fig)

        # -- Front-view diagram --
        st.divider()
        st.markdown("### Front View \u2014 Instant Centre & FVSA")
        st.caption(
            "Slide the bump/droop slider to see how wheel travel changes "
            "the Instant Centre, Roll Centre, FVSA length, and camber in real time."
        )
        bump_in = st.slider("Wheel Travel (Bump / Droop)",
            min_value=-3.0, max_value=3.0, value=0.0, step=0.125,
            key="fv_bump",
            help="Positive = bump (compression). Negative = droop (extension).")

        fig_fv, geo = _draw_front_view_rc(
            f_lca_len, f_uca_len,
            f_lca_inner_h, f_lca_outer_h,
            f_uca_inner_h, f_uca_outer_h,
            f_spindle_h, front_rc, bump_in=bump_in)
        st.pyplot(fig_fv); plt.close(fig_fv)

        # Live metrics
        m1, m2, m3, m4 = st.columns(4)
        with m1:
            if geo["ic_x"] is not None and geo["ic_y"] is not None:
                st.metric("IC Position",
                          f"({geo['ic_x']:.1f}, {geo['ic_y']:.1f})")
            else:
                st.metric("IC Position", "-- (parallel)")
        with m2:
            fvsa_val = f"{geo['fvsa']:.1f} in" if geo["fvsa"] is not None else "--"
            st.metric("FVSA Length", fvsa_val)
        with m3:
            rc_val = f"{geo['rc_y']:.3f} in" if geo["rc_y"] is not None else "--"
            st.metric("Roll Centre Height", rc_val)
        with m4:
            st.metric("Camber Change", f"{geo['camber']:.3f} deg")

        # -- Save --
        st.divider()
        notes = st.text_area("Notes", key="rc_notes",
                             placeholder="Setup notes, track conditions, etc.")
        if st.button("Save to Log", type="primary", use_container_width=True):
            row = {
                "chassis": chassis, "date": date_val, "track": track,
                "notes": notes,
                "f_lca_length": f_lca_len, "f_uca_length": f_uca_len,
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

    # ================================================================
    #  SPRING RATES TAB
    # ================================================================
    with tab_springs:
        st.subheader("Spring Rate Calculator")
        st.markdown("Calculate required spring rates from corner weights and "
                    "desired ride frequency, or find the ride frequency from "
                    "a known spring rate.")

        mode = st.radio("Calculation Mode",
            ["Find Spring Rate from Frequency",
             "Find Frequency from Spring Rate"],
            horizontal=True, key="spring_mode")
        st.divider()

        sc1, sc2 = st.columns(2)
        with sc1:
            st.markdown("**Front**")
            f_corner_wt = st.number_input("Front Corner Weight (lbs)",
                min_value=0.0, value=400.0, step=5.0, key="f_corner_wt",
                help="Weight on one front wheel (total front weight / 2)")
            f_motion_ratio = st.number_input("Front Motion Ratio",
                min_value=0.01, value=1.0, step=0.05, key="f_mr",
                help="Wheel travel / spring travel. 1.0 = coilover at wheel.")
        with sc2:
            st.markdown("**Rear**")
            r_corner_wt = st.number_input("Rear Corner Weight (lbs)",
                min_value=0.0, value=450.0, step=5.0, key="r_corner_wt",
                help="Weight on one rear wheel (total rear weight / 2)")
            r_motion_ratio = st.number_input("Rear Motion Ratio",
                min_value=0.01, value=1.0, step=0.05, key="r_mr",
                help="Wheel travel / spring travel. 1.0 = coilover at wheel.")
        st.divider()

        if mode == "Find Spring Rate from Frequency":
            fc1, fc2 = st.columns(2)
            with fc1:
                f_target_freq = st.slider("Front Target Frequency (Hz)",
                    1.0, 4.0, 1.8, 0.05, key="f_target_freq",
                    help="Typical oval: 1.5-2.5 Hz front")
                f_spring = _calc_spring_rate(f_corner_wt, f_target_freq,
                                            f_motion_ratio)
                f_wheel_rate = _calc_wheel_rate(f_spring, f_motion_ratio)
                st.metric("Front Spring Rate", f"{f_spring:.1f} lbs/in")
                st.metric("Front Wheel Rate", f"{f_wheel_rate:.1f} lbs/in")
            with fc2:
                r_target_freq = st.slider("Rear Target Frequency (Hz)",
                    1.0, 4.0, 2.0, 0.05, key="r_target_freq",
                    help="Typical oval: 1.8-3.0 Hz rear")
                r_spring = _calc_spring_rate(r_corner_wt, r_target_freq,
                                            r_motion_ratio)
                r_wheel_rate = _calc_wheel_rate(r_spring, r_motion_ratio)
                st.metric("Rear Spring Rate", f"{r_spring:.1f} lbs/in")
                st.metric("Rear Wheel Rate", f"{r_wheel_rate:.1f} lbs/in")
            st.divider()
            ratio = round(r_spring / f_spring, 3) if f_spring > 0 else 0
            st.metric("Rear / Front Spring Ratio", f"{ratio:.3f}")
        else:
            fc1, fc2 = st.columns(2)
            with fc1:
                f_spring_known = st.number_input(
                    "Front Spring Rate (lbs/in)", min_value=0.0,
                    value=200.0, step=5.0, key="f_spring_known")
                f_freq = _calc_ride_frequency(f_spring_known, f_corner_wt,
                                             f_motion_ratio)
                f_wr = _calc_wheel_rate(f_spring_known, f_motion_ratio)
                st.metric("Front Ride Frequency", f"{f_freq:.2f} Hz")
                st.metric("Front Wheel Rate", f"{f_wr:.1f} lbs/in")
            with fc2:
                r_spring_known = st.number_input(
                    "Rear Spring Rate (lbs/in)", min_value=0.0,
                    value=250.0, step=5.0, key="r_spring_known")
                r_freq = _calc_ride_frequency(r_spring_known, r_corner_wt,
                                             r_motion_ratio)
                r_wr = _calc_wheel_rate(r_spring_known, r_motion_ratio)
                st.metric("Rear Ride Frequency", f"{r_freq:.2f} Hz")
                st.metric("Rear Wheel Rate", f"{r_wr:.1f} lbs/in")
            st.divider()
            ratio = (round(r_spring_known / f_spring_known, 3)
                     if f_spring_known > 0 else 0)
            st.metric("Rear / Front Spring Ratio", f"{ratio:.3f}")

        st.divider()
        with st.expander("Reference: Typical Ride Frequencies"):
            ref_data = {
                "Category": ["Soft (comfort)", "Medium (street/oval)",
                             "Stiff (road course)", "Very Stiff (sprint)"],
                "Front (Hz)": ["1.0 - 1.5", "1.5 - 2.0",
                               "2.0 - 2.5", "2.5 - 3.5"],
                "Rear (Hz)": ["1.2 - 1.7", "1.7 - 2.3",
                              "2.3 - 2.8", "2.8 - 4.0"],
            }
            st.table(pd.DataFrame(ref_data))

    # ================================================================
    #  CAMBER GAIN TAB
    # ================================================================
    with tab_camber:
        st.subheader("Camber Gain Table")
        st.markdown("Estimates how front camber changes as the wheel travels "
                    "through bump and droop (based on the A-arm geometry "
                    "entered in the Calculate tab).")

        cg_range = st.slider("Wheel Travel Range (in)",
            1.0, 6.0, 3.0, 0.5, key="cg_range",
            help="Total travel from full droop to full bump")

        cg_lca_len = st.session_state.get("f_lca_len", 12.0)
        cg_uca_len = st.session_state.get("f_uca_len", 10.0)
        cg_lca_inner = st.session_state.get("f_lca_inner_h", 6.0)
        cg_lca_outer = st.session_state.get("f_lca_outer_h", 5.5)
        cg_uca_inner = st.session_state.get("f_uca_inner_h", 14.0)
        cg_uca_outer = st.session_state.get("f_uca_outer_h", 13.0)
        cg_spindle = st.session_state.get("f_spindle_h", 30.0)

        camber_data = _calc_camber_gain(
            cg_lca_len, cg_uca_len,
            cg_lca_inner, cg_lca_outer,
            cg_uca_inner, cg_uca_outer,
            cg_spindle,
            travel_range=cg_range, steps=13)

        df_camber = pd.DataFrame(camber_data,
            columns=["Wheel Travel (in)", "Camber Change (deg)"])

        cc1, cc2 = st.columns([1, 1])
        with cc1:
            st.dataframe(df_camber, use_container_width=True, hide_index=True)
        with cc2:
            fig_cg, ax_cg = plt.subplots(figsize=(5, 4))
            fig_cg.patch.set_facecolor("#0e1117")
            ax_cg.set_facecolor("#1a1e2e")
            travels = [d[0] for d in camber_data]
            cambers = [d[1] for d in camber_data]
            ax_cg.plot(travels, cambers, color="#00d4ff", linewidth=2.5,
                       marker="o", markersize=5)
            ax_cg.axhline(y=0, color="#3a3f4b", linewidth=1, linestyle="--")
            ax_cg.axvline(x=0, color="#3a3f4b", linewidth=1, linestyle="--")
            ax_cg.fill_between(travels, cambers, 0, alpha=0.15, color="#00d4ff")
            ax_cg.set_xlabel("Wheel Travel (in)", color="#e0e0e0", fontsize=9)
            ax_cg.set_ylabel("Camber Change (deg)", color="#e0e0e0", fontsize=9)
            ax_cg.set_title("Camber Gain Curve", color="#e0e0e0",
                            fontsize=11, fontweight="bold")
            ax_cg.tick_params(colors="#e0e0e0", labelsize=7)
            for spine in ax_cg.spines.values():
                spine.set_color("#2a2e3a")
            plt.tight_layout()
            st.pyplot(fig_cg); plt.close(fig_cg)

        st.caption("Negative camber change in bump (compression) is typical "
                   "and desirable for cornering grip. This is an approximation "
                   "based on the arm geometry.")

    # ================================================================
    #  COMPARE SETUPS TAB
    # ================================================================
    with tab_compare:
        st.subheader("Compare Saved Setups")
        st.markdown("Select two saved log entries to compare their geometry "
                    "and roll centre values side by side.")

        df_all = read_sheet("roll_centres")
        if df_all.empty:
            st.info("No saved entries to compare. Save some setups first.")
        else:
            labels = []
            for i, row in df_all.iterrows():
                ch = row.get("chassis", "")
                dt = row.get("date", "")
                tr = row.get("track", "")
                labels.append(f"{ch} | {dt} | {tr}")
            df_all["_label"] = labels

            cp1, cp2 = st.columns(2)
            with cp1:
                sel_a = st.selectbox("Setup A", range(len(labels)),
                    format_func=lambda x: labels[x], key="cmp_a")
            with cp2:
                sel_b = st.selectbox("Setup B", range(len(labels)),
                    index=min(1, len(labels) - 1),
                    format_func=lambda x: labels[x], key="cmp_b")

            if sel_a is not None and sel_b is not None:
                row_a = df_all.iloc[sel_a]
                row_b = df_all.iloc[sel_b]
                compare_keys = [
                    ("front_rc_height", "Front RC Height (in)"),
                    ("rear_rc_height", "Rear RC Height (in)"),
                    ("rc_height_diff", "RC Diff (in)"),
                    ("f_lca_length", "Front LCA Length"),
                    ("f_uca_length", "Front UCA Length"),
                    ("f_lca_inner_height", "Front LCA Inner H"),
                    ("f_lca_outer_height", "Front LCA Outer H"),
                    ("f_uca_inner_height", "Front UCA Inner H"),
                    ("f_uca_outer_height", "Front UCA Outer H"),
                    ("f_spindle_height", "Front Track Half"),
                    ("r_trailing_arm_length", "Rear Trailing Arm Len"),
                    ("r_trailing_arm_frame_height", "Rear TA Frame H"),
                    ("r_trailing_arm_axle_height", "Rear TA Axle H"),
                    ("r_upper_link_length", "Rear Upper Link Len"),
                    ("r_upper_link_frame_height", "Rear UL Frame H"),
                    ("r_upper_link_axle_height", "Rear UL Axle H"),
                    ("r_upper_link_frame_offset", "Rear UL Frame Offset"),
                    ("r_upper_link_axle_offset", "Rear UL Axle Offset"),
                    ("r_rear_track_half", "Rear Track Half"),
                ]
                cmp_rows = []
                for key, label in compare_keys:
                    val_a = row_a.get(key, "")
                    val_b = row_b.get(key, "")
                    try:
                        va = float(val_a); vb = float(val_b)
                        diff = round(vb - va, 3)
                        diff_str = f"{diff:+.3f}" if diff != 0 else "--"
                    except (ValueError, TypeError):
                        va = val_a; vb = val_b; diff_str = ""
                    cmp_rows.append({"Parameter": label,
                                     "Setup A": va, "Setup B": vb,
                                     "Difference": diff_str})
                st.dataframe(pd.DataFrame(cmp_rows),
                             use_container_width=True, hide_index=True)

                st.divider()
                st.markdown("#### Visual Overlay")
                try:
                    frc_a = float(row_a.get("front_rc_height", 0))
                    rrc_a = float(row_a.get("rear_rc_height", 0))
                    frc_b = float(row_b.get("front_rc_height", 0))
                    rrc_b = float(row_b.get("rear_rc_height", 0))
                except (ValueError, TypeError):
                    frc_a = rrc_a = frc_b = rrc_b = 0

                fig_cmp, ax_cmp = plt.subplots(figsize=(10, 4))
                fig_cmp.patch.set_facecolor("#0e1117")
                ax_cmp.set_facecolor("#1a1e2e")
                wb = 108
                ax_cmp.axhline(y=0, color="#3a3f4b", linewidth=2)
                ax_cmp.plot([0, wb], [frc_a, rrc_a], "o-",
                            color="#00d4ff", linewidth=2.5,
                            markersize=10, label="Setup A")
                ax_cmp.plot([0, wb], [frc_b, rrc_b], "s--",
                            color="#ff6b35", linewidth=2.5,
                            markersize=10, label="Setup B")
                ax_cmp.legend(facecolor="#1a1e2e", edgecolor="#3a3f4b",
                              labelcolor="#e0e0e0", fontsize=9)
                ax_cmp.set_xlabel("Wheelbase (in)", color="#e0e0e0", fontsize=9)
                ax_cmp.set_ylabel("RC Height (in)", color="#e0e0e0", fontsize=9)
                ax_cmp.set_title("Roll Axis Comparison", color="#e0e0e0",
                                 fontsize=11, fontweight="bold")
                ax_cmp.tick_params(colors="#e0e0e0", labelsize=7)
                for spine in ax_cmp.spines.values():
                    spine.set_color("#2a2e3a")
                plt.tight_layout()
                st.pyplot(fig_cmp); plt.close(fig_cmp)

    # ================================================================
    #  LOG / HISTORY TAB
    # ================================================================
    with tab_log:
        st.subheader("Roll Centre Log")
        df = read_sheet("roll_centres")
        if df.empty:
            st.info("No roll centre entries logged yet. "
                    "Use the Calculate tab to add your first entry.")
        else:
            chassis_filter = st.selectbox("Filter by Chassis",
                ["All"] + chassis_list, key="rc_log_filter")
            if chassis_filter != "All":
                df = df[df["chassis"] == chassis_filter]

            display_cols = [c for c in [
                "chassis", "date", "track",
                "front_rc_height", "rear_rc_height",
                "rc_height_diff", "notes"
            ] if c in df.columns]
            st.dataframe(df[display_cols], use_container_width=True,
                         hide_index=True)

            st.divider()
            st.markdown("#### Delete Entry")
            row_nums = list(range(1, len(df) + 1))
            del_row = st.selectbox("Select row number to delete",
                row_nums,
                format_func=lambda x: (
                    f"Row {x}: "
                    f"{df.iloc[x-1].get('chassis','') if 'chassis' in df.columns else ''}"
                    f" - {df.iloc[x-1].get('date','') if 'date' in df.columns else ''}"
                ), key="rc_del_row")
            if st.button("Delete Selected Entry", key="rc_del_btn"):
                delete_row("roll_centres", del_row + 1)
                st.success("Entry deleted.")
                st.rerun()
