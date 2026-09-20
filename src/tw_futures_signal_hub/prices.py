from __future__ import annotations

import os
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
from FinMind.data import DataLoader

from .candidates import build_candidates
from .io import atomic_csv_write
from .settings import PRICE_DIR


def refresh_prices(symbols: list[str] | None = None, token: str = "", price_dir: Path = PRICE_DIR) -> tuple[int, int]:
    symbols = symbols if symbols is not None else [row["symbol"] for row in build_candidates()]
    loader = DataLoader()
    if token: loader.login_by_token(token)
    today, successes = datetime.now(), 0
    for symbol in symbols:
        try:
            path = price_dir / f"{symbol}.csv"
            start = (today - timedelta(days=60)).strftime("%Y-%m-%d")
            if path.exists():
                previous = pd.read_csv(path)
                if not previous.empty and "date" in previous:
                    last = pd.to_datetime(previous["date"], errors="coerce").max()
                    if pd.notna(last) and last.date() >= today.date():
                        successes += 1
                        continue
                    if pd.notna(last): start = (last + timedelta(days=1)).strftime("%Y-%m-%d")
            frame = loader.taiwan_stock_daily(stock_id=symbol, start_date=start, end_date=today.strftime("%Y-%m-%d"))
            if frame.empty: raise ValueError("no FinMind data returned")
            if path.exists():
                frame = pd.concat([pd.read_csv(path), frame], ignore_index=True).drop_duplicates(subset=["date"], keep="last")
            atomic_csv_write(frame.sort_values("date"), path)
            successes += 1
        except Exception as error:
            print(f"[WARN] price update failed for {symbol}: {error}")
    return successes, len(symbols) - successes
