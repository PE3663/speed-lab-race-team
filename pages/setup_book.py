import streamlit as st
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from utils.gsheet_db import read_sheet, append_row, get_chassis_list, timestamp_now

CORNERS = ["LF", "RF", "LR", "RR"]

def render():
    st.header("🔧 Setup Book")
    chassis_list = get_chassis_list()
    if not chassis_list:
        st.warning("Add a chassis profile first.")
        return

    tab1, tab2 = st.tabs(["View Setups", "Add New Setup"])

    with tab1:
        df = read_sheet("setups")
        if not df.empty:
            filt = st.selectbox("Filter by Chassis", ["All"] + chassis_list)
            if filt != "All":
                df = df[df["chassis"] == filt]
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No setups saved yet.")

    with tab2:
        with st.form("add_setup", clear_on_submit=True):
            st.subheader("New Setup Entry")
            chassis = st.selectbox("Chassis", chassis_list)
            setup_name = st.text_input("Setup Name (e.g. Flamboro Baseline)")

            st.markdown("---")
            st.subheader("Springs")
            spr = {}
            cols = st.columns(4)
            for i, c in enumerate(CORNERS):
                with cols[i]:
                    spr[f"spring_{c}"] = st.text_input(f"Spring {c} (lbs)")

            st.subheader("Bump Springs")
            bump = {}
            cols2 = st.columns(4)
            for i, c in enumerate(CORNERS):
                with cols2[i]:
                    bump[f"bump_spring_{c}"] = st.text_input(f"Bump Spring {c} (lbs)")

            st.subheader("Shocks")
            comp, reb = {}, {}
            cols3 = st.columns(4)
            for i, c in enumerate(CORNERS):
                with cols3[i]:
                    comp[f"shock_comp_{c}"] = st.text_input(f"Compression {c}")
                    reb[f"shock_reb_{c}"] = st.text_input(f"Rebound {c}")

            st.subheader("Ride Heights")
            rh = {}
            cols4 = st.columns(4)
            for i, c in enumerate(CORNERS):
                with cols4[i]:
                    rh[f"ride_height_{c}"] = st.text_input(f"Ride Height {c}")

            st.subheader("Alignment")
            align = {}
            cols5 = st.columns(4)
            for i, c in enumerate(CORNERS):
                with cols5[i]:
                    align[f"camber_{c}"] = st.text_input(f"Camber {c}")
                    align[f"caster_{c}"] = st.text_input(f"Caster {c}") if c in ["LF","RF"] else None
            toe = st.text_input("Toe (total)")

            st.subheader("Scale Weights")
            wt = {}
            cols6 = st.columns(4)
            for i, c in enumerate(CORNERS):
                with cols6[i]:
                    wt[f"weight_{c}"] = st.text_input(f"Weight {c} (lbs)")

            st.subheader("Chassis / Drivetrain")
            cc1, cc2, cc3 = st.columns(3)
            with cc1:
                gear_ratio = st.text_input("Gear Ratio")
            with cc2:
                sway_bar = st.text_input("Sway Bar")
            with cc3:
                track_bar = st.text_input("Track Bar Height")

            tc1, tc2 = st.columns(2)
            with tc1:
                panhard = st.text_input("Panhard Bar")
                trailing_arm = st.text_input("Trailing Arm Angle")
            with tc2:
                tire_pressure = st.text_input("Tire Pressures (LF/RF/LR/RR)")
                stagger = st.text_input("Stagger")

            notes = st.text_area("Setup Notes")

            if st.form_submit_button("Save Setup", type="primary"):
                row = {"chassis": chassis, "setup_name": setup_name, "date": timestamp_now()}
                row.update(spr)
                row.update(bump)
                row.update(comp)
                row.update(reb)
                row.update(rh)
                row.update({k: v for k, v in align.items() if v is not None})
                row["toe"] = toe
                row.update(wt)
                row["gear_ratio"] = gear_ratio
                row["sway_bar"] = sway_bar
                row["track_bar"] = track_bar
                row["panhard"] = panhard
                row["trailing_arm"] = trailing_arm
                row["tire_pressures"] = tire_pressure
                row["stagger"] = stagger
                row["notes"] = notes
                append_row("setups", row)
                st.success(f"Setup '{setup_name}' saved!")
                st.rerun()
