from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
CURRENT_XQ = DATA / "current" / "xq_screener_results.csv"
HISTORY = DATA / "history" / "xq_screener_history.csv"
FUTURES_REFERENCE = DATA / "reference" / "tw_stock_futures_list.csv"
PRICE_DIR = DATA / "prices"
QUOTE_CACHE = DATA / "realtime" / "futures_quotes.csv"
KEEP_DATES = 20
