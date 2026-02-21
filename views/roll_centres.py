import streamlit as st
import pandas as pd
import math
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import FancyArrowPatch
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
# FRONT GEOMETRY  (double A-arm, front-view instant-centre method)
# ---------------------------------------------------------------------------
def _front_view_ic(lca_len, uca_len, lca_inner_h, lca_outer_h,
                   uca_inner_h, uca_outer_h, half_track, bump_in=0.0):
    INNER_X = 4.0
    outer_x = half_track
    lo_h = lca_outer_h + bump_in
    uo_h = uca_outer_h + bump_in * 0.85
    lca_dx = outer_x - INNER_X
    lca_dy = lo_h - lca_inner_h
    uca_dx = outer_x - INNER_X
    uca_dy = uo_h - uca_inner_h
    ic_x = ic_y = rc_y = fvsa = camber_deg = None
    if abs(lca_dx) < 1e-9:
        return dict(ic_x=None, ic_y=None, rc_y=None, fvsa=None, camber=0.0,
                    lca_outer_h=lo_h, uca_outer_h=uo_h)
    m_lca = lca_dy / lca_dx
    m_uca = uca_dy / uca_dx
    slope_diff = m_lca - m_uca
    if abs(slope_diff) < 1e-9:
        return dict(ic_x=None, ic_y=None, rc_y=0.0, fvsa=None, camber=0.0,
                    lca_outer_h=lo_h, uca_outer_h=uo_h)
    ic_x = INNER_X + (uca_inner_h - lca_inner_h) / slope_diff
    ic_y = lca_inner_h + m_lca * (ic_x - INNER_X)
    contact_x = half_track
    dx_ic = ic_x - contact_x
    dy_ic = ic_y - 0.0
    if abs(dx_ic) > 1e-9:
        t_cl = (0.0 - contact_x) / dx_ic
        rc_y = 0.0 + t_cl * dy_ic
    else:
        rc_y = ic_y
    fvsa = math.sqrt(dx_ic ** 2 + dy_ic ** 2)
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


def _calc_sweep_data(lca_len, uca_len, lca_inner_h, lca_outer_h,
                    uca_inner_h, uca_outer_h, half_track,
                    travel_range=3.0, steps=25):
    """Sweep through bump/droop and collect RC height, FVSA, camber."""
    travels, rc_heights, fvsa_lengths, camber_changes = [], [], [], []
    base = _front_view_ic(lca_len, uca_len, lca_inner_h, lca_outer_h,
                          uca_inner_h, uca_outer_h, half_track, bump_in=0.0)
    base_camber = base["camber"] or 0.0
    for i in range(steps):
        t = -travel_range + (2 * travel_range * i / (steps - 1))
        geo = _front_view_ic(lca_len, uca_len, lca_inner_h, lca_outer_h,
                            uca_inner_h, uca_outer_h, half_track, bump_in=t)
        travels.append(round(t, 3))
        rc_heights.append(geo["rc_y"] if geo["rc_y"] is not None else 0.0)
        fvsa_lengths.append(geo["fvsa"] if geo["fvsa"] is not None else 0.0)
        c = (geo["camber"] or 0.0) - base_camber
        camber_changes.append(round(c, 3))
    return travels, rc_heights, fvsa_lengths, camber_changes


def _draw_sweep_chart(travels, rc_heights, fvsa_lengths, camber_changes):
    """3-panel sweep chart: RC height, FVSA, camber vs wheel travel."""
    bg = "#0e1117"; card_bg = "#1a1e2e"; grid_color = "#2a2e3a"
    text_color = "#e0e0e0"
    fig, axes = plt.subplots(3, 1, figsize=(10, 8), sharex=True)
    fig.patch.set_facecolor(bg)
    panels = [
        (axes[0], rc_heights, "RC Height (in)", "#00ff88", "Roll Centre Height"),
        (axes[1], fvsa_lengths, "FVSA (in)", "#ff55ff", "FVSA Length"),
        (axes[2], camber_changes, "Camber Change (deg)", "#00d4ff", "Camber Change"),
    ]
    for ax, data, ylabel, color, title in panels:
        ax.set_facecolor(card_bg)
        ax.plot(travels, data, color=color, linewidth=2.5, marker="o", markersize=3)
        ax.axhline(y=0, color="#3a3f4b", linewidth=1, linestyle="--")
        ax.axvline(x=0, color="#3a3f4b", linewidth=1, linestyle="--")
        ax.fill_between(travels, data, 0, alpha=0.1, color=color)
        ax.set_ylabel(ylabel, color=text_color, fontsize=8)
        ax.set_title(title, color=text_color, fontsize=9, fontweight="bold", loc="left")
        ax.tick_params(colors=text_color, labelsize=7)
        for spine in ax.spines.values():
            spine.set_color(grid_color)
    axes[2].set_xlabel("Wheel Travel (in) [- droop / + bump]", color=text_color, fontsize=8)
    plt.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# DIAGRAM: Side-view Roll Centre + Roll Axis  (ENHANCED)
