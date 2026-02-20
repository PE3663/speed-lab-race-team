import streamlit as st
import time
from urllib.parse import quote as url_quote
from datetime import date
from PIL import Image
from pyzbar.pyzbar import decode as pyzbar_decode
from utils.gsheet_db import read_sheet, append_row, delete_row, update_row, get_chassis_list, timestamp_now



# --- Helper: build tire number list text for print/email ---
def _build_tire_list_text(category, tire_numbers_list, driver_name, car_number, team_email, reg_date):
    """Build a plain-text tire registration list."""
    lines = []
    lines.append(f"TIRE REGISTRATION \u2014 {category.upper()}")
    lines.append("=" * 40)
    lines.append(f"Date:        {reg_date}")
    if driver_name:
        lines.append(f"Driver:      {driver_name}")
    if car_number:
        lines.append(f"Car #:       {car_number}")
    if team_email:
        lines.append(f"Team Email:  {team_email}")
    lines.append("=" * 40)
    lines.append("")
    lines.append("Registered Tires:")
    lines.append("-" * 20)
    for i, tn in enumerate(tire_numbers_list, 1):
        lines.append(f"  {i}.  {tn}")
    lines.append("")
    lines.append(f"Total: {len(tire_numbers_list)} tires registered")
    lines.append("=" * 40)
    return "\n".join(lines)

