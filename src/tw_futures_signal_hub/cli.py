from __future__ import annotations

import argparse
import os

from dotenv import load_dotenv

from .history import update_history
from .prices import refresh_prices
from .quotes import refresh_quotes, run_loop
from .web import create_app
from .xq_export import export_active_xq


def main() -> int:
    parser = argparse.ArgumentParser(prog="twfsh")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("export-xq")
    history = sub.add_parser("update-history"); history.add_argument("--date")
    sub.add_parser("refresh-prices")
    quotes = sub.add_parser("refresh-quotes"); quotes.add_argument("--loop", action="store_true"); quotes.add_argument("--start", default="08:45"); quotes.add_argument("--end", default="13:45"); quotes.add_argument("--interval", type=int, default=5)
    sub.add_parser("run-daily")
    serve = sub.add_parser("serve"); serve.add_argument("--host", default="127.0.0.1"); serve.add_argument("--port", type=int, default=8081)
    args = parser.parse_args(); load_dotenv()
    if args.command == "export-xq": return 0 if export_active_xq() else 1
    if args.command == "update-history": update_history(screened_date=args.date); return 0
    if args.command == "refresh-prices": return 0 if refresh_prices(token=os.getenv("FINMIND_TOKEN", ""))[1] == 0 else 1
    if args.command == "refresh-quotes":
        if args.loop: run_loop(args.start, args.end, args.interval)
        else: refresh_quotes()
        return 0
    if args.command == "run-daily":
        if not export_active_xq(): return 1
        update_history(); return 0 if refresh_prices(token=os.getenv("FINMIND_TOKEN", ""))[1] == 0 else 1
    create_app().run(host=args.host, port=args.port); return 0
