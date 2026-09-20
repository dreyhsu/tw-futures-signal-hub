from datetime import datetime
from pathlib import Path

import pandas as pd

from tw_futures_signal_hub.quotes import near_month, quote_price, refresh_quotes
from tw_futures_signal_hub.web import create_app


def test_quote_selection_and_fallback_price():
    rows = [{"SymbolID": "CDF-S", "DispEName": "CDFSP", "SpotID": "2330"}, {"SymbolID": "CDF-F", "DispEName": "CDF076", "SpotID": "2330"}]
    assert near_month(rows)["DispEName"] == "CDF076"
    assert quote_price({"CBestBidPrice": "10", "CBestAskPrice": "12"}) == (11.0, "mid")


def test_quote_refresh_preserves_stale_cache(monkeypatch, tmp_path: Path):
    cache = tmp_path / "quotes.csv"
    pd.DataFrame([{ "stock_symbol": "2330", "product_code": "CDF", "last_price": "999", "updated_at": "old", "stale": "False", "error": "" }]).to_csv(cache, index=False, encoding="utf-8-sig")
    monkeypatch.setattr("tw_futures_signal_hub.quotes.fetch", lambda _: (_ for _ in ()).throw(RuntimeError("offline")))
    frame = refresh_quotes([{ "symbol": "2330", "product_code": "CDF" }], datetime(2026, 1, 1, 9), cache)
    assert str(frame.iloc[0]["stale"]).lower() == "true"
    assert str(frame.iloc[0]["last_price"]) == "999"


def test_dashboard_and_quote_api_empty_state(monkeypatch):
    monkeypatch.setattr("tw_futures_signal_hub.web.build_candidates", lambda: [])
    monkeypatch.setattr("tw_futures_signal_hub.web.load_cache", lambda: {})
    client = create_app().test_client()
    assert client.get("/").status_code == 200
    payload = client.get("/api/futures-quotes").get_json()
    assert payload["records"] == [] and payload["status"]["state"] == "missing"
