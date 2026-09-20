from __future__ import annotations

import random
import time
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .candidates import build_candidates
from .history import normalize_symbol
from .io import atomic_bytes_write
from .settings import CHART_DIR


TIMEFRAME_URLS = {
    "monthly": "https://stock.wearn.com/finance_mchart.asp?stockid={symbol}&timekind=2&timeblock=2&sma1=&sma2=&sma3=&volume=0&indicator1=Vol&indicator2=MACD&indicator3=None",
    "weekly": "https://stock.wearn.com/finance_wchart.asp?stockid={symbol}&timekind=1&timeblock=3&sma1=&sma2=&sma3=&volume=0&indicator1=Vol&indicator2=MACD&indicator3=None",
    "daily": "https://stock.wearn.com/finance_chart.asp?stockid={symbol}&timekind=0&timeblock=270&sma1=&sma2=&sma3=&volume=0&indicator1=Vol&indicator2=MACD&indicator3=None",
}
IMAGE_SIGNATURES = (b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff", b"GIF87a", b"GIF89a")
USER_AGENTS = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/121 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/605.1.15",
)


def chart_filename(symbol: str, timeframe: str) -> str:
    normalized = normalize_symbol(symbol)
    if not normalized or timeframe not in TIMEFRAME_URLS:
        raise ValueError("invalid chart symbol or timeframe")
    return f"TW_{normalized}_{timeframe}.png"


def setup_session() -> requests.Session:
    session = requests.Session()
    retries = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    session.mount("https://", HTTPAdapter(max_retries=retries))
    return session


def is_image_response(response: requests.Response) -> bool:
    content_type = response.headers.get("Content-Type", "").lower()
    content = response.content
    signature_matches = content.startswith(IMAGE_SIGNATURES) or (
        content.startswith(b"RIFF") and content[8:12] == b"WEBP"
    )
    return content_type.startswith("image/") and signature_matches


def download_chart(
    symbol: str,
    timeframe: str,
    session: requests.Session,
    chart_dir: Path = CHART_DIR,
) -> bool:
    path = chart_dir / chart_filename(symbol, timeframe)
    try:
        response = session.get(
            TIMEFRAME_URLS[timeframe].format(symbol=symbol),
            headers={"User-Agent": random.choice(USER_AGENTS)},
            timeout=15,
        )
        response.raise_for_status()
        if not is_image_response(response):
            raise ValueError(
                f"invalid image response ({response.headers.get('Content-Type', 'unknown')})"
            )
        atomic_bytes_write(response.content, path)
        return True
    except Exception as error:
        print(f"[WARN] chart update failed for {symbol} {timeframe}: {error}")
        return False


def chart_manifest(symbols: list[str], chart_dir: Path = CHART_DIR) -> dict[str, dict[str, int]]:
    manifest: dict[str, dict[str, int]] = {}
    for raw_symbol in symbols:
        symbol = normalize_symbol(raw_symbol)
        if not symbol:
            continue
        for timeframe in TIMEFRAME_URLS:
            path = chart_dir / chart_filename(symbol, timeframe)
            try:
                version = path.stat().st_mtime_ns
            except FileNotFoundError:
                continue
            manifest.setdefault(symbol, {})[timeframe] = version
    return manifest


def refresh_charts(
    candidates: list[dict] | None = None,
    chart_dir: Path = CHART_DIR,
    session: requests.Session | None = None,
    pause: bool = True,
) -> tuple[int, int]:
    candidates = build_candidates() if candidates is None else candidates
    symbols = list(
        dict.fromkeys(
            symbol
            for candidate in candidates
            if (symbol := normalize_symbol(candidate.get("symbol")))
        )
    )
    if not symbols:
        print("[WARN] no candidates available for chart refresh")
        return 0, 0

    chart_dir.mkdir(parents=True, exist_ok=True)
    client = session or setup_session()
    successes = failures = 0
    for symbol in symbols:
        for timeframe in TIMEFRAME_URLS:
            if download_chart(symbol, timeframe, client, chart_dir):
                successes += 1
            else:
                failures += 1
            if pause:
                time.sleep(random.uniform(0.3, 0.7))

    expected = {
        chart_filename(symbol, timeframe)
        for symbol in symbols
        for timeframe in TIMEFRAME_URLS
    }
    for path in chart_dir.glob("TW_*_*.png"):
        if path.name not in expected:
            path.unlink()
    return successes, failures
