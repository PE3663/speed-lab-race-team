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
        "roll_centres": "roll_centres",
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


def _api_retry(func, *args, max_retries=3, **kwargs):
    """Retry a Google Sheets API call with exponential backoff."""
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except gspread.exceptions.APIError as e:
            if attempt < max_retries - 1:
                wait = 2 ** attempt
                time.sleep(wait)
                _get_spreadsheet.clear()
            else:
                raise e


def get_worksheet(sheet_key: str):
    ss = get_spreadsheet()
    tab_name = SHEETS.get(sheet_key, sheet_key)
    try:
        ws = _api_retry(ss.worksheet, tab_name)
    except gspread.WorksheetNotFound:
        ws = _api_retry(ss.add_worksheet, title=tab_name, rows=1000, cols=30)
    return ws


@st.cache_data(ttl=60, show_spinner=False)
def _cached_read_sheet(sheet_key: str) -> pd.DataFrame:
    """Cached read -- avoids repeated API calls within 60 seconds."""
    ws = get_worksheet(sheet_key)
    try:
        all_values = _api_retry(ws.get_all_values)
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


def read_sheet(sheet_key: str) -> pd.DataFrame:
    """Read all data from a sheet tab and return as DataFrame (cached 60s)."""
    return _cached_read_sheet(sheet_key)


def _invalidate_read_cache():
    """Clear the read cache after a write operation."""
    _cached_read_sheet.clear()


def append_row(sheet_key: str, row_data: dict):
    """Append a single row. Writes headers to row 1 if sheet is empty."""
    ws = get_worksheet(sheet_key)
    headers = list(row_data.keys())
    existing = _api_retry(ws.get_all_values)
    if not existing or all(cell == "" for cell in existing[0]):
        # Sheet is empty -- write headers in row 1 then data in row 2
        _api_retry(ws.update, "A1", [headers])
        row_values = [str(v) for v in row_data.values()]
        _api_retry(ws.update, "A2", [row_values])
    else:
        # Sheet has data -- match columns to existing headers
        existing_headers = existing[0]
        # Trim to non-empty headers only
        trimmed = [h for h in existing_headers if h.strip()]
        row_values = [str(row_data.get(h, "")) for h in trimmed]
        _api_retry(ws.append_row, row_values, value_input_option="USER_ENTERED")
    _invalidate_read_cache()


def update_row(sheet_key: str, row_index: int, row_data: dict):
    """Update a row at the given 1-based sheet row index."""
    ws = get_worksheet(sheet_key)
    headers = _api_retry(ws.row_values, 1)
    # Trim to non-empty headers
    trimmed = [h for h in headers if h.strip()]
    row_values = [str(row_data.get(h, "")) for h in trimmed]
    cell_range = f"A{row_index}:{_col_letter(len(trimmed))}{row_index}"
    _api_retry(ws.update, cell_range, [row_values])
    _invalidate_read_cache()


def delete_row(sheet_key: str, row_index: int):
    """Delete a row at the given 1-based sheet row index."""
    ws = get_worksheet(sheet_key)
    _api_retry(ws.delete_rows, int(row_index))
    _invalidate_read_cache()


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


def _col_letter(n):
    """Convert 1-based column number to letter(s): 1->A, 27->AA, etc."""
    result = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        result = chr(65 + r) + result
    return result


def update_row_partial(sheet_key: str, row_index: int, row_data: dict):
    """Update only the specified columns in a row (partial update).
    Supports more than 26 columns."""
    ws = get_worksheet(sheet_key)
    headers = _api_retry(ws.row_values, 1)
    trimmed = [h for h in headers if h.strip()]
    for key, value in row_data.items():
        if key in trimmed:
            col_idx = trimmed.index(key) + 1
            _api_retry(ws.update_cell, row_index, col_idx, str(value))
    _invalidate_read_cache()


def find_race_day(date_str: str, track: str):
    """Find a race day row by date and track.
    Returns (row_index, row_dict) or (None, None) if not found.
    row_index is 1-based sheet row number."""
    ws = get_worksheet("race_day")
    all_values = _api_retry(ws.get_all_values)
    if not all_values or len(all_values) < 2:
        return None, None
    headers = all_values[0]
    date_col = None
    track_col = None
    for i, h in enumerate(headers):
        if h.strip().lower() == "date":
            date_col = i
        if h.strip().lower() == "track":
            track_col = i
    if date_col is None or track_col is None:
        return None, None
    for row_num, row in enumerate(all_values[1:], start=2):
        if len(row) > max(date_col, track_col):
            if row[date_col].strip() == date_str and row[track_col].strip() == track:
                row_dict = {}
                for i, h in enumerate(headers):
                    if h.strip() and i < len(row):
                        row_dict[h.strip()] = row[i]
                return row_num, row_dict
    return None, None


def upsert_race_day(date_str: str, track: str, data: dict):
    """Create or update a race day row identified by date+track.
    Returns the 1-based row index."""
    row_index, existing = find_race_day(date_str, track)
    if row_index is not None:
        # Update existing row
        merged = {}
        if existing:
            merged.update(existing)
        merged.update(data)
        merged["date"] = date_str
        merged["track"] = track
        update_row("race_day", row_index, merged)
        return row_index
    else:
        # Create new row
        data["date"] = date_str
        data["track"] = track
        append_row("race_day", data)
        # Find the row we just created
        new_idx, _ = find_race_day(date_str, track)
        return new_idx


def ensure_race_day_headers(all_headers: list):
    """Make sure the race_day sheet has all required column headers."""
    ws = get_worksheet("race_day")
    existing = _api_retry(ws.row_values, 1)
    trimmed = [h for h in existing if h.strip()]
    missing = [h for h in all_headers if h not in trimmed]
    if missing:
        new_headers = trimmed + missing
        end_col = _col_letter(len(new_headers))
        _api_retry(ws.update, f"A1:{end_col}1", [new_headers])
