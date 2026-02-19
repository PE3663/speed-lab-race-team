import streamlit as st
import pandas as pd
from openai import OpenAI
from utils.gsheet_db import read_sheet, append_row, timestamp_now


def _get_ai_client():
    """Return OpenAI client if API key is configured, else None."""
    try:
        key = st.secrets["openai"]["api_key"]
        if key and key != "YOUR_OPENAI_API_KEY_HERE":
            return OpenAI(api_key=key)
    except Exception:
        pass
    return None


def _build_setup_summary(setup_df):
    """Build a readable summary of the most recent setup for AI context."""
    if setup_df.empty:
        return "No setup data available."
    row = setup_df.iloc[-1]
    lines = [f"Setup: {row.get('setup_name', 'Unknown')} | Chassis: {row.get('chassis', 'Unknown')}"]
    # Springs
    springs = [f"{c}: {row.get(f'spring_{c}', '?')} lbs" for c in ["LF", "RF", "LR", "RR"]]
    lines.append(f"Springs - {', '.join(springs)}")
    # Bump springs
    bumps = [f"{c}: {row.get(f'bump_spring_{c}', '?')} lbs" for c in ["LF", "RF", "LR", "RR"]]
    lines.append(f"Bump Springs - {', '.join(bumps)}")
    # Shocks
    for label, prefix in [("Shock Compression", "shock_comp"), ("Shock Rebound", "shock_reb")]:
        vals = [f"{c}: {row.get(f'{prefix}_{c}', '?')}" for c in ["LF", "RF", "LR", "RR"]]
        lines.append(f"{label} - {', '.join(vals)}")
    # Ride heights
    rh = [f"{c}: {row.get(f'ride_height_{c}', '?')}" for c in ["LF", "RF", "LR", "RR"]]
    lines.append(f"Ride Heights - {', '.join(rh)}")
    # Alignment
    for c in ["LF", "RF", "LR", "RR"]:
        cam = row.get(f"camber_{c}", "?")
        cas = row.get(f"caster_{c}", "?")
        if cas and cas != "?":
            lines.append(f"{c} Camber: {cam}, Caster: {cas}")
        else:
            lines.append(f"{c} Camber: {cam}")
    lines.append(f"Toe: {row.get('toe', '?')}")
    # Weights
    wts = [f"{c}: {row.get(f'weight_{c}', '?')} lbs" for c in ["LF", "RF", "LR", "RR"]]
    lines.append(f"Corner Weights - {', '.join(wts)}")
    lines.append(f"Left%: {row.get('weight_left', '?')}, Rear%: {row.get('weight_rear', '?')}, Cross: {row.get('weight_cross', '?')}")
    # Chassis
    lines.append(f"Gear Ratio: {row.get('gear_ratio', '?')}, Sway Bar: {row.get('sway_bar', '?')}")
    lines.append(f"Track Bar: {row.get('track_bar', '?')}, Panhard: {row.get('panhard', '?')}")
    lines.append(f"Trailing Arm: {row.get('trailing_arm', '?')}, Stagger: {row.get('stagger', '?')}")
    lines.append(f"Tire Pressures: {row.get('tire_pressures', '?')}")
    if row.get("notes"):
        lines.append(f"Notes: {row.get('notes')}")
    return "\n".join(lines)


def _build_history_summary(tuning_df, condition):
    """Build summary of past tuning adjustments for this condition."""
    if tuning_df.empty or "condition" not in tuning_df.columns:
        return "No past tuning history."
    relevant = tuning_df[tuning_df["condition"] == condition]
    if relevant.empty:
        return "No past adjustments logged for this condition."
    lines = []
    for _, r in relevant.tail(5).iterrows():
        result = r.get("result", "Unknown")
        adj = r.get("adjustment", "")
        date = r.get("date", "")
        lines.append(f"- [{result}] {adj} ({date})")
    return "\n".join(lines)


