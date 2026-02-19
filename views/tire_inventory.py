import streamlit as st
import streamlit.components.v1 as components
from utils.gsheet_db import read_sheet, append_row, delete_row, get_chassis_list, timestamp_now

SCANNER_HTML = """
<style>
  body { margin: 0; padding: 0; }
  #scanner-wrap { font-family: sans-serif; }
  #video { width: 100%; max-width: 400px; border-radius: 8px; display: none; }
  #scan-btn {
    background: #e74c3c; color: white; border: none;
    padding: 10px 20px; border-radius: 6px; font-size: 15px;
    cursor: pointer; margin-bottom: 8px;
  }
  #scan-btn.active { background: #27ae60; }
  #result-box {
    margin-top: 8px; padding: 8px 12px;
    background: #1e2a3a; color: #7fdbca;
    border-radius: 6px; font-size: 14px;
    display: none;
  }
  #send-btn {
    background: #2980b9; color: white; border: none;
    padding: 8px 18px; border-radius: 6px; font-size: 14px;
    cursor: pointer; margin-top: 6px; display: none;
  }
</style>
<div id="scanner-wrap">
  <button id="scan-btn" onclick="toggleScanner()">&#x1F4F7; Scan Barcode</button><br>
  <video id="video" autoplay playsinline></video>
  <canvas id="canvas" style="display:none"></canvas>
  <div id="result-box"></div>
  <button id="send-btn" onclick="sendResult()">Use this number</button>
</div>
<script src="https://unpkg.com/@zxing/browser@latest/umd/index.min.js"></script>
<script>
  let codeReader = null;
  let scanning = false;
  let lastResult = "";

  function toggleScanner() {
    if (scanning) { stopScanner(); } else { startScanner(); }
  }

  function startScanner() {
    scanning = true;
    const btn = document.getElementById('scan-btn');
    btn.textContent = '\\u23F9 Stop Scanner';
    btn.classList.add('active');
    document.getElementById('video').style.display = 'block';

    codeReader = new ZXingBrowser.BrowserMultiFormatReader();
    codeReader.decodeFromVideoDevice(null, 'video', (result, err) => {
      if (result) {
        lastResult = result.getText();
        document.getElementById('result-box').style.display = 'block';
        document.getElementById('result-box').textContent = '\\u2705 Scanned: ' + lastResult;
        document.getElementById('send-btn').style.display = 'inline-block';
        stopScanner();
      }
    });
  }

  function stopScanner() {
    scanning = false;
    if (codeReader) { codeReader.reset(); codeReader = null; }
    const btn = document.getElementById('scan-btn');
    btn.textContent = '\\u1F4F7 Scan Barcode';
    btn.classList.remove('active');
    document.getElementById('video').style.display = 'none';
  }

  function sendResult() {
    window.parent.postMessage({ type: 'barcode_result', value: lastResult }, '*');
  }
</script>
"""

def render():
  st.header("\U0001f6a5 Tire Inventory")

  tab1, tab2 = st.tabs(["View Tires", "Add New Tire"])

  with tab1:
    # =============================================
    # Registered Tires Section
    # =============================================
    st.subheader("Registered Tires")
    st.caption("Track which tires are registered for your Home Track and Series.")

    reg_df = read_sheet("tire_reg")
    tire_df = read_sheet("tires")
    tire_numbers = tire_df["tire_number"].tolist() if not tire_df.empty and "tire_number" in tire_df.columns else []

    reg_ht, reg_ser = st.tabs(["\U0001f3e0 Home Track", "\U0001f3c6 Series"])

    # --- Home Track ---
    with reg_ht:
      ht_data = reg_df[reg_df["category"] == "Home Track"] if not reg_df.empty and "category" in reg_df.columns else None
      if ht_data is not None and not ht_data.empty:
        st.dataframe(ht_data[[c for c in ht_data.columns if c != "category"]], use_container_width=True, hide_index=True)
      else:
        st.info("No tires registered for Home Track yet.")

      with st.form("reg_ht_form", clear_on_submit=True):
        rc1, rc2 = st.columns(2)
        with rc1:
          ht_tire = st.text_input("Tire Number / Serial", key="ht_tire_num")
        with rc2:
          ht_track = st.text_input("Track Name", key="ht_track_name")
        ht_notes = st.text_input("Notes (optional)", key="ht_reg_notes")
        if st.form_submit_button("Register for Home Track", type="primary"):
          if not ht_tire:
            st.error("Enter a tire number.")
          else:
            append_row("tire_reg", {
              "tire_number": ht_tire,
              "category": "Home Track",
              "track_or_series": ht_track,
              "notes": ht_notes,
              "registered_date": timestamp_now(),
            })
            st.success(f"Tire '{ht_tire}' registered for Home Track!")
            st.rerun()

    # --- Series ---
    with reg_ser:
      ser_data = reg_df[reg_df["category"] == "Series"] if not reg_df.empty and "category" in reg_df.columns else None
      if ser_data is not None and not ser_data.empty:
        st.dataframe(ser_data[[c for c in ser_data.columns if c != "category"]], use_container_width=True, hide_index=True)
      else:
        st.info("No tires registered for Series yet.")

      with st.form("reg_ser_form", clear_on_submit=True):
        sc1, sc2 = st.columns(2)
        with sc1:
          ser_tire = st.text_input("Tire Number / Serial", key="ser_tire_num")
        with sc2:
          ser_name = st.text_input("Series Name", key="ser_series_name")
        ser_notes = st.text_input("Notes (optional)", key="ser_reg_notes")
        if st.form_submit_button("Register for Series", type="primary"):
          if not ser_tire:
            st.error("Enter a tire number.")
          else:
            append_row("tire_reg", {
              "tire_number": ser_tire,
              "category": "Series",
              "track_or_series": ser_name,
              "notes": ser_notes,
              "registered_date": timestamp_now(),
            })
            st.success(f"Tire '{ser_tire}' registered for Series!")
            st.rerun()

    st.divider()

    # =============================================
    # Tire Inventory Table
    # =============================================
    st.subheader("All Tires")
    df = read_sheet("tires")
    if not df.empty:
      # Filters
      fc1, fc2, fc3 = st.columns(3)
      with fc1:
        status_filt = st.selectbox("Status", ["All", "New", "In Use", "Used", "Scrapped"])
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
        st.metric("In Use", len(df[df["status"] == "In Use"]) if "status" in df.columns else 0)
      with sc4:
        st.metric("Used", len(df[df["status"] == "Used"]) if "status" in df.columns else 0)
    else:
      st.info("No tires in inventory. Add your first tire below.")

  with tab2:
    chassis_list = get_chassis_list()

    # --- Barcode Scanner (outside form so session_state can update) ---
    if "scanned_tire_number" not in st.session_state:
      st.session_state["scanned_tire_number"] = ""

    components.html(
      SCANNER_HTML + """
      <script>
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
      height=60,
    )

    # Pick up barcode from query params if present
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
        status = st.selectbox("Status", ["New", "In Use", "Used", "Scrapped"])
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
