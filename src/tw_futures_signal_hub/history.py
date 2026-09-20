from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from .io import atomic_csv_write, read_csv
from .settings import CURRENT_XQ, HISTORY, KEEP_DATES


def normalize_symbol(value: object) -> str:
    value = str(value or "").strip().upper().replace(".TW", "")
    return value if value.isdigit() and len(value) == 4 else ""


def read_xq_export(path: Path = CURRENT_XQ) -> pd.DataFrame:
    raw = read_csv(path, dtype=str).fillna("")
    if raw.empty:
        raise ValueError(f"XQ export is empty or missing: {path}")
    first_column = str(raw.columns[0])
    raw = raw.loc[~raw[first_column].astype(str).str.startswith("執行時間")].copy()
    symbol_column = "代碼" if "代碼" in raw.columns else "代號" if "代號" in raw.columns else None
    if not symbol_column:
        raise ValueError("XQ export must include a '代碼' or '代號' column")
    raw["代號"] = raw[symbol_column].map(normalize_symbol)
    raw = raw[raw["代號"] != ""].drop_duplicates(subset=["代號"], keep="last").reset_index(drop=True)
    if raw.empty:
        raise ValueError("XQ export contains no valid four-digit Taiwan stock symbols")
    return raw


def append_history(current: pd.DataFrame, screened_date: str | None = None, path: Path = HISTORY, keep_dates: int = KEEP_DATES) -> pd.DataFrame:
    if current.empty:
        raise ValueError("Refusing to overwrite history with an empty XQ export")
    incoming = current.copy()
    incoming["screened_date"] = screened_date or date.today().isoformat()
    existing = read_csv(path, dtype={"代號": str})
    combined = pd.concat([existing, incoming], ignore_index=True, sort=False)
    combined["代號"] = combined["代號"].map(normalize_symbol)
    combined["screened_date"] = combined["screened_date"].astype(str)
    combined = combined[combined["代號"] != ""].drop_duplicates(subset=["代號", "screened_date"], keep="last")
    dates = sorted(combined["screened_date"].dropna().unique(), reverse=True)[:keep_dates]
    result = combined[combined["screened_date"].isin(dates)].sort_values(["screened_date", "代號"]).reset_index(drop=True)
    atomic_csv_write(result, path)
    return result


def update_history(export_path: Path = CURRENT_XQ, history_path: Path = HISTORY, screened_date: str | None = None) -> pd.DataFrame:
    return append_history(read_xq_export(export_path), screened_date, history_path)
