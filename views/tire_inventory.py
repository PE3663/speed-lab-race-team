import streamlit as st
import streamlit.components.v1 as components
from utils.gsheet_db import read_sheet, append_row, delete_row, update_row, get_chassis_list, timestamp_now


SCANNER_HTML = """
<style>
  body { margin: 0; padding: 0; }
  #scanner-wrap { font-family: sans-serif; }
  #scan-btn {
    background: #e74c3c; color: white; border: none;
    padding: 10px 20px; border-radius: 6px; font-size: 15px;
    cursor: pointer; margin-bottom: 8px;
  }
  #scan-btn.active { background: #27ae60; }
  #video {
    width: 100%; max-width: 400px; border-radius: 8px;
    display: none;
  }
  #result-box {
    margin-top: 8px; padding: 8px 12px;
    background: #1e2a3a; color: #7fdbca;
    border-radius: 6px; font-size: 14px; display: none;
  }
  #send-btn {
    background: #2980b9; color: white; border: none;
    padding: 8px 18px; border-radius: 6px; font-size: 14px;
    cursor: pointer; margin-top: 6px; display: none;
  }
  #file-input { display: none; }
  #error-box {
    margin-top: 8px; padding: 8px 12px;
    background: #3a1e1e; color: #ff8a80;
    border-radius: 6px; font-size: 13px; display: none;
  }
</style>
<div id="scanner-wrap">
  <button id="scan-btn" onclick="startScanner()">&#x1F4F7; Scan Barcode</button><br>
  <video id="video" autoplay playsinline></video>
  <canvas id="canvas" style="display:none"></canvas>
  <input type="file" id="file-input" accept="image/*" capture="environment" onchange="handleFileCapture(event)">
  <div id="result-box"></div>
  <div id="error-box"></div>
  <button id="send-btn" onclick="sendResult()">Use this number</button>
</div>
<script src="https://unpkg.com/@zxing/browser@0.1.4/umd/index.min.js"></script>
<script>
let codeReader = null;
let scanning = false;
let lastResult = "";
let stream = null;

function showError(msg) {
  var eb = document.getElementById('error-box');
  eb.textContent = msg;
  eb.style.display = 'block';
  setTimeout(function() { eb.style.display = 'none'; }, 5000);
}

function startScanner() {
  var errorBox = document.getElementById('error-box');
  errorBox.style.display = 'none';
  // Try live video first, fall back to file capture
  if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
    navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } })
      .then(function(s) {
        stream = s;
        scanning = true;
        var btn = document.getElementById('scan-btn');
        btn.textContent = '\u23F9 Stop Scanner';
        btn.classList.add('active');
        var video = document.getElementById('video');
        video.style.display = 'block';
        video.srcObject = stream;
        codeReader = new ZXingBrowser.BrowserMultiFormatReader();
        codeReader.decodeFromVideoDevice(null, 'video', function(result, err) {
          if (result) {
            lastResult = result.getText();
            document.getElementById('result-box').style.display = 'block';
            document.getElementById('result-box').textContent = '\u2705 Scanned: ' + lastResult;
            document.getElementById('send-btn').style.display = 'inline-block';
            stopScanner();
          }
        });
      })
      .catch(function(err) {
        // Camera denied or not available - use file capture
        document.getElementById('file-input').click();
      });
  } else {
    // No getUserMedia - use file capture
    document.getElementById('file-input').click();
  }
}

function stopScanner() {
  scanning = false;
  if (stream) {
    stream.getTracks().forEach(function(t) { t.stop(); });
    stream = null;
  }
  if (codeReader) {
    codeReader.reset();
    codeReader = null;
  }
  var btn = document.getElementById('scan-btn');
  btn.textContent = '\u1F4F7 Scan Barcode';
  btn.classList.remove('active');
  document.getElementById('video').style.display = 'none';
}

function handleFileCapture(event) {
  var file = event.target.files[0];
  if (!file) return;
  var img = new Image();
  var reader = new FileReader();
  reader.onload = function(e) {
    img.onload = function() {
      var canvas = document.getElementById('canvas');
      canvas.width = img.width;
      canvas.height = img.height;
      var ctx = canvas.getContext('2d');
      ctx.drawImage(img, 0, 0);
      try {
        var zxingReader = new ZXingBrowser.BrowserMultiFormatReader();
        var luminance = ZXingBrowser.HTMLCanvasElementLuminanceSource
          ? new ZXingBrowser.HTMLCanvasElementLuminanceSource(canvas)
          : null;
        // Decode from image URL instead
        zxingReader.decodeFromImageUrl(e.target.result)
          .then(function(result) {
            lastResult = result.getText();
            document.getElementById('result-box').style.display = 'block';
            document.getElementById('result-box').textContent = '\u2705 Scanned: ' + lastResult;
            document.getElementById('send-btn').style.display = 'inline-block';
          })
          .catch(function(err) {
            showError('No barcode found in image. Try again with better lighting.');
          });
      } catch(err) {
        showError('Scanner error: ' + err.message);
      }
    };
    img.src = e.target.result;
  };
  reader.readAsDataURL(file);
  event.target.value = '';
}

function sendResult() {
  window.parent.postMessage({ type: 'barcode_result', value: lastResult }, '*');
}
</script>
"""


