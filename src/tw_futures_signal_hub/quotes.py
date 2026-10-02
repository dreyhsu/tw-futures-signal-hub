from __future__ import annotations

import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from .candidates import build_candidates, number
from .io import atomic_csv_write, read_csv
from .settings import QUOTE_CACHE, QUOTE_LOG

URL = "https://mis.taifex.com.tw/futures/api/getQuoteList"
COLUMNS = ["stock_symbol", "product_code", "cid", "contract_code", "contract_name", "status", "quote_date", "quote_time", "last_price", "previous_close", "change", "change_pct", "price_source", "updated_at", "stale", "error"]


def announce(message: str, now: datetime | None = None, log_path: Path = QUOTE_LOG) -> None:
    line = f"[{(now or datetime.now()).strftime('%Y-%m-%d %H:%M:%S')}] {message}"
    print(line, flush=True)
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except OSError as error:
        print(f"[WARN] Could not write quote log: {error}", flush=True)


def cid(product_code: str) -> str:
    code = product_code.split(",", 1)[0].strip().upper()
    if not code: raise ValueError("missing futures product code")
    return code if code.endswith("F") else f"{code}F"


def fetch(product_code: str) -> list[dict[str, Any]]:
    response = requests.post(URL, json={"MarketType": "0", "SymbolType": "F", "KindID": "4", "CID": cid(product_code), "ExpireMonth": ""}, timeout=10)
    response.raise_for_status()
    payload = response.json()
    if payload.get("RtCode") != "0": raise RuntimeError(payload.get("RtMsg") or "TAIFEX API error")
    return payload["RtData"]["QuoteList"]


def near_month(rows: list[dict]) -> dict | None:
    return next((row for row in rows if str(row.get("SymbolID", "")).endswith("-F") and str(row.get("DispEName", "")) != str(row.get("SpotID", ""))), None)


def quote_price(row: dict) -> tuple[float | None, str]:
    last, test = number(row.get("CLastPrice")), number(row.get("CTestPrice"))
    if last and last > 0: return last, "last"
    if test and test > 0: return test, "test"
    bid, ask = number(row.get("CBestBidPrice") or row.get("CBidPrice1")), number(row.get("CBestAskPrice") or row.get("CAskPrice1"))
    if bid and ask: return round((bid + ask) / 2, 4), "mid"
    return (bid, "bid") if bid else (ask, "ask") if ask else (None, "")


def price_change(price: float | None, previous_close: float | None) -> tuple[float | None, float | None]:
    if price is None or previous_close is None or previous_close <= 0:
        return None, None
    change = round(price - previous_close, 4)
    return change, round(change / previous_close * 100, 4)


def load_cache(path: Path = QUOTE_CACHE) -> dict[str, dict]:
    frame = read_csv(path, dtype=str).fillna("")
    return {str(row.get("stock_symbol")): row.to_dict() for _, row in frame.iterrows() if row.get("stock_symbol")}


def refresh_quotes(candidates: list[dict] | None = None, now: datetime | None = None, cache_path: Path = QUOTE_CACHE) -> pd.DataFrame:
    candidates, now = candidates if candidates is not None else build_candidates(), now or datetime.now()
    previous, records, timestamp = load_cache(cache_path), [], now.strftime("%Y-%m-%d %H:%M:%S")
    for candidate in candidates:
        symbol, product_code = candidate["symbol"], candidate["product_code"]
        try:
            row = near_month(fetch(product_code))
            if row is None: raise ValueError("no near-month contract returned")
            price, source = quote_price(row)
            previous_close = number(row.get("CRefPrice"))
            change, change_pct = price_change(price, previous_close)
            records.append({"stock_symbol": symbol, "product_code": product_code, "cid": cid(product_code), "contract_code": row.get("DispEName", ""), "contract_name": row.get("DispCName", ""), "status": row.get("Status", ""), "quote_date": row.get("CDate", ""), "quote_time": row.get("CTime") or row.get("CTestTime", ""), "last_price": price, "previous_close": previous_close, "change": change, "change_pct": change_pct, "price_source": source, "updated_at": timestamp, "stale": False, "error": "" if price is not None else "No valid price in TAIFEX response"})
        except Exception as error:
            stale = previous.get(symbol, {"stock_symbol": symbol, "product_code": product_code, "cid": cid(product_code)})
            stale.update({"updated_at": timestamp, "stale": True, "error": str(error)})
            records.append(stale)
        time.sleep(0.1)
    frame = pd.DataFrame(records).reindex(columns=COLUMNS)
    atomic_csv_write(frame, cache_path)
    return frame


def cache_status(cache: dict[str, dict]) -> dict:
    if not cache: return {"state": "missing", "label": "Futures cache missing", "updated_at": "", "error_sample": ""}
    stale = [row for row in cache.values() if str(row.get("stale", "")).lower() in {"true", "1"}]
    errors = [row.get("error", "") for row in cache.values() if row.get("error")]
    updated = max((row.get("updated_at", "") for row in cache.values()), default="")
    state = "error" if len(stale) == len(cache) and errors else "stale" if stale else "error" if errors else "ok"
    return {"state": state, "label": f"{len(stale)}/{len(cache)} stale", "updated_at": updated, "error_sample": errors[0] if errors else ""}


def run_loop(start: str = "08:45", end: str = "13:45", interval: int = 5) -> None:
    start_time, end_time = (datetime.strptime(value, "%H:%M").time() for value in (start, end))
    announce(f"Quote scheduler started: weekdays {start}-{end}, every {interval} minutes.")
    first_refresh = True
    while True:
        now = datetime.now()
        if now.weekday() >= 5:
            announce("Weekend detected; no quote updates are scheduled. Exiting.", now)
            return
        if now.time() > end_time:
            announce(f"Market update window ended at {end}. Exiting.", now)
            return
        target = datetime.combine(now.date(), start_time)
        if now.time() >= start_time and first_refresh:
            target = now
        elif now > target:
            target += timedelta(minutes=((int((now - target).total_seconds() // 60) // interval) + 1) * interval)
        if target.time() > end_time:
            announce(f"No refresh remains before {end}. Exiting.", now)
            return
        announce(f"Next quote refresh: {target.strftime('%Y-%m-%d %H:%M:%S')}", now)
        time.sleep(max(0, (target - now).total_seconds()))
        frame = refresh_quotes()
        first_refresh = False
        stale_count = int(frame["stale"].astype(str).str.lower().isin({"true", "1"}).sum()) if not frame.empty else 0
        announce(f"Quote refresh complete: {len(frame)} records, {stale_count} stale.")