def _ask_ai(client, condition, description, setup_summary, history_summary):
    """Ask OpenAI for setup-specific tuning suggestions."""
    prompt = f"""You are an expert Pro Late Model oval race car chassis tuner and setup engineer.

The driver reports: {condition}
Description: {description}

Current Car Setup:
{setup_summary}

Past Tuning History for this condition:
{history_summary}

Based on the SPECIFIC setup numbers above, provide 4-6 targeted adjustment recommendations.
For each recommendation:
- Reference the actual current values from the setup
- Suggest specific new values or ranges
- Explain briefly why this change helps

Keep responses practical and concise. Format as a numbered list.
End with one sentence about what to check first."""
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=800,
            temperature=0.7,
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"AI error: {e}"


def render():
    st.header("\U0001f3af Trackside Tuning Guide")
    st.markdown("Quick reference for common handling issues and recommended adjustments.")

    tab1, tab2, tab3 = st.tabs(["Quick Fixes", "Tuning Log", "Reference"])

    # --- Quick Fix Guide ---
    with tab1:
        st.subheader("What's the car doing?")
        condition = st.selectbox("Select Handling Condition", [
            "Tight / Push - Entry", "Tight / Push - Center", "Tight / Push - Exit",
            "Loose - Entry", "Loose - Center", "Loose - Exit",
            "Tight Entry / Loose Exit", "Loose Entry / Tight Exit",
            "Lacks Forward Drive", "Bouncing / Porpoising",
            "Chassis Roll - Too Much", "Chassis Roll - Not Enough"
        ])

        fixes = {
            "Tight / Push - Entry": {
                "description": "Car won't turn into the corner on entry.",
                "quick_fixes": ["Soften RF spring or raise RF", "Add LR bite (raise LR or lower RR)", "Decrease RF camber (more negative)", "Increase RF caster", "Soften RF bump spring", "Lower LF air pressure 1-2 psi"],
                "advanced": "Consider more rear stagger, move weight to left side, or adjust sway bar."
            },
            "Tight / Push - Center": {
                "description": "Car pushes through the middle of the corner.",
                "quick_fixes": ["Soften RR spring", "Add more cross weight", "Soften RF shock rebound", "Raise rear ride height", "Add rear stagger", "Soften RF bump spring"],
                "advanced": "Check cross weight percentage, aim for track-specific range."
            },
            "Tight / Push - Exit": {
                "description": "Car pushes coming off the corner.",
                "quick_fixes": ["Stiffen LR spring", "Soften RR shock compression", "Lower RR or raise LR", "Add rear stagger", "Stiffen LR bump spring"],
                "advanced": "May need to adjust panhard bar height or 3-link angles."
            },
            "Loose - Entry": {
                "description": "Rear steps out when entering the corner.",
                "quick_fixes": ["Stiffen RF spring or lower RF", "Soften LR shock rebound", "Reduce rear stagger", "Add RR air pressure 1-2 psi", "Stiffen RF bump spring"],
                "advanced": "Check LR shock for fade, verify rear alignment."
            },
            "Loose - Center": {
                "description": "Rear is loose through the middle of the corner.",
                "quick_fixes": ["Stiffen RR spring", "Remove cross weight", "Stiffen LR shock rebound", "Lower rear ride height", "Stiffen RR bump spring"],
                "advanced": "Consider sway bar adjustment or rear moment center changes."
            },
            "Loose - Exit": {
                "description": "Rear comes around on corner exit / acceleration.",
                "quick_fixes": ["Soften LR spring", "Stiffen RR shock compression", "Raise RR or lower LR", "Reduce rear stagger", "Soften LR bump spring"],
                "advanced": "Verify rear end alignment and pinion angle."
            },
            "Tight Entry / Loose Exit": {
                "description": "Pushes going in, then snaps loose coming off.",
                "quick_fixes": ["Increase LR spring rate", "Decrease RR spring rate", "Adjust shock package for transition", "Check cross weight balance", "Adjust bump spring split LR vs RR"],
                "advanced": "Classic cross-weight or spring split issue. May need full re-scale."
            },
            "Loose Entry / Tight Exit": {
                "description": "Rear rotates on entry but pushes on exit.",
                "quick_fixes": ["Decrease LR spring rate", "Increase RR spring rate", "Adjust RF shock for entry", "Check sway bar preload", "Adjust bump spring split"],
                "advanced": "Often a weight distribution or rear geometry issue."
            },
            "Lacks Forward Drive": {
                "description": "Car feels slow off the corners, no bite.",
                "quick_fixes": ["Check gear ratio selection", "Increase rear stagger", "Adjust LR shock compression", "Verify tire pressures", "Check for binding in rear suspension"],
                "advanced": "May be a gear ratio or torque converter issue."
            },
            "Bouncing / Porpoising": {
                "description": "Car bounces or oscillates on the track.",
                "quick_fixes": ["Stiffen shock package (compression)", "Check for bottoming - increase bump spring rate", "Raise ride height", "Verify spring rates aren't too soft", "Check shock condition / rebuild"],
                "advanced": "Often a shock valving issue or spring/bump spring mismatch."
            },
            "Chassis Roll - Too Much": {
                "description": "Car rolls excessively in corners.",
                "quick_fixes": ["Stiffen sway bar", "Increase spring rates overall", "Lower ride height", "Stiffen bump springs", "Add rebound to shocks"],
                "advanced": "Consider moment center geometry and CG height."
            },
            "Chassis Roll - Not Enough": {
                "description": "Car feels rigid, doesn't plant rear tires.",
                "quick_fixes": ["Soften sway bar or disconnect", "Soften spring rates", "Raise ride height slightly", "Soften bump springs", "Reduce rebound in shocks"],
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

            # --- AI-Powered Suggestions ---
            st.markdown("---")
            ai_client = _get_ai_client()
            if ai_client:
                st.subheader("\U0001f916 AI Setup-Specific Suggestions")
                setup_df = read_sheet("setups")
                if setup_df.empty:
                    st.warning("No setups in Setup Book yet. Add a setup first so AI can analyze your specific numbers.")
                else:
                    setup_names = setup_df["setup_name"].tolist() if "setup_name" in setup_df.columns else []
                    sel_setup = st.selectbox("Analyze which setup?", setup_names, key="ai_setup_sel")
                    if sel_setup:
                        sel_row_df = setup_df[setup_df["setup_name"] == sel_setup]
                    else:
                        sel_row_df = setup_df.tail(1)
                    if st.button("\U0001f9e0 Get AI Suggestions", type="primary", key="ai_suggest_btn"):
                        with st.spinner("Analyzing your setup..."):
                            setup_summary = _build_setup_summary(sel_row_df)
                            tuning_df = read_sheet("tuning")
                            history_summary = _build_history_summary(tuning_df, condition)
                            ai_result = _ask_ai(ai_client, condition, fix["description"], setup_summary, history_summary)
                        st.markdown(ai_result)
                        st.caption("\u26A0\uFE0F AI suggestions are a starting point, not gospel. Always verify with your crew chief's judgment.")
            else:
                with st.expander("\U0001f916 AI Setup-Specific Suggestions"):
                    st.info("To get AI-powered recommendations based on your actual setup, add your OpenAI API key in Streamlit secrets under [openai] > api_key.")
                    st.markdown("Get an API key at [platform.openai.com](https://platform.openai.com/api-keys)")

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
                with rc1:
                    st.metric("Improved", len(log_df[log_df["result"] == "Improved"]))
                with rc2:
                    st.metric("No Change", len(log_df[log_df["result"] == "No Change"]))
                with rc3:
                    st.metric("Worse", len(log_df[log_df["result"] == "Worse"]))
                with rc4:
                    st.metric("Untested", len(log_df[log_df["result"] == "Not Yet Tested"]))

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
