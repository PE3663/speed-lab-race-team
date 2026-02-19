import streamlit as st
import pandas as pd
from openai import OpenAI
from utils.gsheet_db import read_sheet, append_row, timestamp_now


def _get_ai_client():
    """Return Perplexity Sonar client if API key is configured, else None."""
    try:
        key = st.secrets["perplexity"]["api_key"]
        if key and key != "YOUR_PERPLEXITY_API_KEY_HERE":
            return OpenAI(api_key=key, base_url="https://api.perplexity.ai")
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


def _get_ai_suggestion(client, setup_summary, symptom):
    """Ask Perplexity Sonar for tuning advice based on setup and symptom."""
    system_msg = (
        "You are an expert oval-track racing engineer specializing in Pro Late Model "
        "stock cars. The driver will describe a handling problem and provide their current "
        "chassis setup. Respond with concise, actionable adjustment recommendations. "
        "For each recommendation, explain WHAT to change, HOW MUCH to change it, "
        "and WHY it helps. Keep the response under 300 words. "
        "Focus on the most impactful 2-3 changes."
    )
    user_msg = (
        f"Current Setup:\n{setup_summary}\n\n"
        f"Problem: {symptom}\n\n"
        "What specific setup changes do you recommend?"
    )
    try:
        resp = client.chat.completions.create(
            model="sonar",
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
            max_tokens=500,
            temperature=0.3,
        )
        return resp.choices[0].message.content
    except Exception as e:
        return f"AI error: {e}"


# --------------- Hardcoded knowledge base (fallback) ---------------
SYMPTOM_FIXES = {
    "Tight / Pushes in center": [
        "Soften RF spring 25-50 lbs",
        "Add LR bite (raise panhard bar on left)",
        "Reduce cross-weight 0.2-0.5%",
        "Increase LR rebound 1-2 clicks",
    ],
    "Loose off corner": [
        "Stiffen RR spring 25-50 lbs",
        "Lower panhard bar on right side",
        "Add cross-weight 0.2-0.5%",
        "Increase RR rebound 1-2 clicks",
    ],
    "Tight on entry": [
        "Soften RF shock compression 1-2 clicks",
        "Reduce LF spring rate 25 lbs",
        "Increase front stagger slightly",
    ],
    "Loose on entry": [
        "Stiffen RF shock compression 1-2 clicks",
        "Add LF spring rate 25 lbs",
        "Lower rear ride height 1/4 inch",
    ],
    "No forward bite off corner": [
        "Soften RR spring 25-50 lbs",
        "Lower rear ride height",
        "Check LR shock rebound - may be too stiff",
        "Increase rear stagger",
    ],
    "Bouncing / Unstable": [
        "Increase shock rebound all corners 1-2 clicks",
        "Check for worn shocks",
        "Raise ride height if bottoming out",
        "Review spring rates for track conditions",
    ],
}


def show():
    st.header("Trackside Tuning")

    ai_client = _get_ai_client()

    # ---- load setup data for AI context ----
    try:
        setup_df = read_sheet("Setups")
    except Exception:
        setup_df = pd.DataFrame()

    setup_summary = _build_setup_summary(setup_df)

    # ---- What's the car doing? ----
    st.subheader("What's the car doing?")
    symptom = st.selectbox(
        "Select handling issue",
        list(SYMPTOM_FIXES.keys()),
    )

    if st.button("Get Recommendations", type="primary"):
        st.markdown("---")

        # AI-powered recommendation
        if ai_client and setup_summary != "No setup data available.":
            with st.spinner("Analyzing setup with AI..."):
                ai_advice = _get_ai_suggestion(ai_client, setup_summary, symptom)
            st.subheader("AI Recommendation")
            st.info("Based on your actual setup data and the selected handling issue:")
            st.markdown(ai_advice)
            st.markdown("---")

        # Hardcoded quick fixes (always shown)
        st.subheader("Quick Reference Fixes")
        fixes = SYMPTOM_FIXES.get(symptom, [])
        for fix in fixes:
            st.markdown(f"- {fix}")

        if not ai_client:
            st.caption("Tip: Add a Perplexity API key in Streamlit secrets for AI-powered recommendations tailored to your setup.")

    # ---- Tuning Log ----
    st.markdown("---")
    st.subheader("Tuning Log")
    with st.form("tuning_log_form"):
        col1, col2 = st.columns(2)
        with col1:
            log_date = st.date_input("Date")
            log_track = st.text_input("Track")
        with col2:
            log_session = st.selectbox("Session", ["Practice", "Qualifying", "Heat", "Feature"])
            log_condition = st.selectbox("Track Condition", ["Dry/Slick", "Tacky", "Heavy", "Wet"])
        log_symptom = st.text_input("Symptom / Handling Issue")
        log_change = st.text_area("Change Made")
        log_result = st.text_area("Result / Notes")
        submitted = st.form_submit_button("Save Log Entry")
        if submitted and log_symptom:
            append_row("TuningLog", {
                "timestamp": timestamp_now(),
                "date": str(log_date),
                "track": log_track,
                "session": log_session,
                "condition": log_condition,
                "symptom": log_symptom,
                "change": log_change,
                "result": log_result,
            })
            st.success("Log entry saved!")

    # Show recent log entries
    try:
        log_df = read_sheet("TuningLog")
        if not log_df.empty:
            st.dataframe(log_df.tail(10).iloc[::-1], use_container_width=True)
    except Exception:
        st.caption("No tuning log entries yet.")