# --- Helper: render a registration category tab ---
def _reg_tab(category, icon, reg_df, tire_numbers, tab_key, tires_df=None):
    cat_data = reg_df[reg_df["category"] == category] if not reg_df.empty and "category" in reg_df.columns else None
    if cat_data is not None and not cat_data.empty:
        display_cols = [c for c in ["tire_number", "track_or_series", "mould_mark", "finish_size", "notes", "registered_date"] if c in cat_data.columns]
        st.dataframe(cat_data[display_cols] if display_cols else cat_data, use_container_width=True, hide_index=True)
        if "track_or_series" in cat_data.columns:
            groups = cat_data["track_or_series"].unique().tolist()
            for grp in groups:
                grp_tires = cat_data[cat_data["track_or_series"] == grp]
                with st.expander(f"{icon} {grp} ({len(grp_tires)} tires)"):
                    for _, r in grp_tires.iterrows():
                        tc1, tc2, tc3 = st.columns([3, 1, 1])
                        with tc1:
                            st.markdown(f"**{r.get('tire_number', '')}** \u2014 {r.get('notes', '')}")
                        with tc2:
                            mm = r.get('mould_mark', '')
                            fs = r.get('finish_size', '')
                            if mm or fs:
                                st.caption(f"Mould: {mm} | Size: {fs}")
                        with tc3:
                            st.caption(r.get("registered_date", ""))
    else:
        st.info(f"No tires registered for {category} yet.")

        # --- Print / Email Registration List ---
    if cat_data is not None and not cat_data.empty and "tire_number" in cat_data.columns:
        tire_nums = cat_data["tire_number"].tolist()
        with st.expander(f"🖨️ Print / Email {category} Registration List", expanded=False):
            pc1, pc2 = st.columns(2)
            with pc1:
                driver_name = st.text_input("Driver Name", key=f"{tab_key}_driver")
                car_number = st.text_input("Car Number", key=f"{tab_key}_car_num")
            with pc2:
                team_email = st.text_input("Team Email", key=f"{tab_key}_email")
                reg_date = st.date_input("Date", value=date.today(), key=f"{tab_key}_reg_date")
            reg_date_str = str(reg_date)
            # Build the text
            body_text = _build_tire_list_text(category, tire_nums, driver_name, car_number, team_email, reg_date_str)
            # Print button — renders hidden div and prints it
            tire_list_html = "<br>".join([f"{i}. &nbsp; {tn}" for i, tn in enumerate(tire_nums, 1)])
            print_html = f"""
            <div id="print_{tab_key}" style="display:none;">
                <h2>TIRE REGISTRATION &mdash; {category.upper()}</h2>
                <table style="margin-bottom:1em;">
                    <tr><td><b>Date:</b></td><td id="p_{tab_key}_date">{reg_date_str}</td></tr>
                    <tr><td><b>Driver:</b></td><td id="p_{tab_key}_driver">{driver_name}</td></tr>
                    <tr><td><b>Car #:</b></td><td id="p_{tab_key}_car">{car_number}</td></tr>
                    <tr><td><b>Email:</b></td><td id="p_{tab_key}_email">{team_email}</td></tr>
                </table>
                <h3>Registered Tires:</h3>
                <div style="font-size:14pt;">{tire_list_html}</div>
                <p><b>Total: {len(tire_nums)} tires registered</b></p>
            </div>
            <style>
            @media print {{
                body * {{ visibility: hidden !important; }}
                #print_{tab_key}, #print_{tab_key} * {{ visibility: visible !important; }}
                #print_{tab_key} {{ display: block !important; position: fixed; left: 0; top: 0; width: 100%; padding: 2em; }}
            }}
            </style>
            """
            st.markdown(print_html, unsafe_allow_html=True)
            bc1, bc2 = st.columns(2)
            with bc1:
                st.markdown(
                    f'<button onclick="document.getElementById(\'print_{tab_key}\').style.display=\'block\';window.print();setTimeout(function(){{document.getElementById(\'print_{tab_key}\').style.display=\'none\'}},500)" '
                    'style="background-color:#4CAF50;color:white;padding:0.5rem 1.5rem;'
                    'border:none;border-radius:0.5rem;cursor:pointer;font-size:1rem;width:100%"'
                    '>🖨️ Print Registration List</button>',
                    unsafe_allow_html=True,
                )
            with bc2:
                subject = url_quote(f"Tire Registration - {category} - {reg_date_str}")
                mailto_body = url_quote(body_text)
                mailto_link = f"mailto:{team_email}?subject={subject}&body={mailto_body}"
                st.markdown(
                    f'<a href="{mailto_link}" style="display:inline-block;background-color:#2196F3;color:white;'
                    'padding:0.5rem 1.5rem;border:none;border-radius:0.5rem;cursor:pointer;font-size:1rem;'
                    'text-decoration:none;text-align:center;width:100%"'
                    '>📧 Email Registration List</a>',
                    unsafe_allow_html=True,
                )
            st.markdown("---")
    with st.form(f"reg_{tab_key}_form", clear_on_submit=True):
        st.markdown(f"**Register a Tire for {category}**")
        rc1, rc2 = st.columns(2)
        with rc1:
            if tire_numbers:
                sel_tire = st.selectbox("Select Tire from Inventory", [""] + tire_numbers, key=f"{tab_key}_tire_inv")
                man_tire = st.text_input("Or enter tire number manually", key=f"{tab_key}_tire_manual")
            else:
                sel_tire = ""
                man_tire = st.text_input("Tire Number / Serial", key=f"{tab_key}_tire_manual")
        with rc2:
            loc_name = st.text_input("Track / Series Name", key=f"{tab_key}_loc_name")
            reg_notes = st.text_input("Notes (optional)", key=f"{tab_key}_reg_notes")
        rc3, rc4 = st.columns(2)
        with rc3:
            reg_mould = st.text_input("Mould Mark", key=f"{tab_key}_mould")
        with rc4:
            reg_finish = st.text_input("Finish Size", key=f"{tab_key}_finish")
        if st.form_submit_button(f"Register for {category}", type="primary"):
            final_tire = sel_tire if sel_tire else man_tire
            if not final_tire:
                st.error("Enter or select a tire number.")
            elif not loc_name:
                st.error("Enter a track or series name.")
            else:
                append_row("tire_reg", {
                    "tire_number": final_tire,
                    "category": category,
                    "track_or_series": loc_name,
                    "mould_mark": reg_mould,
                    "finish_size": reg_finish,
                    "notes": reg_notes,
                    "registered_date": timestamp_now(),
                })
                st.success(f"Tire '{final_tire}' registered for {category}!")
                st.rerun()
    if cat_data is not None and not cat_data.empty and "tire_number" in cat_data.columns:
        st.markdown("---")
        del_labels = []
        del_indices = []
        for i, r in cat_data.iterrows():
            label = f"{r.get('tire_number', '')} @ {r.get('track_or_series', '')}"
            del_labels.append(label)
            del_indices.append(i)
        del_choice = st.selectbox("Select registration to remove", del_labels, key=f"del_{tab_key}_reg")
        if st.button("Remove Registration", key=f"del_{tab_key}_btn", type="secondary"):
            sel_idx = del_labels.index(del_choice)
            sheet_row = del_indices[sel_idx] + 2
            delete_row("tire_reg", sheet_row)
            st.success(f"Registration removed: {del_choice}")
            st.rerun()

