from __future__ import annotations

from flask import Flask, jsonify, render_template

from .candidates import build_candidates, grouped_candidates
from .quotes import cache_status, load_cache


def create_app() -> Flask:
    app = Flask(__name__)

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
            item.update({"futures_last": item.get("futures_last", quote.get("last_price")), "futures_contract": quote.get("contract_code", ""), "futures_stale": str(quote.get("stale", "")).lower() in {"true", "1"}, "futures_updated_at": quote.get("updated_at", "")})
        return render_template("dashboard.html", groups=grouped_candidates(candidates), count=len(candidates), quote_status=cache_status(quotes))

    @app.get("/api/futures-quotes")
    def futures_quotes():
        quotes = load_cache()
        return jsonify({"records": list(quotes.values()), "status": cache_status(quotes)})
    return app
