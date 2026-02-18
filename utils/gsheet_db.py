import gspread
import streamlit as st
import pandas as pd
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
        st.error("**Google Sheets credentials not configured.** "
                 "Go to Manage app > Settings > Secrets and add `[gcp_service_account]`.")
        st.stop()


@st.cache_resource(ttl=300)
def _get_client():
    creds = dict(st.secrets["gcp_service_account"])
    return gspread.service_account_from_dict(creds)


def get_spreadsheet():
    _require_credentials()
    return _get_client().open(SPREADSHEET_NAME)


def get_worksheet(sheet_key: str):
    ss = get_spreadsheet()
    tab_name = SHEETS.get(sheet_key, sheet_key)
    try:
        ws = ss.worksheet(tab_name)
    except gspread.WorksheetNotFound:
        ws = ss.add_worksheet(title=tab_name, rows=1000, cols=30)
    return ws


def read_sheet(sheet_key: str) -> pd.DataFrame:
    ws = get_worksheet(sheet_key)
    try:
        data = ws.get_all_records()
    except Exception:
        return pd.DataFrame()
    if data:
        return pd.DataFrame(data)
    return pd.DataFrame()


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
        row_values = [str(row_data.get(h, "")) for h in existing_headers]
        ws.append_row(row_values, value_input_option="USER_ENTERED")


def update_row(sheet_key: str, row_index: int, row_data: dict):
    ws = get_worksheet(sheet_key)
    headers = ws.row_values(1)
    row_values = [str(row_data.get(h, "")) for h in headers]
    cell_range = f"A{row_index}:{chr(64 + len(headers))}{row_index}"
    ws.update(cell_range, [row_values])


def delete_row(sheet_key: str, row_index: int):
    ws = get_worksheet(sheet_key)
    ws.delete_rows(row_index)


def get_chassis_list() -> list:
    df = read_sheet("chassis")
    if df.empty:
        return []
    if "chassis_name" in df.columns:
        return df["chassis_name"].tolist()
    return []


def timestamp_now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")