def render():
    st.header("\U0001f6a2 Tire Inventory")
    tab1, tab2, tab3, tab4 = st.tabs(["View Tires", "Registered Tires", "Add New Tire", "Tire Temp"])

    # ==============================================
    # TAB 1 -- View Tires (Inventory)
    # ==============================================
    with tab1:
        df = read_sheet("tires")
        if not df.empty:
            fc1, fc2, fc3 = st.columns(3)
            with fc1:
                status_filt = st.selectbox("Status", ["All", "New", "Practice", "Delaware", "Series", "Used", "Scrapped"])
            with fc2:
                pos_filt = st.selectbox("Position", ["All", "LF", "RF", "LR", "RR", "Spare"])
            with fc3:
                compound_filt = st.text_input("Compound Filter")
            filtered = df.copy()
            if status_filt != "All" and "status" in filtered.columns:
                filtered = filtered[filtered["status"] == status_filt]
            if pos_filt != "All" and "position" in filtered.columns:
                filtered = filtered[filtered["position"] == pos_filt]
            if compound_filt and "compound" in filtered.columns:
                filtered = filtered[filtered["compound"].str.contains(compound_filt, case=False, na=False)]
            st.dataframe(filtered, use_container_width=True, hide_index=True)

            st.divider()
            st.subheader("Quick Stats")
            sc1, sc2, sc3, sc4 = st.columns(4)
            with sc1:
                st.metric("Total", len(df))
            with sc2:
                st.metric("New", len(df[df["status"] == "New"]) if "status" in df.columns else 0)
            with sc3:
                st.metric("Delaware", len(df[df["status"] == "Delaware"]) if "status" in df.columns else 0)
            with sc4:
                st.metric("Used", len(df[df["status"] == "Used"]) if "status" in df.columns else 0)

            # --- Edit Tire ---
            st.divider()
            st.subheader("Edit Tire")
            if "tire_number" in df.columns:
                edit_labels = df["tire_number"].tolist()
                edit_sel = st.selectbox("Select tire to edit", edit_labels, key="edit_tire_sel")
                if edit_sel:
                    row_idx = df[df["tire_number"] == edit_sel].index[0]
                    row = df.iloc[row_idx]
                    with st.form("edit_tire_form", clear_on_submit=False):
                        ec1, ec2 = st.columns(2)
                        with ec1:
                            e_status = st.selectbox("Status", ["New", "Practice", "Delaware", "Series", "Used", "Scrapped"], index=["New", "Practice", "Delaware", "Series", "Used", "Scrapped"].index(row.get("status", "New")) if row.get("status", "New") in ["New", "Practice", "Delaware", "Series", "Used", "Scrapped"] else 0)
                            e_position = st.selectbox("Position", ["LF", "RF", "LR", "RR", "Spare"], index=["LF", "RF", "LR", "RR", "Spare"].index(row.get("position", "LF")) if row.get("position", "LF") in ["LF", "RF", "LR", "RR", "Spare"] else 0)
                            e_durometer = st.text_input("Durometer Reading", value=row.get("durometer", ""))
                            e_mould_mark = st.text_input("Mould Mark", value=row.get("mould_mark", ""))
                        with ec2:
                            e_laps = st.text_input("Laps Run", value=row.get("laps_run", "0"))
                            e_races = st.text_input("Races Run", value=row.get("races_run", "0"))
                            e_circumference = st.text_input("Circumference / Rollout", value=row.get("circumference", ""))
                            e_finish_size = st.text_input("Finish Size", value=row.get("finish_size", ""))
                        e_notes = st.text_area("Notes", value=row.get("notes", ""))
                        if st.form_submit_button("Update Tire", type="primary"):
                            updated = row.to_dict()
                            updated["status"] = e_status
                            updated["position"] = e_position
                            updated["durometer"] = e_durometer
                            updated["laps_run"] = e_laps
                            updated["races_run"] = e_races
                            updated["circumference"] = e_circumference
                            updated["mould_mark"] = e_mould_mark
                            updated["finish_size"] = e_finish_size
                            updated["notes"] = e_notes
                            update_row("tires", row_idx + 2, updated)
                            st.success(f"Tire '{edit_sel}' updated!")
                            st.rerun()

            # --- Delete Tire ---
            st.divider()
            st.subheader("Delete Tire")
            if "tire_number" in df.columns:
                del_sel = st.selectbox("Select tire to delete", df["tire_number"].tolist(), key="del_tire_sel")
                if st.button("Delete Selected Tire", type="secondary"):
                    row_idx = df[df["tire_number"] == del_sel].index[0] + 2
                    delete_row("tires", row_idx)
                    # Also remove any registrations for this tire
                    reg_df = read_sheet("tire_reg")
                    if not reg_df.empty and "tire_number" in reg_df.columns:
                        reg_matches = reg_df[reg_df["tire_number"] == del_sel]
                        if not reg_matches.empty:
                            for ri in sorted(reg_matches.index.tolist(), reverse=True):
                                delete_row("tire_reg", ri + 2)
                    st.success(f"Tire '{del_sel}' deleted!")
                    st.rerun()
        else:
            st.info("No tires in inventory. Add your first tire below.")

    # ==============================================
    # TAB 2 -- Registered Tires
    # ==============================================
    with tab2:
        st.subheader("Registered Tires")
        st.caption("Track which tires are registered for Practice, Delaware, or Series. Add, view, and remove registrations below.")
        reg_df = read_sheet("tire_reg")
        tire_df = read_sheet("tires")
        tire_numbers = tire_df["tire_number"].tolist() if not tire_df.empty and "tire_number" in tire_df.columns else []

        # --- Summary metrics ---
        prac_count = 0
        del_count = 0
        ser_count = 0
        if not reg_df.empty and "category" in reg_df.columns:
            prac_count = len(reg_df[reg_df["category"] == "Practice"])
            del_count = len(reg_df[reg_df["category"] == "Delaware"])
            ser_count = len(reg_df[reg_df["category"] == "Series"])
        mc1, mc2, mc3, mc4 = st.columns(4)
        with mc1:
            st.metric("Total Registered", prac_count + del_count + ser_count)
        with mc2:
            st.metric("Practice", prac_count)
        with mc3:
            st.metric("Delaware", del_count)
        with mc4:
            st.metric("Series", ser_count)
        st.divider()
        reg_prac, reg_del, reg_ser = st.tabs(["\U0001f3ce Practice", "\U0001f3c1 Delaware", "\U0001f3c6 Series"])
        with reg_prac:
            _reg_tab("Practice", "\U0001f3ce", reg_df, tire_numbers, "prac", tire_df)
        with reg_del:
            _reg_tab("Delaware", "\U0001f3c1", reg_df, tire_numbers, "del", tire_df)
        with reg_ser:
            _reg_tab("Series", "\U0001f3c6", reg_df, tire_numbers, "ser", tire_df)

    # ==============================================
    # TAB 3 -- Add New Tire
    # ==============================================
    with tab3:
        chassis_list = get_chassis_list()
        if "scanned_tire_number" not in st.session_state:
            st.session_state["scanned_tire_number"] = ""

        # --- Barcode Scanner using camera ---
        with st.expander("\U0001f4f7 Scan Barcode", expanded=False):
            st.caption("Take a photo of the barcode on the tire. The app will read the number automatically.")
            camera_img = st.camera_input("Point camera at barcode", key="tire_barcode_cam")
            if camera_img is not None:
                try:
                    img = Image.open(camera_img)
                    decoded = pyzbar_decode(img)
                    if decoded:
                        barcode_val = decoded[0].data.decode("utf-8")
                        st.session_state["scanned_tire_number"] = barcode_val
                        st.success(f"Scanned: **{barcode_val}** -- pre-filled below")
                    else:
                        st.warning("No barcode detected. Try again with better lighting or hold the barcode closer.")
                except Exception as e:
                    st.error(f"Scanner error: {e}")
        if st.session_state["scanned_tire_number"]:
            st.success(f"Scanned: **{st.session_state['scanned_tire_number']}** -- pre-filled below")

        with st.form("add_tire", clear_on_submit=True):
            st.subheader("New Tire Entry")
            c1, c2 = st.columns(2)
            with c1:
                tire_number = st.text_input(
                    "Tire Number / Serial *",
                    value=st.session_state.get("scanned_tire_number", "")
                )
                brand = st.text_input("Brand (e.g. Hoosier)")
                compound = st.text_input("Compound (e.g. LM20, LM40, D800)")
                mould_mark = st.text_input("Mould Mark")
                finish_size = st.text_input("Finish Size")
            with c2:
                position = st.selectbox("Position", ["LF", "RF", "LR", "RR", "Spare"])
                status = st.selectbox("Status", ["New", "Practice", "Delaware", "Series", "Used", "Scrapped"])
                assigned_chassis = st.selectbox("Assigned Chassis", [""] + chassis_list)
                date_purchased = st.date_input("Date Purchased")
            st.markdown("---")
            c3, c4 = st.columns(2)
            with c3:
                durometer = st.text_input("Durometer Reading")
                circumference = st.text_input("Circumference / Rollout")
            with c4:
                laps_run = st.number_input("Laps Run", min_value=0, value=0)
                races_run = st.number_input("Races Run", min_value=0, value=0)
            notes = st.text_area("Notes (heat cycles, shaving, etc.)")
            if st.form_submit_button("Save Tire", type="primary"):
                if not tire_number:
                    st.error("Tire number is required.")
                else:
                    append_row("tires", {
                        "tire_number": tire_number,
                        "brand": brand,
                        "compound": compound,
                        "mould_mark": mould_mark,
                        "finish_size": finish_size,
                        "position": position,
                        "status": status,
                        "assigned_chassis": assigned_chassis,
                        "date_purchased": str(date_purchased),
                        "durometer": durometer,
                        "circumference": circumference,
                        "laps_run": laps_run,
                        "races_run": races_run,
                        "notes": notes,
                        "created": timestamp_now(),
                    })
                    # Auto-register for Practice, Delaware, or Series
                    if status in ["Practice", "Delaware", "Series"]:
                        time.sleep(2)
                        try:
                            append_row("tire_reg", {
                                "tire_number": tire_number,
                                "category": status,
                                "track_or_series": status,
                                "mould_mark": mould_mark,
                                "finish_size": finish_size,
                                "notes": notes,
                                "registered_date": timestamp_now(),
                            })
                            st.success(f"Tire '{tire_number}' added and registered for {status}!")
                        except Exception as e:
                            st.warning(f"Tire saved but auto-registration failed: {e}")
                    else:
                        st.success(f"Tire '{tire_number}' added!")
                    st.session_state["scanned_tire_number"] = ""
                    st.rerun()

    # ==============================================
    # TAB 4 -- Tire Temp (Camber Analysis)
    # ==============================================
    with tab4:
        st.subheader("Tire Temperature Analysis")
        st.caption("Enter tire temps (Inner, Middle, Outer) for each corner. The app will analyze camber based on the temperature spread.")
        corners = ["LF", "RF", "LR", "RR"]
        temps = {}
        for corner in corners:
            with st.expander(f"\U0001f321 {corner} Temps", expanded=True):
                tc1, tc2, tc3 = st.columns(3)
                with tc1:
                    t_in = st.number_input(f"{corner} Inner", min_value=0.0, max_value=500.0, value=0.0, step=1.0, key=f"{corner}_in")
                with tc2:
                    t_mid = st.number_input(f"{corner} Middle", min_value=0.0, max_value=500.0, value=0.0, step=1.0, key=f"{corner}_mid")
                with tc3:
                    t_out = st.number_input(f"{corner} Outer", min_value=0.0, max_value=500.0, value=0.0, step=1.0, key=f"{corner}_out")
                temps[corner] = {"inner": t_in, "middle": t_mid, "outer": t_out}

        st.divider()
        st.subheader("Camber Analysis Results")
        any_data = any(t["inner"] > 0 or t["outer"] > 0 for t in temps.values())
        if not any_data:
            st.info("Enter tire temperatures above to see camber analysis.")
        else:
            for corner in corners:
                t = temps[corner]
                t_in = t["inner"]
                t_out = t["outer"]
                t_mid = t["middle"]
                if t_in == 0 and t_out == 0:
                    continue
                camber_delta = t_in - t_out
                if camber_delta > 10:
                    camber_status = "Too much negative camber"
                    camber_advice = "Reduce negative camber on this corner."
                    icon = "\u26a0\ufe0f"
                elif camber_delta < -10:
                    camber_status = "Not enough negative camber"
                    camber_advice = "Add negative camber or increase roll resistance on this corner."
                    icon = "\u26a0\ufe0f"
                else:
                    camber_status = "Camber OK"
                    camber_advice = "Camber close; adjust only for fine balance."
                    icon = "\u2705"
                with st.container():
                    rc1, rc2 = st.columns([1, 3])
                    with rc1:
                        st.metric(f"{corner} Delta", f"{camber_delta:+.1f}\u00b0")
                    with rc2:
                        st.markdown(f"{icon} **{camber_status}**")
                        st.caption(camber_advice)
                    st.caption(f"Inner: {t_in}\u00b0 | Mid: {t_mid}\u00b0 | Outer: {t_out}\u00b0")
                    st.markdown("---")
