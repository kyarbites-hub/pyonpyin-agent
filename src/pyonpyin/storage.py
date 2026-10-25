"""Select the durable local MVP store or the existing Sheets integration."""

import os


def storage_backend():
    return os.environ.get("PYONPYIN_STORAGE", "sheets" if os.environ.get(
        "GOOGLE_SPREADSHEET_ID") else "sqlite").strip().lower()


def get_store():
    if storage_backend() == "sqlite":
        from pyonpyin.sqlite_store import SQLiteStore
        return SQLiteStore()
    if storage_backend() == "sheets":
        from pyonpyin.sheets import SheetsStore
        store = SheetsStore()
        store.ensure_schema()
        return store
    raise RuntimeError("PYONPYIN_STORAGE must be sqlite or sheets.")