# ---------------------------------------------------------------------------
def _draw_rc_diagram(front_rc, rear_rc, roll_deg=0.0, dive_deg=0.0):
    bg = "#0e1117"; card_bg = "#1a1e2e"; ground_color = "#3a3f4b"
    car_color = "#cc0000"; car_outline = "#ff3333"
    front_color = "#00d4ff"; rear_color = "#ff6b35"
    axis_color = "#ffd700"; text_color = "#e0e0e0"; grid_color = "#2a2e3a"
    wheelbase = 108
    fig, ax = plt.subplots(figsize=(10, 4.5))
    fig.patch.set_facecolor(bg); ax.set_facecolor(card_bg)
    # Ground line
    ax.axhline(y=0, color=ground_color, linewidth=2.5, zorder=1)
    ax.fill_between([-15, wheelbase + 15], -2, 0,
                    color=ground_color, alpha=0.15, zorder=0)
    max_h = max(abs(front_rc), abs(rear_rc), 10) + 5
    # Minor grid lines
    for h in range(0, int(max_h) + 5, 5):
        if h > 0:
            ax.axhline(y=h, color=grid_color, linewidth=0.5,
                       linestyle="--", alpha=0.4, zorder=0)
    for h in range(0, int(max_h) + 5, 1):
        if h > 0:
            ax.axhline(y=h, color=grid_color, linewidth=0.2,
                       linestyle=":", alpha=0.2, zorder=0)
    # Wheels
    wheel_r = 5
    for wx in [0, wheelbase]:
        circle = plt.Circle((wx, wheel_r), wheel_r, fill=False,
                           color="#666", linewidth=2, zorder=3)
        ax.add_patch(circle)
        inner = plt.Circle((wx, wheel_r), 2.5, fill=True,
                          color="#444", linewidth=1, zorder=3)
        ax.add_patch(inner)
    # Car body
    body_y = wheel_r * 2
    body = patches.FancyBboxPatch((-5, body_y), wheelbase + 10, 10,
            boxstyle="round,pad=2", facecolor=car_color,
            edgecolor=car_outline, alpha=0.25, linewidth=1.5, zorder=2)
    ax.add_patch(body)
    # Dive/roll shifts
    dive_shift_front = dive_deg * 0.3
    dive_shift_rear = -dive_deg * 0.3
    roll_shift = roll_deg * 0.15
    eff_front_rc = front_rc + dive_shift_front + roll_shift
    eff_rear_rc = rear_rc + dive_shift_rear - roll_shift
    # RC markers
    ax.plot(0, eff_front_rc, "o", color=front_color, markersize=14,
            zorder=5, markeredgecolor="white", markeredgewidth=1.5)
    ax.plot(wheelbase, eff_rear_rc, "o", color=rear_color, markersize=14,
            zorder=5, markeredgecolor="white", markeredgewidth=1.5)
    # Roll axis line
    ax.plot([0, wheelbase], [eff_front_rc, eff_rear_rc],
            color=axis_color, linewidth=2.5, linestyle="-", zorder=4, alpha=0.9)
    # Roll axis extensions
    extend = 15
    if wheelbase > 0:
        slope = (eff_rear_rc - eff_front_rc) / wheelbase
        ax.plot([-extend, 0],
                [eff_front_rc - slope * extend, eff_front_rc],
                color=axis_color, linewidth=1, linestyle=":", alpha=0.4, zorder=4)
        ax.plot([wheelbase, wheelbase + extend],
                [eff_rear_rc, eff_rear_rc + slope * extend],
                color=axis_color, linewidth=1, linestyle=":", alpha=0.4, zorder=4)
    # NEW: Roll axis angle annotation
    if wheelbase > 0:
        ra_angle = math.degrees(math.atan2(eff_rear_rc - eff_front_rc, wheelbase))
        mid_x = wheelbase / 2
        mid_y = (eff_front_rc + eff_rear_rc) / 2
        # Draw angle arc at front RC point
        arc_r = 20
        theta1 = 0
        theta2 = ra_angle if ra_angle >= 0 else ra_angle
        angle_arc = patches.Arc((0, eff_front_rc), arc_r * 2, arc_r * 2,
                               angle=0, theta1=min(0, ra_angle),
                               theta2=max(0, ra_angle),
                               color=axis_color, linewidth=1.5, alpha=0.6, zorder=5)
        ax.add_patch(angle_arc)
        ax.text(25, eff_front_rc + (2 if ra_angle >= 0 else -3),
                f"{ra_angle:.2f}\u00b0", fontsize=8, color=axis_color,
                ha="left", va="center", fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.2", facecolor=card_bg,
                         edgecolor=axis_color, alpha=0.7), zorder=6)
    # Vertical reference lines from ground to RC
    ax.plot([0, 0], [0, eff_front_rc], color=front_color, linewidth=1.2,
            linestyle="--", alpha=0.9, zorder=4)
    ax.plot([wheelbase, wheelbase], [0, eff_rear_rc], color=rear_color,
            linewidth=1.2, linestyle="--", alpha=0.9, zorder=4)
    # NEW: Height dimension arrows
    arr_offset = -8
    ax.annotate("", xy=(arr_offset, eff_front_rc), xytext=(arr_offset, 0),
                arrowprops=dict(arrowstyle="<->", color=front_color, lw=1.2))
    ax.text(arr_offset - 3, eff_front_rc / 2, f'{eff_front_rc:.3f}"',
            fontsize=9, color=front_color, ha="right", va="center",
            rotation=90, zorder=6)
    arr_offset_r = wheelbase + 8
    ax.annotate("", xy=(arr_offset_r, eff_rear_rc), xytext=(arr_offset_r, 0),
                arrowprops=dict(arrowstyle="<->", color=rear_color, lw=1.2))
    ax.text(arr_offset_r + 3, eff_rear_rc / 2, f'{eff_rear_rc:.3f}"',
            fontsize=9, color=rear_color, ha="left", va="center",
            rotation=90, zorder=6)
    # RC annotations
    f_offset = 2.5 if eff_front_rc >= 0 else -3.5
    r_offset = 2.5 if eff_rear_rc >= 0 else -3.5
    ax.annotate(f"FRONT RC\n{eff_front_rc:.3f}\"",
        xy=(0, eff_front_rc), xytext=(-12, eff_front_rc + f_offset),
        fontsize=9, fontweight="bold", color=front_color, ha="center", va="bottom",
        arrowprops=dict(arrowstyle="->", color=front_color, lw=1.2,
                       connectionstyle="arc3,rad=0.2"), zorder=6,
        bbox=dict(boxstyle="round,pad=0.3", facecolor=card_bg,
                 edgecolor=front_color, alpha=0.85))
    ax.annotate(f"REAR RC\n{eff_rear_rc:.3f}\"",
        xy=(wheelbase, eff_rear_rc),
        xytext=(wheelbase + 12, eff_rear_rc + r_offset),
        fontsize=9, fontweight="bold", color=rear_color, ha="center", va="bottom",
        arrowprops=dict(arrowstyle="->", color=rear_color, lw=1.2,
                       connectionstyle="arc3,rad=-0.2"), zorder=6,
        bbox=dict(boxstyle="round,pad=0.3", facecolor=card_bg,
                 edgecolor=rear_color, alpha=0.85))
    # Roll axis label with angle
    mid_x = wheelbase / 2
    mid_y = (eff_front_rc + eff_rear_rc) / 2
    ra_angle_val = math.degrees(math.atan2(eff_rear_rc - eff_front_rc, wheelbase))
    ax.text(mid_x, mid_y + 3,
            f"ROLL AXIS ({abs(eff_rear_rc - eff_front_rc):.3f}\" diff | {ra_angle_val:.2f}\u00b0)",
            fontsize=8, color=axis_color, ha="center", va="bottom",
            fontstyle="italic", fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.25", facecolor=card_bg,
                     edgecolor=axis_color, alpha=0.7), zorder=6)
    # NEW: CG estimate marker (visual reference)
    cg_x = wheelbase * 0.47  # slightly front-biased
    cg_y = body_y + 5  # approximate CG height
    ax.plot(cg_x, cg_y, "x", color="#ff55ff", markersize=12,
            markeredgewidth=2.5, zorder=6)
    ax.text(cg_x, cg_y + 2, "CG (est.)", fontsize=9, color="#ff55ff",
            ha="center", va="bottom", fontstyle="italic",
            alpha=0.7, zorder=6)
    # NEW: Moment arm lines from CG to roll axis
    # Project CG onto roll axis
    if wheelbase > 0:
        slope_ra = (eff_rear_rc - eff_front_rc) / wheelbase
        ra_y_at_cg = eff_front_rc + slope_ra * cg_x
        ax.plot([cg_x, cg_x], [ra_y_at_cg, cg_y], color="#ff55ff",
                linewidth=1, linestyle="-.", alpha=0.4, zorder=4)
        moment_arm = abs(cg_y - ra_y_at_cg)
        ax.text(cg_x + 3, (ra_y_at_cg + cg_y) / 2,
                f"h={moment_arm:.1f}\"", fontsize=9, color="#ff55ff",
                ha="left", va="center", alpha=0.9, zorder=6)
    # Labels
    ax.text(0, -3.5, "FRONT", fontsize=9, color=text_color,
            ha="center", fontweight="bold", zorder=6)
    ax.text(wheelbase, -3.5, "REAR", fontsize=9, color=text_color,
            ha="center", fontweight="bold", zorder=6)
    ax.text(-15, -0.3, "GROUND", fontsize=9, color=ground_color,
            ha="left", va="top", fontstyle="italic", zorder=6)
    # NEW: Wheelbase dimension
    ax.annotate("", xy=(wheelbase, -5), xytext=(0, -5),
                arrowprops=dict(arrowstyle="<->", color="#888", lw=1))
    ax.text(wheelbase / 2, -5.8, f"Wheelbase: {wheelbase}\"",
            fontsize=9, color="#888", ha="center", va="top", zorder=6)
    # Dive/roll info
    if abs(dive_deg) > 0.01 or abs(roll_deg) > 0.01:
        info = []
        if abs(dive_deg) > 0.01:
            info.append(f"Dive: {dive_deg:+.1f}\u00b0")
        if abs(roll_deg) > 0.01:
            info.append(f"Roll: {roll_deg:+.1f}\u00b0")
        ax.text(wheelbase + 20, -3.5, " | ".join(info), fontsize=9,
                color="#888", ha="right", va="top", fontstyle="italic", zorder=6)
    ax.set_xlim(-25, wheelbase + 25)
    y_lo = min(eff_front_rc, eff_rear_rc, 0) - 8
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
# DIAGRAM: Front-view IC + RC construction (ENHANCED with 10 features)
# ---------------------------------------------------------------------------
def _draw_front_view_rc(lca_len, uca_len, lca_inner_h, lca_outer_h,
                        uca_inner_h, uca_outer_h, half_track, front_rc,
                        bump_in=0.0, roll_deg=0.0):
    bg = "#0e1117"; card_bg = "#1a1e2e"; ground_color = "#3a3f4b"
    lca_color = "#00d4ff"; uca_color = "#ff6b35"; ic_color = "#ffd700"
    rc_color = "#00ff88"; text_color = "#e0e0e0"; grid_color = "#2a2e3a"
    tire_color = "#555555"; fvsa_color = "#ff55ff"
    spindle_color = "#aaaaff"; dim_color = "#cccccc"
    INNER_X = 4.0
    outer_x = half_track
    # Body roll shifts
    roll_rad = math.radians(roll_deg)
    r_bump = bump_in + half_track * math.sin(roll_rad)
    l_bump = bump_in - half_track * math.sin(roll_rad)
    geo_r = _front_view_ic(lca_len, uca_len, lca_inner_h, lca_outer_h,
                           uca_inner_h, uca_outer_h, half_track, bump_in=r_bump)
    geo_l = _front_view_ic(lca_len, uca_len, lca_inner_h, lca_outer_h,
                           uca_inner_h, uca_outer_h, half_track, bump_in=l_bump)
    lo_h_r = geo_r["lca_outer_h"]; uo_h_r = geo_r["uca_outer_h"]
    lo_h_l = geo_l["lca_outer_h"]; uo_h_l = geo_l["uca_outer_h"]
    fig, ax = plt.subplots(figsize=(10, 7))
    fig.patch.set_facecolor(bg); ax.set_facecolor(card_bg)
    # Ground
    ax.axhline(y=0, color=ground_color, linewidth=2.5, zorder=1)
    max_h = max(uca_inner_h, uo_h_r, uo_h_l, 20) + 5
    # Major + minor grid
    for h in range(0, int(max_h) + 5, 5):
        if h > 0:
            ax.axhline(y=h, color=grid_color, linewidth=0.5,
                       linestyle="--", alpha=0.3, zorder=0)
    for h in range(0, int(max_h) + 5, 1):
        if h > 0:
            ax.axhline(y=h, color=grid_color, linewidth=0.2,
                       linestyle=":", alpha=0.15, zorder=0)
    # Vertical grid
    for vx in range(-int(half_track) - 10, int(half_track) + 15, 10):
        ax.axvline(x=vx, color=grid_color, linewidth=0.2,
                   linestyle=":", alpha=0.15, zorder=0)
    # Centreline
    ax.axvline(x=0, color=grid_color, linewidth=1,
               linestyle="-.", alpha=0.5, zorder=1)
    ax.text(0.5, max_h - 1, "CL", fontsize=8, color=grid_color,
            ha="left", va="top", fontstyle="italic", zorder=6)
    # Tires (rotated by camber angle)
    import matplotlib.transforms as mtransforms
    tire_w = 4; tire_h = 10
    for sign in [1, -1]:
        # Get camber for this side
        side_geo = geo_r if sign == 1 else geo_l
        camber_deg = side_geo["camber"] or 0.0
        # Contact patch centre (rotation pivot)
        cp_x = half_track * sign
        # Draw tire as rectangle rotated around contact patch
        tire_rect = patches.Rectangle(
            (-tire_w / 2, 0), tire_w, tire_h,
            facecolor=tire_color, edgecolor="#777",
            alpha=0.5, linewidth=1.5, zorder=2)
        t = mtransforms.Affine2D().rotate_deg_around(0, 0, -camber_deg * sign * 3) + \
            mtransforms.Affine2D().translate(cp_x, 0) + ax.transData
        tire_rect.set_transform(t)
        ax.add_patch(tire_rect)
    # NEW: Tire centre lines (vertical dashed through wheel centre)
    for sign in [1, -1]:
        wx = half_track * sign
        ax.plot([wx, wx], [0, tire_h + 2], color="#aaa",
                linewidth=1, linestyle=":", alpha=0.8, zorder=2)
        ax.text(wx, tire_h + 2.5, "WC", fontsize=9, color="#aaa",
                ha="center", va="bottom", alpha=0.9, zorder=6)
    # Frame box
    frame_w = INNER_X * 2 + 4; frame_h = uca_inner_h - lca_inner_h + 4
    frame = patches.FancyBboxPatch((-frame_w / 2, lca_inner_h - 2),
            frame_w, frame_h, boxstyle="round,pad=1",
            facecolor="#cc0000", edgecolor="#ff3333",
            alpha=0.2, linewidth=1.5, zorder=2)
    ax.add_patch(frame)
    # Right-side arms
    ax.plot([INNER_X, outer_x], [lca_inner_h, lo_h_r],
            color=lca_color, linewidth=2.5, zorder=4, label="LCA")
    ax.plot(INNER_X, lca_inner_h, "o", color=lca_color, markersize=8,
            zorder=5, markeredgecolor="white", markeredgewidth=1)
    ax.plot(outer_x, lo_h_r, "o", color=lca_color, markersize=8,
            zorder=5, markeredgecolor="white", markeredgewidth=1)
    ax.plot([INNER_X, outer_x], [uca_inner_h, uo_h_r],
            color=uca_color, linewidth=2.5, zorder=4, label="UCA")
    ax.plot(INNER_X, uca_inner_h, "o", color=uca_color, markersize=8,
            zorder=5, markeredgecolor="white", markeredgewidth=1)
    ax.plot(outer_x, uo_h_r, "o", color=uca_color, markersize=8,
            zorder=5, markeredgecolor="white", markeredgewidth=1)
    # NEW: Spindle / Kingpin line (connects upper and lower ball joints)
    ax.plot([outer_x, outer_x], [lo_h_r, uo_h_r], color=spindle_color,
            linewidth=2, linestyle="-", alpha=0.9, zorder=4)
    ax.text(outer_x + 1.5, (lo_h_r + uo_h_r) / 2, "KP", fontsize=9,
            color=spindle_color, ha="left", va="center", alpha=0.9, zorder=6)
    # NEW: KPI angle (King Pin Inclination)
    kpi_dy = uo_h_r - lo_h_r
    if abs(kpi_dy) > 0.01:
        kpi_angle = math.degrees(math.atan2(0, kpi_dy))  # vertical = 0 deg
        # True KPI: angle from vertical
        kpi_actual = 90.0 - math.degrees(math.atan2(kpi_dy, 0.001))
        ax.text(outer_x + 1.5, lo_h_r - 1.5,
                f"KPI: {abs(kpi_actual):.1f}\u00b0", fontsize=9,
                color=spindle_color, ha="left", va="top", alpha=0.9, zorder=6)
    # NEW: Arm angle annotations (right side)
    lca_angle_r = math.degrees(math.atan2(lo_h_r - lca_inner_h, outer_x - INNER_X))
    uca_angle_r = math.degrees(math.atan2(uo_h_r - uca_inner_h, outer_x - INNER_X))
    lca_mid_x = (INNER_X + outer_x) / 2
    lca_mid_y = (lca_inner_h + lo_h_r) / 2
    ax.text(lca_mid_x, lca_mid_y - 1.5, f"{lca_angle_r:.1f}\u00b0",
            fontsize=9, color=lca_color, ha="center", va="top",
            fontweight="bold", alpha=0.8, zorder=6,
            bbox=dict(boxstyle="round,pad=0.15", facecolor=card_bg,
                     edgecolor=lca_color, alpha=0.85))
    uca_mid_x = (INNER_X + outer_x) / 2
    uca_mid_y = (uca_inner_h + uo_h_r) / 2
    ax.text(uca_mid_x, uca_mid_y + 1.5, f"{uca_angle_r:.1f}\u00b0",
            fontsize=9, color=uca_color, ha="center", va="bottom",
            fontweight="bold", alpha=0.8, zorder=6,
            bbox=dict(boxstyle="round,pad=0.15", facecolor=card_bg,
                     edgecolor=uca_color, alpha=0.85))
    # NEW: Arm length labels (right side)
    lca_actual = math.sqrt((outer_x - INNER_X)**2 + (lo_h_r - lca_inner_h)**2)
    uca_actual = math.sqrt((outer_x - INNER_X)**2 + (uo_h_r - uca_inner_h)**2)
    ax.text(lca_mid_x + 6, lca_mid_y + 0.5, f"{lca_actual:.1f}\"",
            fontsize=9, color=lca_color, ha="left", va="center",
            alpha=0.9, fontstyle="italic", zorder=6)
    ax.text(uca_mid_x + 6, uca_mid_y - 0.5, f"{uca_actual:.1f}\"",
            fontsize=9, color=uca_color, ha="left", va="center",
            alpha=0.9, fontstyle="italic", zorder=6)
    # Left-side arms
    ax.plot([-INNER_X, -outer_x], [lca_inner_h, lo_h_l],
            color=lca_color, linewidth=2.5, alpha=0.6, zorder=4)
    ax.plot([-INNER_X, -outer_x], [uca_inner_h, uo_h_l],
            color=uca_color, linewidth=2.5, alpha=0.6, zorder=4)
    for px, py in [(-INNER_X, lca_inner_h), (-outer_x, lo_h_l),
                   (-INNER_X, uca_inner_h), (-outer_x, uo_h_l)]:
        ax.plot(px, py, "o", color="#888", markersize=6, alpha=0.6, zorder=5)
    # Left spindle
    ax.plot([-outer_x, -outer_x], [lo_h_l, uo_h_l], color=spindle_color,
            linewidth=2, linestyle="-", alpha=0.9, zorder=4)
    # NEW: RC migration trail (shows RC at different travel positions)
    trail_steps = 9
    trail_range = 2.0
    for ti in range(trail_steps):
        tt = -trail_range + (2 * trail_range * ti / (trail_steps - 1))
        if abs(tt - bump_in) < 0.01:
            continue
        tg = _front_view_ic(lca_len, uca_len, lca_inner_h, lca_outer_h,
                           uca_inner_h, uca_outer_h, half_track, bump_in=tt)
        if tg["rc_y"] is not None:
            alpha_val = 0.3 + 0.2 * (1 - abs(tt - bump_in) / trail_range)
            ax.plot(0, tg["rc_y"], "o", color=rc_color, markersize=5,
                    alpha=alpha_val, zorder=3)
    # Right-side IC construction
    ic_x_r = geo_r["ic_x"]; ic_y_r = geo_r["ic_y"]
    rc_y_r = geo_r["rc_y"]; fvsa_r = geo_r["fvsa"]
    if ic_x_r is not None:
        ax.plot([INNER_X, ic_x_r], [lca_inner_h, ic_y_r],
                color=lca_color, linewidth=1, linestyle="--", alpha=0.5, zorder=3)
        ax.plot([INNER_X, ic_x_r], [uca_inner_h, ic_y_r],
                color=uca_color, linewidth=1, linestyle="--", alpha=0.5, zorder=3)
        ax.plot(ic_x_r, ic_y_r, "D", color=ic_color, markersize=12,
                zorder=6, markeredgecolor="white", markeredgewidth=1.5)
        ic_label_r = f"IC R\n({ic_x_r:.0f}, {ic_y_r:.1f})"
        ax.annotate(ic_label_r, xy=(ic_x_r, ic_y_r),
            xytext=(ic_x_r - 10, ic_y_r + 3),
            fontsize=8, fontweight="bold", color=ic_color,
            ha="center", va="bottom",
            arrowprops=dict(arrowstyle="->", color=ic_color, lw=1),
            zorder=7, bbox=dict(boxstyle="round,pad=0.3",
                               facecolor=card_bg, edgecolor=ic_color, alpha=0.85))
        fvsa_label = f"FVSA R ({fvsa_r:.1f} in)" if fvsa_r else "FVSA"
        ax.plot([half_track, ic_x_r], [0, ic_y_r],
                color=fvsa_color, linewidth=2, linestyle="-",
                alpha=0.6, zorder=4, label=fvsa_label)
        ax.plot([half_track, 0], [0, rc_y_r],
                color=rc_color, linewidth=2, linestyle="-",
                alpha=0.8, zorder=4)
    # NEW: Scrub radius indicator (right side)
    scrub_radius = half_track - outer_x  # simplified - distance from KP to contact
    ax.annotate("", xy=(half_track, -1.5), xytext=(outer_x, -1.5),
                arrowprops=dict(arrowstyle="<->", color=dim_color, lw=1))
    ax.text((half_track + outer_x) / 2, -2.5,
            f"Scrub: {abs(scrub_radius):.1f}\"", fontsize=9,
            color=dim_color, ha="center", va="top", zorder=6)
    # Left-side IC construction
    ic_x_l = geo_l["ic_x"]; ic_y_l = geo_l["ic_y"]
    rc_y_l = geo_l["rc_y"]; fvsa_l = geo_l["fvsa"]
    if ic_x_l is not None and abs(roll_deg) > 0.01:
        l_ic_x_plot = -ic_x_l
        ax.plot([-INNER_X, l_ic_x_plot], [lca_inner_h, ic_y_l],
                color=lca_color, linewidth=1, linestyle="--",
                alpha=0.3, zorder=3)
        ax.plot([-INNER_X, l_ic_x_plot], [uca_inner_h, ic_y_l],
                color=uca_color, linewidth=1, linestyle="--",
                alpha=0.3, zorder=3)
        ax.plot(l_ic_x_plot, ic_y_l, "D", color="#ffaa00",
                markersize=10, zorder=6, markeredgecolor="white",
                markeredgewidth=1, alpha=0.8)
        ic_label_l = f"IC L\n({ic_x_l:.0f}, {ic_y_l:.1f})"
        ax.annotate(ic_label_l, xy=(l_ic_x_plot, ic_y_l),
            xytext=(l_ic_x_plot + 10, ic_y_l + 3),
            fontsize=8, fontweight="bold", color="#ffaa00",
            ha="center", va="bottom",
            arrowprops=dict(arrowstyle="->", color="#ffaa00", lw=1),
            zorder=7, bbox=dict(boxstyle="round,pad=0.3",
                               facecolor=card_bg, edgecolor="#ffaa00", alpha=0.85))
        ax.plot([-half_track, l_ic_x_plot], [0, ic_y_l],
                color=fvsa_color, linewidth=1.5, linestyle="-",
                alpha=0.4, zorder=4)
        ax.plot([-half_track, 0], [0, rc_y_l],
                color=rc_color, linewidth=1.5, linestyle="--",
                alpha=0.9, zorder=4)
    # RC marker (use average of L/R if rolling)
    if abs(roll_deg) > 0.01 and rc_y_r is not None and rc_y_l is not None:
        avg_rc = (rc_y_r + rc_y_l) / 2
        ax.plot(0, avg_rc, "o", color=rc_color, markersize=14,
                zorder=6, markeredgecolor="white", markeredgewidth=2)
        ax.annotate(f"ROLL CENTRE\n{avg_rc:.3f}\"",
            xy=(0, avg_rc), xytext=(-12, avg_rc + 4),
            fontsize=9, fontweight="bold", color=rc_color,
            ha="center", va="bottom",
            arrowprops=dict(arrowstyle="->", color=rc_color, lw=1.2,
                           connectionstyle="arc3,rad=0.2"),
            zorder=7, bbox=dict(boxstyle="round,pad=0.3",
                               facecolor=card_bg, edgecolor=rc_color, alpha=0.85))
    elif rc_y_r is not None:
        ax.plot(0, rc_y_r, "o", color=rc_color, markersize=14,
                zorder=6, markeredgecolor="white", markeredgewidth=2)
        ax.annotate(f"ROLL CENTRE\n{rc_y_r:.3f}\"",
            xy=(0, rc_y_r), xytext=(-12, rc_y_r + 4),
            fontsize=9, fontweight="bold", color=rc_color,
            ha="center", va="bottom",
            arrowprops=dict(arrowstyle="->", color=rc_color, lw=1.2,
                           connectionstyle="arc3,rad=0.2"),
            zorder=7, bbox=dict(boxstyle="round,pad=0.3",
                               facecolor=card_bg, edgecolor=rc_color, alpha=0.85))
    else:
        ax.plot(0, 0, "o", color=rc_color, markersize=14,
                zorder=6, markeredgecolor="white", markeredgewidth=2)
        ax.text(-12, 2, "RC at ground (parallel arms)",
                fontsize=8, color=rc_color, ha="center", zorder=7)
    # Contact patches
    for side_key in ["R", "L"]:
        cx = half_track if side_key == "R" else -half_track
        ax.plot(cx, 0, "^", color="#aaa", markersize=10,
                zorder=5, markeredgecolor="white", markeredgewidth=1)
        ax.text(cx, -1.5, "Contact\nPatch", fontsize=9, color="#aaa",
                ha="center", va="top", zorder=6)
    # NEW: Track width dimension
    ax.annotate("", xy=(half_track, -4), xytext=(-half_track, -4),
                arrowprops=dict(arrowstyle="<->", color=dim_color, lw=1))
    ax.text(0, -4.8, f"Track: {half_track * 2:.1f}\"",
            fontsize=9, color=dim_color, ha="center", va="top", zorder=6)
    # Info text
    if abs(bump_in) > 0.001 or abs(roll_deg) > 0.01:
        parts = []
        if abs(bump_in) > 0.001:
            parts.append(f"Bump: {bump_in:+.2f}\"")
        if abs(roll_deg) > 0.01:
            parts.append(f"Roll: {roll_deg:+.1f} deg")
        ax.text(0, -6.5, " | ".join(parts), fontsize=8,
                color="#ffaa00", ha="center", fontstyle="italic",
                fontweight="bold", zorder=6)
    else:
        ax.text(0, -6.5, "VIEW: Looking from behind front wheels",
                fontsize=8, color=text_color, ha="center",
                fontstyle="italic", zorder=6)
    ax.legend(loc="upper right", facecolor=card_bg, edgecolor=grid_color,
              labelcolor=text_color, fontsize=8)
    margin = 8
    ax.set_xlim(-half_track - margin, half_track + margin)
    y_lo = -8; y_hi_val = max_h + 5
    if ic_y_r is not None:
        y_hi_val = max(y_hi_val, ic_y_r + 8)
    if ic_y_l is not None:
        y_hi_val = max(y_hi_val, ic_y_l + 8)
    ax.set_ylim(y_lo, y_hi_val); ax.set_aspect("auto")
    ax.set_xlabel("Lateral Position (inches)", color=text_color, fontsize=8)
    ax.set_ylabel("Height (inches)", color=text_color, fontsize=8)
    title_txt = "Front View \u2014 Instant Centre Construction"
    if abs(roll_deg) > 0.01:
        title_txt += f" (Roll: {roll_deg:+.1f} deg)"
    ax.set_title(title_txt, color=text_color, fontsize=11, fontweight="bold")
    ax.tick_params(colors=text_color, labelsize=7)
    for spine in ax.spines.values():
        spine.set_color(grid_color)
    plt.tight_layout()
    return fig, geo_r, geo_l


