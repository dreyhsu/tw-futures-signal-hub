from datetime import datetime
from pathlib import Path

import pandas as pd

from tw_futures_signal_hub.quotes import announce, cache_status, near_month, price_change, quote_price, refresh_quotes
from tw_futures_signal_hub.web import create_app


def test_quote_selection_and_fallback_price():
    rows = [{"SymbolID": "CDF-S", "DispEName": "CDFSP", "SpotID": "2330"}, {"SymbolID": "CDF-F", "DispEName": "CDF076", "SpotID": "2330"}]
    assert near_month(rows)["DispEName"] == "CDF076"
    assert quote_price({"CBestBidPrice": "10", "CBestAskPrice": "12"}) == (11.0, "mid")
    assert price_change(37.8, 38.35) == (-0.55, -1.4342)


def test_quote_refresh_preserves_stale_cache(monkeypatch, tmp_path: Path):
    cache = tmp_path / "quotes.csv"
    pd.DataFrame([{ "stock_symbol": "2330", "product_code": "CDF", "last_price": "999", "updated_at": "old", "stale": "False", "error": "" }]).to_csv(cache, index=False, encoding="utf-8-sig")
    monkeypatch.setattr("tw_futures_signal_hub.quotes.fetch", lambda _: (_ for _ in ()).throw(RuntimeError("offline")))
    frame = refresh_quotes([{ "symbol": "2330", "product_code": "CDF" }], datetime(2026, 1, 1, 9), cache)
    assert str(frame.iloc[0]["stale"]).lower() == "true"
    assert str(frame.iloc[0]["last_price"]) == "999"


def test_quote_status_exposes_latest_update():
    status = cache_status({
        "2330": {"updated_at": "2026-09-22 09:10:00", "stale": "False", "error": ""},
        "2317": {"updated_at": "2026-09-22 09:15:00", "stale": "True", "error": "offline"},
    })
    assert status == {
        "state": "stale", "label": "1/2 stale", "updated_at": "2026-09-22 09:15:00", "error_sample": "offline"
    }


def test_quote_announcement_is_visible_and_logged(capsys, tmp_path: Path):
    log = tmp_path / "quotes.log"
    announce("Next quote refresh: 2026-09-22 09:20:00", datetime(2026, 9, 22, 9, 15), log)
    expected = "[2026-09-22 09:15:00] Next quote refresh: 2026-09-22 09:20:00"
    assert expected in capsys.readouterr().out
    assert log.read_text(encoding="utf-8").strip() == expected


def test_dashboard_and_quote_api_empty_state(monkeypatch):
    monkeypatch.setattr("tw_futures_signal_hub.web.build_candidates", lambda: [])
    monkeypatch.setattr("tw_futures_signal_hub.web.load_cache", lambda: {})
    client = create_app().test_client()
    assert client.get("/").status_code == 200
    payload = client.get("/api/futures-quotes").get_json()
    assert payload["records"] == [] and payload["status"]["state"] == "missing"
    assert payload["status"]["updated_at"] == ""


def test_dashboard_name_has_hover_chart_urls(monkeypatch):
    candidate = {
        "symbol": "2330", "name": "台積電", "industry": "半導體", "sub_industry": "晶圓代工",
        "screened_date": "2026-09-20", "hit_count": 2, "product_code": "CDF",
        "screen_price": 1000, "latest_close": 1000, "ma5": 990, "close_vs_ma5_pct": 1,
        "return_1m": 3, "return_1w": 2, "return_1d": 1,
    }
    monkeypatch.setattr("tw_futures_signal_hub.web.build_candidates", lambda: [candidate])
    monkeypatch.setattr("tw_futures_signal_hub.web.load_cache", lambda: {
        "2330": {"last_price": "101", "previous_close": "100", "change_pct": "1", "contract_code": "CDF106", "stale": "False", "updated_at": "2026-09-22 09:50:00", "error": ""}
    })
    monkeypatch.setattr(
        "tw_futures_signal_hub.web.chart_manifest",
        lambda symbols, chart_dir: {"2330": {"monthly": 1, "weekly": 2, "daily": 3}},
    )
    response = create_app().test_client().get("/")
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert 'class="chart-trigger" tabindex="0" data-symbol="2330"' in body
    assert "/charts/2330/monthly?v=1" in body
    assert "/charts/2330/weekly?v=2" in body
    assert "/charts/2330/daily?v=3" in body
    assert 'id="quote-updated-at"' in body
    assert "setInterval(refresh, 10000)" in body
    assert 'data-change class="quote-up">+1.00%</strong>' in body
    assert 'data-previous-close>Prev: 100.00</small>' in body


def test_chart_route_serves_only_valid_chart_paths(monkeypatch, tmp_path: Path):
    chart = tmp_path / "TW_2330_daily.png"
    chart.write_bytes(b"\x89PNG\r\n\x1a\nchart")
    monkeypatch.setattr("tw_futures_signal_hub.web.CHART_DIR", tmp_path)
    client = create_app().test_client()
    response = client.get("/charts/2330/daily?v=1")
    assert response.status_code == 200
    assert response.data.startswith(b"\x89PNG")
    assert client.get("/charts/not-a-symbol/daily").status_code == 404
    assert client.get("/charts/2330/unknown").status_code == 404