# --- Helper: render a registration category tab ---
def _reg_tab(category, icon, reg_df, tire_numbers, tab_key):
  cat_data = reg_df[reg_df["category"] == category] if not reg_df.empty and "category" in reg_df.columns else None
  if cat_data is not None and not cat_data.empty:
    display_cols = [c for c in ["tire_number", "track_or_series", "notes", "registered_date"] if c in cat_data.columns]
    st.dataframe(cat_data[display_cols] if display_cols else cat_data, use_container_width=True, hide_index=True)
    if "track_or_series" in cat_data.columns:
      groups = cat_data["track_or_series"].unique().tolist()
      for grp in groups:
        grp_tires = cat_data[cat_data["track_or_series"] == grp]
        with st.expander(f"{icon} {grp} ({len(grp_tires)} tires)"):
          for _, r in grp_tires.iterrows():
            tc1, tc2 = st.columns([3, 1])
            with tc1:
              st.markdown(f"**{r.get('tire_number', '')}** \u2014 {r.get('notes', '')}")
            with tc2:
              st.caption(r.get("registered_date", ""))
  else:
    st.info(f"No tires registered for {category} yet.")
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
  tab1, tab2, tab3 = st.tabs(["View Tires", "Registered Tires", "Add New Tire"])
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
            with ec2:
              e_laps = st.text_input("Laps Run", value=row.get("laps_run", "0"))
              e_races = st.text_input("Races Run", value=row.get("races_run", "0"))
              e_circumference = st.text_input("Circumference / Rollout", value=row.get("circumference", ""))
            e_notes = st.text_area("Notes", value=row.get("notes", ""))
            if st.form_submit_button("Update Tire", type="primary"):
              updated = row.to_dict()
              updated["status"] = e_status
              updated["position"] = e_position
              updated["durometer"] = e_durometer
              updated["laps_run"] = e_laps
              updated["races_run"] = e_races
              updated["circumference"] = e_circumference
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
      _reg_tab("Practice", "\U0001f3ce", reg_df, tire_numbers, "prac")
    with reg_del:
      _reg_tab("Delaware", "\U0001f3c1", reg_df, tire_numbers, "del")
    with reg_ser:
      _reg_tab("Series", "\U0001f3c6", reg_df, tire_numbers, "ser")
  # ==============================================
  # TAB 3 -- Add New Tire
  # ==============================================
  with tab3:
    chassis_list = get_chassis_list()
    if "scanned_tire_number" not in st.session_state:
      st.session_state["scanned_tire_number"] = ""
    components.html(
      SCANNER_HTML + """
      window.addEventListener('message', function(e) {
        if (e.data && e.data.type === 'barcode_result') {
          const url = new URL(window.parent.location.href);
          url.searchParams.set('barcode', e.data.value);
          window.parent.history.replaceState({}, '', url);
          window.parent.location.reload();
        }
      });
      </script>
      """,
      height=200,
    )
    params = st.query_params
    if "barcode" in params and params["barcode"]:
      st.session_state["scanned_tire_number"] = params["barcode"]
      st.query_params.clear()
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
        size = st.text_input("Size (e.g. 90/11-15)")
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
            "size": size,
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
          st.session_state["scanned_tire_number"] = ""
          st.success(f"Tire '{tire_number}' added!")
          st.rerun()