# ---------------------------------------------------------------------------
# RENDER
# ---------------------------------------------------------------------------
def render():
    st.title("Roll Centres")
    st.caption("Calculate and track front and rear roll centre heights for each chassis.")
    chassis_list = get_chassis_list()
    if not chassis_list:
        st.warning("No chassis found. Please add a chassis in Chassis Profiles first.")
        return
    _ensure_headers()
    tab_calc, tab_springs, tab_camber, tab_sweep, tab_compare, tab_log = st.tabs([
        "Calculate", "Spring Rates", "Camber Gain",
        "Sweep Chart", "Compare Setups", "Log / History"
    ])
    # ================================================================
    # CALCULATE TAB
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
            f_lca_len, f_uca_len, f_lca_inner_h, f_lca_outer_h,
            f_uca_inner_h, f_uca_outer_h, f_spindle_h)
        st.divider()
        st.markdown("### Rear Suspension")
        st.caption("Trailing Arms + Upper Link")
        r1, r2, r3 = st.columns(3)
        with r1:
            st.markdown("**Trailing Arms**")
            r_ta_length = st.number_input("Trailing Arm Length (in)", min_value=0.0,
                value=28.0, step=0.25, key="r_ta_len",
                help="Length of trailing arm from frame pivot to axle mount")
            r_ta_frame_h = st.number_input("Frame Mount Height (in)", value=8.0,
                step=0.25, key="r_ta_frame_h",
                help="Height of trailing arm frame pivot from ground")
            r_ta_axle_h = st.number_input("Axle Mount Height (in)", value=8.0,
                step=0.25, key="r_ta_axle_h",
                help="Height of trailing arm mount on axle housing from ground")
        with r2:
            st.markdown("**Upper Link**")
            r_ul_length = st.number_input("Upper Link Length (in)", min_value=0.0,
                value=12.0, step=0.25, key="r_ul_len",
                help="Length of the upper link / 3rd link / pull bar")
            r_ul_frame_h = st.number_input("Frame Mount Height (in)", value=18.0,
                step=0.25, key="r_ul_frame_h",
                help="Height of upper link chassis-side mount from ground")
            r_ul_axle_h = st.number_input("Axle Mount Height (in)", value=16.0,
                step=0.25, key="r_ul_axle_h",
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
            r_ul_frame_h, r_ul_axle_h, r_ul_frame_offset, r_ul_axle_offset)
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
        # -- Front-view diagram (with roll) --
        st.divider()
        st.markdown("### Front View \u2014 Instant Centre & FVSA")
        st.caption(
            "Slide the bump/droop slider to see how wheel travel changes "
            "the Instant Centre, Roll Centre, FVSA length, and camber in real time. "
            "The Body Roll slider above also affects this view, showing L/R IC separation."
        )
        bump_in = st.slider("Wheel Travel (Bump / Droop)",
            min_value=-3.0, max_value=3.0, value=0.0, step=0.125,
            key="fv_bump",
            help="Positive = bump (compression). Negative = droop (extension).")
        fig_fv, geo_r, geo_l = _draw_front_view_rc(
            f_lca_len, f_uca_len, f_lca_inner_h, f_lca_outer_h,
            f_uca_inner_h, f_uca_outer_h, f_spindle_h, front_rc,
            bump_in=bump_in, roll_deg=roll_deg)
        st.pyplot(fig_fv); plt.close(fig_fv)
        # Live metrics
        if abs(roll_deg) > 0.01:
            st.markdown("##### Right Side")
            m1, m2, m3, m4 = st.columns(4)
            with m1:
                if geo_r["ic_x"] is not None and geo_r["ic_y"] is not None:
                    st.metric("IC Position (R)",
                        f"({geo_r['ic_x']:.0f}, {geo_r['ic_y']:.1f})",
                        help="Right-side Instant Centre (lateral, height) in inches.")
                else:
                    st.metric("IC Position (R)", "-- (parallel)",
                        help="Right-side Instant Centre.")
            with m2:
                fvsa_val = f"{geo_r['fvsa']:.1f} in" if geo_r["fvsa"] is not None else "--"
                st.metric("FVSA Length (R)", fvsa_val,
                    help="Right-side Front View Swing Arm length.")
            with m3:
                rc_val = f"{geo_r['rc_y']:.3f} in" if geo_r["rc_y"] is not None else "--"
                st.metric("RC Height (R)", rc_val,
                    help="Right-side roll centre height contribution.")
            with m4:
                st.metric("Camber (R)", f"{geo_r['camber']:.3f} deg",
                    help="Right-side camber angle.")
            st.markdown("##### Left Side")
            m5, m6, m7, m8 = st.columns(4)
            with m5:
                if geo_l["ic_x"] is not None and geo_l["ic_y"] is not None:
                    st.metric("IC Position (L)",
                        f"({geo_l['ic_x']:.0f}, {geo_l['ic_y']:.1f})",
                        help="Left-side Instant Centre (lateral, height) in inches.")
                else:
                    st.metric("IC Position (L)", "-- (parallel)",
                        help="Left-side Instant Centre.")
            with m6:
                fvsa_val_l = f"{geo_l['fvsa']:.1f} in" if geo_l["fvsa"] is not None else "--"
                st.metric("FVSA Length (L)", fvsa_val_l,
                    help="Left-side Front View Swing Arm length.")
            with m7:
                rc_val_l = f"{geo_l['rc_y']:.3f} in" if geo_l["rc_y"] is not None else "--"
                st.metric("RC Height (L)", rc_val_l,
                    help="Left-side roll centre height contribution.")
            with m8:
                st.metric("Camber (L)", f"{geo_l['camber']:.3f} deg",
                    help="Left-side camber angle.")
        else:
            m1, m2, m3, m4 = st.columns(4)
            with m1:
                if geo_r["ic_x"] is not None and geo_r["ic_y"] is not None:
                    st.metric("IC Position",
                        f"({geo_r['ic_x']:.0f}, {geo_r['ic_y']:.1f})",
                        help="The Instant Centre (IC) is where the upper and lower control arm lines intersect. Shown as (lateral position, height) in inches.")
                else:
                    st.metric("IC Position", "-- (parallel)",
                        help="The Instant Centre (IC) is where the upper and lower control arm lines intersect.")
            with m2:
                fvsa_val = f"{geo_r['fvsa']:.1f} in" if geo_r["fvsa"] is not None else "--"
                st.metric("FVSA Length", fvsa_val,
                    help="Front View Swing Arm length. Distance from contact patch to IC.")
            with m3:
                rc_val = f"{geo_r['rc_y']:.3f} in" if geo_r["rc_y"] is not None else "--"
                st.metric("Roll Centre Height", rc_val,
                    help="Height above ground where the car body pivots during cornering.")
            with m4:
                st.metric("Camber Change", f"{geo_r['camber']:.3f} deg",
                    help="Camber angle at the current bump/droop position.")
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
    # SPRING RATES TAB
    # ================================================================
    with tab_springs:
        st.subheader("Spring Rate Calculator")
        st.markdown("Calculate required spring rates from corner weights and "
                    "desired ride frequency, or find the ride frequency from "
                    "a known spring rate.")
        mode = st.radio("Calculation Mode",
            ["Find Spring Rate from Frequency", "Find Frequency from Spring Rate"],
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
                f_spring = _calc_spring_rate(f_corner_wt, f_target_freq, f_motion_ratio)
                f_wheel_rate = _calc_wheel_rate(f_spring, f_motion_ratio)
                st.metric("Front Spring Rate", f"{f_spring:.1f} lbs/in")
                st.metric("Front Wheel Rate", f"{f_wheel_rate:.1f} lbs/in")
            with fc2:
                r_target_freq = st.slider("Rear Target Frequency (Hz)",
                    1.0, 4.0, 2.0, 0.05, key="r_target_freq",
                    help="Typical oval: 1.8-3.0 Hz rear")
                r_spring = _calc_spring_rate(r_corner_wt, r_target_freq, r_motion_ratio)
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
                f_freq = _calc_ride_frequency(f_spring_known, f_corner_wt, f_motion_ratio)
                f_wr = _calc_wheel_rate(f_spring_known, f_motion_ratio)
                st.metric("Front Ride Frequency", f"{f_freq:.2f} Hz")
                st.metric("Front Wheel Rate", f"{f_wr:.1f} lbs/in")
            with fc2:
                r_spring_known = st.number_input(
                    "Rear Spring Rate (lbs/in)", min_value=0.0,
                    value=250.0, step=5.0, key="r_spring_known")
                r_freq = _calc_ride_frequency(r_spring_known, r_corner_wt, r_motion_ratio)
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
                "Front (Hz)": ["1.0 - 1.5", "1.5 - 2.0", "2.0 - 2.5", "2.5 - 3.5"],
                "Rear (Hz)": ["1.2 - 1.7", "1.7 - 2.3", "2.3 - 2.8", "2.8 - 4.0"],
            }
            st.table(pd.DataFrame(ref_data))
    # ================================================================
    # CAMBER GAIN TAB
    # ================================================================
    with tab_camber:
        st.subheader("Camber Gain Table")
        st.markdown("Estimates how front camber changes as the wheel travels "
                    "through bump and droop (based on the A-arm geometry "
                    "entered in the Calculate tab).")
        cg_range = st.slider("Wheel Travel Range (in)", 1.0, 6.0, 3.0, 0.5,
            key="cg_range", help="Total travel from full droop to full bump")
        cg_lca_len = st.session_state.get("f_lca_len", 12.0)
        cg_uca_len = st.session_state.get("f_uca_len", 10.0)
        cg_lca_inner = st.session_state.get("f_lca_inner_h", 6.0)
        cg_lca_outer = st.session_state.get("f_lca_outer_h", 5.5)
        cg_uca_inner = st.session_state.get("f_uca_inner_h", 14.0)
        cg_uca_outer = st.session_state.get("f_uca_outer_h", 13.0)
        cg_spindle = st.session_state.get("f_spindle_h", 30.0)
        camber_data = _calc_camber_gain(
            cg_lca_len, cg_uca_len, cg_lca_inner, cg_lca_outer,
            cg_uca_inner, cg_uca_outer, cg_spindle,
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
            tvls = [d[0] for d in camber_data]
            cmbs = [d[1] for d in camber_data]
            ax_cg.plot(tvls, cmbs, color="#00d4ff", linewidth=2.5,
                      marker="o", markersize=5)
            ax_cg.axhline(y=0, color="#3a3f4b", linewidth=1, linestyle="--")
            ax_cg.axvline(x=0, color="#3a3f4b", linewidth=1, linestyle="--")
            ax_cg.fill_between(tvls, cmbs, 0, alpha=0.15, color="#00d4ff")
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
    # SWEEP CHART TAB
    # ================================================================
    with tab_sweep:
        st.subheader("Suspension Sweep Chart")
        st.markdown(
            "Visualise how **Roll Centre height**, **FVSA length**, and "
            "**Camber change** vary across the full range of wheel travel. "
            "Uses the geometry from the Calculate tab."
        )
        sw_range = st.slider("Sweep Travel Range (in)", 1.0, 6.0, 3.0, 0.5,
            key="sw_range", help="Total travel from full droop to full bump")
        sw_lca_len = st.session_state.get("f_lca_len", 12.0)
        sw_uca_len = st.session_state.get("f_uca_len", 10.0)
        sw_lca_inner = st.session_state.get("f_lca_inner_h", 6.0)
        sw_lca_outer = st.session_state.get("f_lca_outer_h", 5.5)
        sw_uca_inner = st.session_state.get("f_uca_inner_h", 14.0)
        sw_uca_outer = st.session_state.get("f_uca_outer_h", 13.0)
        sw_spindle = st.session_state.get("f_spindle_h", 30.0)
        travels, rc_heights, fvsa_lengths, camber_changes = _calc_sweep_data(
            sw_lca_len, sw_uca_len, sw_lca_inner, sw_lca_outer,
            sw_uca_inner, sw_uca_outer, sw_spindle,
            travel_range=sw_range, steps=25)
        fig_sw = _draw_sweep_chart(travels, rc_heights,
                                  fvsa_lengths, camber_changes)
        st.pyplot(fig_sw); plt.close(fig_sw)
        st.divider()
        st.markdown("##### Values at Static (0 travel)")
        mid_idx = len(travels) // 2
        sw1, sw2, sw3 = st.columns(3)
        with sw1:
            st.metric("RC Height", f"{rc_heights[mid_idx]:.3f} in")
        with sw2:
            st.metric("FVSA Length", f"{fvsa_lengths[mid_idx]:.1f} in")
        with sw3:
            st.metric("Camber Change", f"{camber_changes[mid_idx]:.3f} deg")
        st.divider()
        st.markdown("##### Range Summary")
        rc_min = min(rc_heights); rc_max = max(rc_heights)
        fv_min = min(fvsa_lengths); fv_max = max(fvsa_lengths)
        cm_min = min(camber_changes); cm_max = max(camber_changes)
        rg1, rg2, rg3, rg4, rg5, rg6 = st.columns(6)
        with rg1:
            st.metric("RC Min", f"{rc_min:.2f} in")
        with rg2:
            st.metric("RC Max", f"{rc_max:.2f} in")
        with rg3:
            st.metric("FVSA Min", f"{fv_min:.0f} in")
        with rg4:
            st.metric("FVSA Max", f"{fv_max:.0f} in")
        with rg5:
            st.metric("Camber Min", f"{cm_min:.3f}\u00b0")
        with rg6:
            st.metric("Camber Max", f"{cm_max:.3f}\u00b0")
        with st.expander("Raw Sweep Data"):
            sweep_df = pd.DataFrame({
                "Travel (in)": travels,
                "RC Height (in)": [round(v, 3) for v in rc_heights],
                "FVSA (in)": [round(v, 1) for v in fvsa_lengths],
                "Camber Change (deg)": camber_changes,
            })
            st.dataframe(sweep_df, use_container_width=True, hide_index=True)
    # ================================================================
    # COMPARE SETUPS TAB
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
                        "Setup A": va, "Setup B": vb, "Difference": diff_str})
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
                    color="#00d4ff", linewidth=2.5, markersize=10,
                    label="Setup A")
                ax_cmp.plot([0, wb], [frc_b, rrc_b], "s--",
                    color="#ff6b35", linewidth=2.5, markersize=10,
                    label="Setup B")
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
    # LOG / HISTORY TAB
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
                "chassis", "date", "track", "front_rc_height",
                "rear_rc_height", "rc_height_diff", "notes"
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
