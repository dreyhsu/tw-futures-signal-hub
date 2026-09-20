# TW Futures Signal Hub

Standalone XQ-to-TAIFEX dashboard for Taiwan individual-stock futures candidates.

## Setup

Run from this repository on the Windows computer that has XQ installed:

```bat
conda run -n tss pip install -e .
copy .env.example .env
conda run -n tss twfsh serve
```

Add `FINMIND_TOKEN` to `.env` if available. Open `http://127.0.0.1:8081`.

## Daily workflow

`conda run -n tss twfsh run-daily` runs the active XQ screener, exports the result, retains 20 distinct screening dates, finds futures candidates, and refreshes their spot-price history.

Run `scripts\\install_tasks.bat` once to create the daily 18:10 task and weekday 08:45 TAIFEX quote task. Quote polling exits after 13:45 and stores stale last-known-good values if TAIFEX temporarily fails.

## Data ownership

Generated data is ignored by Git. `data/reference/tw_stock_futures_list.csv` is the version-controlled stock-to-futures mapping. Do not copy the old mixed-source history; this app starts its own XQ-only history.
