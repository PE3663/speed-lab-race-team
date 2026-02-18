import streamlit as st
import sys, os
import pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from utils.gsheet_db import read_sheet, append_row, timestamp_now


def render():
    st.header("🎯 Trackside Tuning Guide")
    st.markdown("Quick reference for common handling issues and recommended adjustments.")

    tab1, tab2, tab3 = st.tabs(["Quick Fixes", "Tuning Log", "Reference"])

    # --- Quick Fix Guide ---
    with tab1:
        st.subheader("What's the car doing?")
        condition = st.selectbox("Select Handling Condition", [
            "Tight / Push - Entry",
            "Tight / Push - Center",
            "Tight / Push - Exit",
            "Loose - Entry",
            "Loose - Center",
            "Loose - Exit",
            "Tight Entry / Loose Exit",
            "Loose Entry / Tight Exit",
            "Lacks Forward Drive",
            "Bouncing / Porpoising",
            "Chassis Roll - Too Much",
            "Chassis Roll - Not Enough"
        ])

        fixes = {
            "Tight / Push - Entry": {
                "description": "Car won't turn into the corner on entry.",
                "quick_fixes": [
                    "Soften RF spring or raise RF",
                    "Add LR bite (raise LR or lower RR)",
                    "Decrease RF camber (more negative)",
                    "Increase RF caster",
                    "Soften RF bump spring",
                    "Lower LF air pressure 1-2 psi"
                ],
                "advanced": "Consider more rear stagger, move weight to left side, or adjust sway bar."
            },
            "Tight / Push - Center": {
                "description": "Car pushes through the middle of the corner.",
                "quick_fixes": [
                    "Soften RR spring",
                    "Add more cross weight",
                    "Soften RF shock rebound",
                    "Raise rear ride height",
                    "Add rear stagger",
                    "Soften RF bump spring"
                ],
                "advanced": "Check cross weight percentage, aim for track-specific range."
            },
            "Tight / Push - Exit": {
                "description": "Car pushes coming off the corner.",
                "quick_fixes": [
                    "Stiffen LR spring",
                    "Soften RR shock compression",
                    "Lower RR or raise LR",
                    "Add rear stagger",
                    "Stiffen LR bump spring"
                ],
                "advanced": "May need to adjust panhard bar height or 3-link angles."
            },
            "Loose - Entry": {
                "description": "Rear steps out when entering the corner.",
                "quick_fixes": [
                    "Stiffen RF spring or lower RF",
                    "Soften LR shock rebound",
                    "Reduce rear stagger",
                    "Add RR air pressure 1-2 psi",
                    "Stiffen RF bump spring"
                ],
                "advanced": "Check LR shock for fade, verify rear alignment."
            },
            "Loose - Center": {
                "description": "Rear is loose through the middle of the corner.",
                "quick_fixes": [
                    "Stiffen RR spring",
                    "Remove cross weight",
                    "Stiffen LR shock rebound",
                    "Lower rear ride height",
                    "Stiffen RR bump spring"
                ],
                "advanced": "Consider sway bar adjustment or rear moment center changes."
            },
            "Loose - Exit": {
                "description": "Rear comes around on corner exit / acceleration.",
                "quick_fixes": [
                    "Soften LR spring",
                    "Stiffen RR shock compression",
                    "Raise RR or lower LR",
                    "Reduce rear stagger",
                    "Soften LR bump spring"
                ],
                "advanced": "Verify rear end alignment and pinion angle."
            },
            "Tight Entry / Loose Exit": {
                "description": "Pushes going in, then snaps loose coming off.",
                "quick_fixes": [
                    "Increase LR spring rate",
                    "Decrease RR spring rate",
                    "Adjust shock package for transition",
                    "Check cross weight balance",
                    "Adjust bump spring split LR vs RR"
                ],
                "advanced": "Classic cross-weight or spring split issue. May need full re-scale."
            },
            "Loose Entry / Tight Exit": {
                "description": "Rear rotates on entry but pushes on exit.",
                "quick_fixes": [
                    "Decrease LR spring rate",
                    "Increase RR spring rate",
                    "Adjust RF shock for entry",
                    "Check sway bar preload",
                    "Adjust bump spring split"
                ],
                "advanced": "Often a weight distribution or rear geometry issue."
            },
            "Lacks Forward Drive": {
                "description": "Car feels slow off the corners, no bite.",
                "quick_fixes": [
                    "Check gear ratio selection",
                    "Increase rear stagger",
                    "Adjust LR shock compression",
                    "Verify tire pressures",
                    "Check for binding in rear suspension"
                ],
                "advanced": "May be a gear ratio or torque converter issue."
            },
            "Bouncing / Porpoising": {
                "description": "Car bounces or oscillates on the track.",
                "quick_fixes": [
                    "Stiffen shock package (compression)",
                    "Check for bottoming - increase bump spring rate",
                    "Raise ride height",
                    "Verify spring rates aren't too soft",
                    "Check shock condition / rebuild"
                ],
                "advanced": "Often a shock valving issue or spring/bump spring mismatch."
            },
            "Chassis Roll - Too Much": {
                "description": "Car rolls excessively in corners.",
                "quick_fixes": [
                    "Stiffen sway bar",
                    "Increase spring rates overall",
                    "Lower ride height",
                    "Stiffen bump springs",
                    "Add rebound to shocks"
                ],
                "advanced": "Consider moment center geometry and CG height."
            },
            "Chassis Roll - Not Enough": {
                "description": "Car feels rigid, doesn't plant rear tires.",
                "quick_fixes": [
                    "Soften sway bar or disconnect",
                    "Soften spring rates",
                    "Raise ride height slightly",
                    "Soften bump springs",
                    "Reduce rebound in shocks"
                ],
                "advanced": "Car may need more mechanical grip. Check tire temps."
            }
        }

        if condition in fixes:
            fix = fixes[condition]
            st.markdown(f"**Condition:** {fix['description']}")
            st.markdown("---")
            st.markdown("**Recommended Adjustments:**")
            for f in fix["quick_fixes"]:
                st.markdown(f"- {f}")
            st.markdown("---")
            st.info(f"**Advanced Note:** {fix['advanced']}")

            # Log the change
            st.markdown("---")
            st.subheader("Log This Adjustment")
            with st.form("log_adjustment"):
                adj_desc = st.text_area("What adjustment did you make?", height=80)
                adj_result = st.selectbox("Result", ["Not Yet Tested", "Improved", "No Change", "Worse"])
                if st.form_submit_button("Save to Tuning Log"):
                    if adj_desc:
                        append_row("tuning", {
                            "date": timestamp_now(),
                            "condition": condition,
                            "adjustment": adj_desc,
                            "result": adj_result,
                            "created": timestamp_now()
                        })
                        st.success("Adjustment logged!")
                        st.rerun()

    # --- Tuning Log ---
    with tab2:
        st.subheader("Tuning Adjustment History")
        log_df = read_sheet("tuning")

        if log_df.empty:
            st.info("No adjustments logged yet. Use the Quick Fixes tab to log changes.")
        else:
            result_filter = st.selectbox("Filter by Result", ["All", "Improved", "No Change", "Worse", "Not Yet Tested"])
            display = log_df.copy()
            if result_filter != "All" and "result" in display.columns:
                display = display[display["result"] == result_filter]

            display_cols = [c for c in ["date", "condition", "adjustment", "result"] if c in display.columns]
            st.dataframe(display[display_cols] if display_cols else display, use_container_width=True, hide_index=True)

            # Stats
            if "result" in log_df.columns:
                st.markdown("---")
                st.subheader("Adjustment Success Rate")
                rc1, rc2, rc3, rc4 = st.columns(4)
                total = len(log_df)
                with rc1:
                    improved = len(log_df[log_df["result"] == "Improved"])
                    st.metric("Improved", improved)
                with rc2:
                    no_change = len(log_df[log_df["result"] == "No Change"])
                    st.metric("No Change", no_change)
                with rc3:
                    worse = len(log_df[log_df["result"] == "Worse"])
                    st.metric("Worse", worse)
                with rc4:
                    untested = len(log_df[log_df["result"] == "Not Yet Tested"])
                    st.metric("Untested", untested)

    # --- Reference ---
    with tab3:
        st.subheader("Quick Reference Charts")

        st.markdown("### Weight & Balance Targets")
        ref1, ref2 = st.columns(2)
        with ref1:
            st.markdown("""**Typical Pro Late Model Ranges:**
- Left Side Weight: 56-58%
- Cross Weight: 49-52%
- Front Weight: 51-54%
- Rear Bite: 10-30 lbs""")
        with ref2:
            st.markdown("""**Tire Pressures (Hot):**
- LF: 12-16 psi
- RF: 18-24 psi
- LR: 14-18 psi
- RR: 18-24 psi""")

        st.markdown("### Spring Rate Guide")
        st.markdown("""
| Position | Soft | Medium | Stiff |
|----------|------|--------|-------|
| LF | 600-700 | 700-850 | 850-1000 |
| RF | 600-700 | 700-850 | 850-1100 |
| LR | 175-200 | 200-250 | 250-350 |
| RR | 175-200 | 200-250 | 250-350 |
""")

        st.markdown("### Gear Ratio Quick Ref")
        st.markdown("""
| Track Size | Suggested Range |
|------------|----------------|
| 1/4 mile | 5.83 - 6.33 |
| 3/8 mile | 5.14 - 5.67 |
| 1/2 mile | 4.56 - 5.14 |
| 5/8+ mile | 4.11 - 4.56 |

*Varies by engine RPM range, tire size, and track surface.*
""")
