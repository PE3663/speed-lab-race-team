import gspread
import streamlit as st
import pandas as pd
import time
from datetime import datetime

# -- Google Sheets Database Helper --
SPREADSHEET_NAME = "SpeedLabRaceTeam"

SHEETS = {
    "chassis": "chassis_profiles",
    "setups": "setups",
    "race_day": "race_day",
    "tires": "tires",
    "parts": "parts_inventory",
    "maintenance": "maintenance",
    "tuning": "tuning_log",
    "tire_reg": "tire_registrations",
        "weekly_checklist": "weekly_checklist",
}


def _has_credentials():
    try:
        sa = st.secrets["gcp_service_account"]
        if sa and sa.get("type") == "service_account":
            return True
    except Exception:
        pass
    return False


def _require_credentials():
    if not _has_credentials():
        st.error(
            "**Google Sheets credentials not configured.** "
            "Go to Manage app > Settings > Secrets and add `[gcp_service_account]`."
        )
        st.stop()


@st.cache_resource(ttl=300)
def _get_client():
    creds = dict(st.secrets["gcp_service_account"])
    return gspread.service_account_from_dict(creds)


@st.cache_resource(ttl=120)
def _get_spreadsheet():
    """Open the spreadsheet once and cache it for 120 seconds."""
    _require_credentials()
    return _get_client().open(SPREADSHEET_NAME)


def get_spreadsheet():
    """Return the cached spreadsheet, with retry on API errors."""
    for attempt in range(3):
        try:
            return _get_spreadsheet()
        except gspread.exceptions.APIError as e:
            if attempt < 2:
                time.sleep(2 ** attempt)
                _get_spreadsheet.clear()
            else:
                raise e


def get_worksheet(sheet_key: str):
    ss = get_spreadsheet()
    tab_name = SHEETS.get(sheet_key, sheet_key)
    try:
        ws = ss.worksheet(tab_name)
    except gspread.WorksheetNotFound:
        ws = ss.add_worksheet(title=tab_name, rows=1000, cols=30)
    return ws


def read_sheet(sheet_key: str) -> pd.DataFrame:
    """Read all data from a sheet tab and return as DataFrame."""
    ws = get_worksheet(sheet_key)
    try:
        all_values = ws.get_all_values()
    except Exception:
        return pd.DataFrame()

    if not all_values or len(all_values) < 2:
        return pd.DataFrame()

    headers = all_values[0]
    # Find the last non-empty header to trim extra blank columns
    num_cols = 0
    for i, h in enumerate(headers):
        if h.strip():
            num_cols = i + 1
    if num_cols == 0:
        return pd.DataFrame()

    headers = headers[:num_cols]
    rows = [r[:num_cols] for r in all_values[1:]]
    # Filter out completely empty rows
    rows = [r for r in rows if any(cell.strip() for cell in r)]
    if not rows:
        return pd.DataFrame()

    return pd.DataFrame(rows, columns=headers)


def append_row(sheet_key: str, row_data: dict):
    """Append a single row. Writes headers to row 1 if sheet is empty."""
    ws = get_worksheet(sheet_key)
    headers = list(row_data.keys())
    existing = ws.get_all_values()

    if not existing or all(cell == "" for cell in existing[0]):
        # Sheet is empty -- write headers in row 1 then data in row 2
        ws.update("A1", [headers])
        row_values = [str(v) for v in row_data.values()]
        ws.update("A2", [row_values])
    else:
        # Sheet has data -- match columns to existing headers
        existing_headers = existing[0]
        # Trim to non-empty headers only
        trimmed = [h for h in existing_headers if h.strip()]
        row_values = [str(row_data.get(h, "")) for h in trimmed]
        ws.append_row(row_values, value_input_option="USER_ENTERED")


def update_row(sheet_key: str, row_index: int, row_data: dict):
    """Update a row at the given 1-based sheet row index."""
    ws = get_worksheet(sheet_key)
    headers = ws.row_values(1)
    # Trim to non-empty headers
    trimmed = [h for h in headers if h.strip()]
    row_values = [str(row_data.get(h, "")) for h in trimmed]
    cell_range = f"A{row_index}:{chr(64 + len(trimmed))}{row_index}"
    ws.update(cell_range, [row_values])


def delete_row(sheet_key: str, row_index: int):
    """Delete a row at the given 1-based sheet row index."""
    ws = get_worksheet(sheet_key)
    ws.delete_rows(row_index)


def get_chassis_list() -> list:
    """Return a list of chassis names from the chassis_profiles sheet."""
    df = read_sheet("chassis")
    if df.empty:
        return []
    if "chassis_name" in df.columns:
        return df["chassis_name"].tolist()
    return []


def timestamp_now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")
