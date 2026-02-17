import gspread
import streamlit as st
import pandas as pd
from datetime import datetime

# ── Google Sheets Database Helper ────────────────────────────
# Uses gspread + Streamlit secrets for service account auth.
# Your Google Sheet should be named: "SpeedLabRaceTeam"
# Each module gets its own worksheet tab.
# ──────────────────────────────────────────────────────

SPREADSHEET_NAME = "SpeedLabRaceTeam"

# Worksheet tab names
SHEETS = {
    "chassis": "Chassis",
    "setups": "Setups",
    "race_day": "RaceDayLog",
    "tires": "TireInventory",
    "parts": "PartsInventory",
    "maintenance": "Maintenance",
}


@st.cache_resource(ttl=300)
def _get_client():
    """Authenticate with Google using service account from Streamlit secrets."""
    try:
        creds = dict(st.secrets["gcp_service_account"])
        gc = gspread.service_account_from_dict(creds)
    except Exception:
        # Local dev fallback — uses ~/.config/gspread/service_account.json
        gc = gspread.service_account()
    return gc


def get_spreadsheet():
    """Open the main SpeedLabRaceTeam spreadsheet."""
    gc = _get_client()
    return gc.open(SPREADSHEET_NAME)


def get_worksheet(sheet_key: str):
    """Get or create a worksheet tab by key name."""
    ss = get_spreadsheet()
    tab_name = SHEETS.get(sheet_key, sheet_key)
    try:
        ws = ss.worksheet(tab_name)
    except gspread.WorksheetNotFound:
        ws = ss.add_worksheet(title=tab_name, rows=1000, cols=30)
    return ws


def read_sheet(sheet_key: str) -> pd.DataFrame:
    """Read all data from a worksheet as a DataFrame."""
    ws = get_worksheet(sheet_key)
    data = ws.get_all_records()
    if data:
        return pd.DataFrame(data)
    return pd.DataFrame()


def append_row(sheet_key: str, row_data: dict):
    """Append a single row to a worksheet. Auto-adds headers if empty."""
    ws = get_worksheet(sheet_key)
    existing = ws.get_all_values()
    if not existing:
        # First row — write headers
        headers = list(row_data.keys())
        ws.append_row(headers)
    row_values = list(row_data.values())
    ws.append_row(row_values)


def update_row(sheet_key: str, row_index: int, row_data: dict):
    """Update a specific row (1-indexed, row 1 = headers, row 2 = first data row)."""
    ws = get_worksheet(sheet_key)
    headers = ws.row_values(1)
    row_values = [row_data.get(h, "") for h in headers]
    cell_range = f"A{row_index}:{chr(64 + len(headers))}{row_index}"
    ws.update(cell_range, [row_values])


def delete_row(sheet_key: str, row_index: int):
    """Delete a specific row by index (1-indexed)."""
    ws = get_worksheet(sheet_key)
    ws.delete_rows(row_index)


def get_chassis_list() -> list:
    """Helper: return list of chassis names for dropdowns."""
    df = read_sheet("chassis")
    if df.empty:
        return []
    return df["chassis_name"].tolist()


def timestamp_now() -> str:
    """Return current timestamp string."""
    return datetime.now().strftime("%Y-%m-%d %H:%M")
