from pathlib import Path

import pandas as pd
import pytest

from tw_futures_signal_hub.candidates import build_candidates, price_metrics
from tw_futures_signal_hub.history import append_history, read_xq_export


def test_xq_export_removes_metadata_and_normalizes_symbols(tmp_path: Path):
    source = tmp_path / "xq.csv"
    pd.DataFrame([{ "序號": "執行時間：2026-09-20", "代碼": "", "商品": "" }, {"序號": "1", "代碼": "2330.TW", "商品": "台積電"}, {"序號": "2", "代碼": "bad", "商品": "bad"}]).to_csv(source, index=False, encoding="utf-8-sig")
    frame = read_xq_export(source)
    assert frame["代號"].tolist() == ["2330"]


def test_history_keeps_twenty_distinct_dates(tmp_path: Path):
    path = tmp_path / "history.csv"
    for day in range(25): append_history(pd.DataFrame({"代號": ["2330"], "商品": ["台積電"]}), f"2026-01-{day + 1:02}", path)
    assert pd.read_csv(path)["screened_date"].nunique() == 20


def test_candidates_intersect_and_count_hits(tmp_path: Path):
    history, futures, prices = tmp_path / "history.csv", tmp_path / "futures.csv", tmp_path / "prices"
    prices.mkdir()
    pd.DataFrame({"代號": ["2330", "2330", "9999"], "商品": ["台積電"] * 3, "產業": ["半導體"] * 3, "細產業": ["晶圓代工"] * 3, "screened_date": ["2026-01-01", "2026-01-02", "2026-01-02"]}).to_csv(history, index=False, encoding="utf-8-sig")
    pd.DataFrame({"stock_symbol": ["2330"], "product_code": ["CDF"]}).to_csv(futures, index=False, encoding="utf-8-sig")
    result = build_candidates(history, futures, prices)
    assert len(result) == 1 and result[0]["hit_count"] == 2 and result[0]["product_code"] == "CDF"


def test_price_metrics_for_short_series(tmp_path: Path):
    path = tmp_path / "price.csv"
    pd.DataFrame({"date": ["2026-01-01", "2026-01-02"], "close": [10, 11]}).to_csv(path, index=False)
    assert price_metrics(path)["return_1d"] == 10.0
    assert price_metrics(path)["return_1m"] is None
