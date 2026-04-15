"""
Google Sheets integration for Employee Clearance System.
Uses Google Sheets as a database with service account authentication.
"""
import os
import json
import time
import socket
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from functools import wraps
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Google Sheets API configuration
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']


def retry_google_sheets_api(max_retries=3, delay=1):
    """Decorator to retry Google Sheets API calls on connection errors."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except (ConnectionResetError, socket.error, HttpError) as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        wait_time = delay * (2 ** attempt)
                        print(f"Google Sheets API error (attempt {attempt + 1}/{max_retries}): {e}. Retrying in {wait_time}s...")
                        time.sleep(wait_time)
                    else:
                        print(f"Google Sheets API failed after {max_retries} attempts: {e}")
            raise last_exception
        return wrapper
    return decorator


# Worksheet names for each table
WORKSHEETS = {
    "users": "Users",
    "clearance_files": "ClearanceFiles",
    "clearance_steps": "ClearanceSteps",
    "rejections": "Rejections"
}

# Column headers for each worksheet (used for range calculation and initialization)
WORKSHEET_HEADERS = {
    "Users": ["id", "email", "password_hash", "role", "department", "created_at"],
    "ClearanceFiles": ["id", "employee_id", "employee_name", "current_phase", "current_department",
                        "status", "it_required", "created_at", "total_cycle_time"],
    "ClearanceSteps": ["id", "file_id", "phase", "department", "acknowledged_at", "completed_at",
                       "sla_hours", "status", "sla_status", "notes", "rejection_count"],
    "Rejections": ["id", "step_id", "rejected_by", "rejected_to", "reason", "rejected_at"]
}


class _SheetCache:
    """Simple TTL cache for worksheet data."""
    def __init__(self, ttl_seconds: int = 30):
        self._cache: Dict[str, Tuple[Any, float]] = {}
        self._ttl = ttl_seconds

    def _key(self, worksheet_name: str, method: str) -> str:
        return f"{worksheet_name}:{method}"

    def get(self, worksheet_name: str, method: str):
        key = self._key(worksheet_name, method)
        entry = self._cache.get(key)
        if entry is None:
            return None
        value, timestamp = entry
        if time.time() - timestamp > self._ttl:
            del self._cache[key]
            return None
        return value

    def set(self, worksheet_name: str, method: str, value: Any):
        self._cache[self._key(worksheet_name, method)] = (value, time.time())

    def invalidate(self, worksheet_name: str):
        keys = [k for k in self._cache if k.startswith(f"{worksheet_name}:")]
        for k in keys:
            del self._cache[k]


class GoogleSheetsService:
    """Service for interacting with Google Sheets as a database."""

    def __init__(self, spreadsheet_id: str = None):
        self.spreadsheet_id = spreadsheet_id or os.getenv("GOOGLE_SHEETS_ID", "")
        if not self.spreadsheet_id:
            raise ValueError("Google Sheets ID not configured. Set GOOGLE_SHEETS_ID environment variable.")

        # Load service account credentials
        creds_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
        if creds_json:
            creds_info = json.loads(creds_json)
        else:
            creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "credentials.json")
            if os.path.exists(creds_path):
                with open(creds_path, 'r') as f:
                    creds_info = json.load(f)
            else:
                raise ValueError("Google service account credentials not found.")

        credentials = service_account.Credentials.from_service_account_info(
            creds_info, scopes=SCOPES
        )
        self.service = build('sheets', 'v4', credentials=credentials)
        self.sheets = self.service.spreadsheets()
        self._cache = _SheetCache(ttl_seconds=30)

    def _get_range(self, worksheet: str, range_start: str = "A1", range_end: str = None) -> str:
        """Construct a range string for the worksheet."""
        if range_end:
            return f"{worksheet}!{range_start}:{range_end}"
        return f"{worksheet}!{range_start}"

    def _get_full_data_range(self, worksheet_name: str) -> str:
        """Get a range that covers all possible data columns (A:ZZ covers 702 columns)."""
        return self._get_range(worksheet_name, "A1", "ZZ")

    @retry_google_sheets_api(max_retries=3, delay=1)
    def get_all_rows(self, worksheet_name: str) -> List[List[Any]]:
        """Get all rows from a worksheet."""
        cached = self._cache.get(worksheet_name, "all_rows")
        if cached is not None:
            return cached

        range_name = self._get_full_data_range(worksheet_name)
        result = self.sheets.values().get(
            spreadsheetId=self.spreadsheet_id,
            range=range_name
        ).execute()
        rows = result.get('values', [])
        self._cache.set(worksheet_name, "all_rows", rows)
        return rows

    def get_rows_with_headers(self, worksheet_name: str) -> List[Dict[str, Any]]:
        """Get rows as dictionaries with header mapping."""
        cached = self._cache.get(worksheet_name, "dict_rows")
        if cached is not None:
            return cached

        rows = self.get_all_rows(worksheet_name)
        if not rows:
            return []

        headers = rows[0]
        data_rows = rows[1:]

        result = []
        for row in data_rows:
            row_dict = {}
            for i, header in enumerate(headers):
                row_dict[header] = row[i] if i < len(row) else None
            result.append(row_dict)

        self._cache.set(worksheet_name, "dict_rows", result)
        return result

    @retry_google_sheets_api(max_retries=3, delay=1)
    def append_row(self, worksheet_name: str, row_data: List[Any]) -> bool:
        """Append a new row to the worksheet."""
        range_name = self._get_range(worksheet_name, "A1")
        body = {'values': [row_data]}
        self.sheets.values().append(
            spreadsheetId=self.spreadsheet_id,
            range=range_name,
            valueInputOption='USER_ENTERED',
            insertDataOption='INSERT_ROWS',
            body=body
        ).execute()
        self._cache.invalidate(worksheet_name)
        return True

    @retry_google_sheets_api(max_retries=3, delay=1)
    def update_row(self, worksheet_name: str, row_index: int, row_data: List[Any]) -> bool:
        """Update a specific row in the worksheet (1-indexed)."""
        range_name = self._get_range(worksheet_name, f"A{row_index}")
        body = {'values': [row_data]}
        self.sheets.values().update(
            spreadsheetId=self.spreadsheet_id,
            range=range_name,
            valueInputOption='USER_ENTERED',
            body=body
        ).execute()
        self._cache.invalidate(worksheet_name)
        return True

    @retry_google_sheets_api(max_retries=3, delay=1)
    def batch_update_rows(self, worksheet_name: str, updates: List[Tuple[int, List[Any]]]) -> bool:
        """Update multiple rows at once. updates is a list of (row_index, row_data) tuples."""
        if not updates:
            return True

        data = []
        for row_index, row_data in updates:
            range_name = self._get_range(worksheet_name, f"A{row_index}")
            data.append({
                'range': range_name,
                'values': [row_data]
            })

        body = {
            'valueInputOption': 'USER_ENTERED',
            'data': data
        }
        self.sheets.values().batchUpdate(
            spreadsheetId=self.spreadsheet_id,
            body=body
        ).execute()
        self._cache.invalidate(worksheet_name)
        return True

    @retry_google_sheets_api(max_retries=3, delay=1)
    def delete_row(self, worksheet_name: str, row_index: int) -> bool:
        """Delete a specific row from the worksheet (1-indexed)."""
        request = {
            "requests": [{
                "deleteDimension": {
                    "range": {
                        "sheetId": self._get_sheet_id(worksheet_name),
                        "dimension": "ROWS",
                        "startIndex": row_index - 1,
                        "endIndex": row_index
                    }
                }
            }]
        }
        self.sheets.batchUpdate(
            spreadsheetId=self.spreadsheet_id,
            body=request
        ).execute()
        self._cache.invalidate(worksheet_name)
        return True

    @retry_google_sheets_api(max_retries=3, delay=1)
    def _get_sheet_id(self, worksheet_name: str) -> int:
        """Get the sheet ID for a worksheet name."""
        spreadsheet = self.sheets.get(spreadsheetId=self.spreadsheet_id).execute()
        for sheet in spreadsheet['sheets']:
            if sheet['properties']['title'] == worksheet_name:
                return sheet['properties']['sheetId']
        raise ValueError(f"Worksheet '{worksheet_name}' not found")

    @retry_google_sheets_api(max_retries=3, delay=1)
    def clear_worksheet(self, worksheet_name: str) -> bool:
        """Clear all data from a worksheet (except headers)."""
        try:
            range_name = self._get_range(worksheet_name, "A2", "ZZ")
            self.sheets.values().clear(
                spreadsheetId=self.spreadsheet_id,
                range=range_name,
                body={}
            ).execute()
            self._cache.invalidate(worksheet_name)
            return True
        except HttpError as e:
            print(f"Error clearing worksheet: {e}")
            return False

    def initialize_spreadsheet(self):
        """Initialize the spreadsheet with headers if empty."""
        for key, worksheet_name in WORKSHEETS.items():
            rows = self.get_all_rows(worksheet_name)
            if not rows:
                headers = WORKSHEET_HEADERS.get(worksheet_name)
                if headers:
                    self.append_row(worksheet_name, headers)
                    print(f"Initialized {worksheet_name} with headers")


# Singleton instance
_sheets_service = None


def get_sheets_service() -> GoogleSheetsService:
    """Get or create the Google Sheets service instance."""
    global _sheets_service
    if _sheets_service is None:
        _sheets_service = GoogleSheetsService()
    return _sheets_service
