from __future__ import annotations

from flask import Flask, abort, jsonify, render_template, send_from_directory, url_for

from .candidates import build_candidates, grouped_candidates
from .charts import TIMEFRAME_URLS, chart_filename, chart_manifest
from .history import normalize_symbol
from .quotes import cache_status, load_cache
from .settings import CHART_DIR


def create_app() -> Flask:
    app = Flask(__name__)

    def direction(value) -> str:
        try:
            change = float(value)
        except (TypeError, ValueError):
            return "quote-flat"
        return "quote-up" if change > 0 else "quote-down" if change < 0 else "quote-flat"

    @app.template_filter("num")
    def num(value): return "--" if value is None else f"{float(value):,.2f}"

    @app.template_filter("pct")
    def pct(value): return "--" if value is None else f"{float(value):+.2f}%"

    @app.get("/")
    def dashboard():
        candidates = build_candidates()
        quotes = load_cache()
        for item in candidates:
            quote = quotes.get(item["symbol"], {})
            item.update({"futures_last": item.get("futures_last", quote.get("last_price")), "futures_previous_close": quote.get("previous_close"), "futures_change_pct": quote.get("change_pct"), "futures_direction": direction(quote.get("change_pct")), "futures_contract": quote.get("contract_code", ""), "futures_stale": str(quote.get("stale", "")).lower() in {"true", "1"}, "futures_updated_at": quote.get("updated_at", "")})
        available = chart_manifest([item["symbol"] for item in candidates], CHART_DIR)
        chart_map = {
            symbol: {
                timeframe: url_for(
                    "chart_image",
                    symbol=symbol,
                    timeframe=timeframe,
                    v=version,
                )
                for timeframe, version in timeframes.items()
            }
            for symbol, timeframes in available.items()
        }
        return render_template(
            "dashboard.html",
            groups=grouped_candidates(candidates),
            count=len(candidates),
            quote_status=cache_status(quotes),
            chart_map=chart_map,
        )

    @app.get("/charts/<symbol>/<timeframe>")
    def chart_image(symbol: str, timeframe: str):
        symbol = normalize_symbol(symbol)
        if not symbol or timeframe not in TIMEFRAME_URLS:
            abort(404)
        filename = chart_filename(symbol, timeframe)
        if not (CHART_DIR / filename).is_file():
            abort(404)
        return send_from_directory(CHART_DIR, filename, max_age=31536000, conditional=True)

    @app.get("/api/futures-quotes")
    def futures_quotes():
        quotes = load_cache()
        return jsonify({"records": list(quotes.values()), "status": cache_status(quotes)})
    return app
