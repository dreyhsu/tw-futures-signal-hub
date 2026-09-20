import os
from pathlib import Path

from tw_futures_signal_hub.charts import (
    chart_manifest,
    download_chart,
    refresh_charts,
)


PNG = b"\x89PNG\r\n\x1a\n" + b"chart"


class FakeResponse:
    def __init__(self, content=PNG, content_type="image/png", status_code=200):
        self.content = content
        self.headers = {"Content-Type": content_type}
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeSession:
    def __init__(self, response):
        self.response = response

    def get(self, *args, **kwargs):
        return self.response


def test_manifest_maps_three_timeframes_and_changes_version(tmp_path: Path):
    for timeframe in ("monthly", "weekly", "daily"):
        (tmp_path / f"TW_2330_{timeframe}.png").write_bytes(PNG)
    first = chart_manifest(["2330"], tmp_path)
    daily = tmp_path / "TW_2330_daily.png"
    newer = daily.stat().st_mtime_ns + 1_000_000_000
    os.utime(daily, ns=(newer, newer))
    second = chart_manifest(["2330"], tmp_path)
    assert set(first["2330"]) == {"monthly", "weekly", "daily"}
    assert first["2330"]["daily"] != second["2330"]["daily"]


def test_invalid_download_preserves_existing_chart(tmp_path: Path):
    path = tmp_path / "TW_2330_daily.png"
    path.write_bytes(PNG)
    session = FakeSession(FakeResponse(b"<html>blocked</html>", "text/html"))
    assert download_chart("2330", "daily", session, tmp_path) is False
    assert path.read_bytes() == PNG


def test_refresh_replaces_valid_charts_and_removes_obsolete_symbols(tmp_path: Path):
    obsolete = tmp_path / "TW_2317_daily.png"
    obsolete.write_bytes(PNG)
    replacement = b"\x89PNG\r\n\x1a\n" + b"new"
    result = refresh_charts(
        [{"symbol": "2330"}],
        tmp_path,
        FakeSession(FakeResponse(replacement)),
        pause=False,
    )
    assert result == (3, 0)
    assert not obsolete.exists()
    assert (tmp_path / "TW_2330_daily.png").read_bytes() == replacement
