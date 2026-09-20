from __future__ import annotations

from pathlib import Path

import pandas as pd

from .history import normalize_symbol
from .io import read_csv
from .settings import FUTURES_REFERENCE, HISTORY, PRICE_DIR


def number(value: object) -> float | None:
    try:
        if pd.isna(value): return None
        return round(float(value), 2)
    except (TypeError, ValueError): return None


def text(value: object) -> str:
    return "" if value is None or pd.isna(value) else str(value).strip()


def price_metrics(path: Path) -> dict:
    frame = read_csv(path)
    blank = {"latest_close": None, "ma5": None, "close_vs_ma5_pct": None, "return_1d": None, "return_1w": None, "return_1m": None, "pullback_status": "missing"}
    if frame.empty or not {"date", "close"}.issubset(frame.columns): return blank
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
    frame = frame.dropna(subset=["date", "close"]).sort_values("date").tail(80).reset_index(drop=True)
    if frame.empty: return blank
    closes = frame["close"].astype(float)
    latest = float(closes.iloc[-1])
    ma5 = float(closes.tail(5).mean()) if len(closes) >= 5 else None
    pct = lambda prior: round((latest / prior - 1) * 100, 2) if prior not in (None, 0) else None
    vs_ma5 = pct(ma5)
    return {"latest_close": round(latest, 2), "ma5": round(ma5, 2) if ma5 else None, "close_vs_ma5_pct": vs_ma5, "return_1d": pct(float(closes.iloc[-2])) if len(closes) > 1 else None, "return_1w": pct(float(closes.iloc[-6])) if len(closes) > 5 else None, "return_1m": pct(float(closes.iloc[-22])) if len(closes) > 21 else None, "pullback_status": "below_ma5" if vs_ma5 is not None and vs_ma5 < 0 else "near_ma5" if vs_ma5 is not None and vs_ma5 <= 1 else "normal"}


def load_futures(path: Path = FUTURES_REFERENCE) -> dict[str, str]:
    frame = read_csv(path, dtype=str).fillna("")
    if not {"stock_symbol", "product_code"}.issubset(frame.columns): return {}
    return {normalize_symbol(row.stock_symbol): text(row.product_code) for row in frame.itertuples() if normalize_symbol(row.stock_symbol)}


def build_candidates(history_path: Path = HISTORY, futures_path: Path = FUTURES_REFERENCE, price_dir: Path = PRICE_DIR) -> list[dict]:
    history = read_csv(history_path, dtype={"代號": str}).fillna("")
    futures = load_futures(futures_path)
    if history.empty or not futures or "代號" not in history.columns: return []
    history["代號"] = history["代號"].map(normalize_symbol)
    matches = history[history["代號"].isin(futures)].copy()
    if matches.empty: return []
    if "screened_date" not in matches.columns:
        matches["screened_date"] = ""
    else:
        matches["screened_date"] = matches["screened_date"].astype(str)
    latest = matches.sort_values("screened_date").drop_duplicates("代號", keep="last")
    hits = matches.groupby("代號").size().to_dict()
    rows = []
    for row in latest.to_dict("records"):
        symbol = row["代號"]
        rows.append({"symbol": symbol, "name": text(row.get("商品")) or text(row.get("名稱")), "industry": text(row.get("產業")) or "未分類", "sub_industry": text(row.get("細產業")), "screened_date": text(row.get("screened_date")), "hit_count": int(hits[symbol]), "product_code": futures[symbol], "screen_price": number(row.get("成交")), **price_metrics(price_dir / f"{symbol}.csv")})
    rows = sorted(rows, key=lambda item: item["symbol"])
    rows = sorted(rows, key=lambda item: item["screened_date"], reverse=True)
    return sorted(rows, key=lambda item: item["hit_count"], reverse=True)


def grouped_candidates(candidates: list[dict]) -> list[dict]:
    groups: dict[str, list[dict]] = {}
    for candidate in candidates: groups.setdefault(candidate["industry"], []).append(candidate)
    return [{"group": group, "symbols": sorted(rows, key=lambda item: (-item["hit_count"], item["symbol"])), "symbol_count": len(rows)} for group, rows in sorted(groups.items())]
