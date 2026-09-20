from __future__ import annotations

import csv
import io
import time
from pathlib import Path
from uuid import uuid4

import pandas as pd
from pywinauto import Desktop

from .io import atomic_csv_write
from .settings import CURRENT_XQ

XQ_COMMAND_IDS = {"執行選股": 17554, "匯出": 20616}


def _toolbar_button(window, label: str):
    """Find an XQ toolbar action by its native command ID."""
    command_id = XQ_COMMAND_IDS[label]
    matches, available = [], []
    for toolbar in window.descendants(class_name="ToolbarWindow32"):
        if not toolbar.is_visible():
            continue
        for index in range(toolbar.button_count()):
            info = toolbar.get_button_struct(index)
            if info.fsStyle & 1:  # TBSTYLE_SEP
                continue
            available.append(info.idCommand)
            if info.idCommand == command_id:
                button = toolbar.button(index)
                matches.append(button)
    if len(matches) != 1:
        raise RuntimeError(
            f"Expected one XQ '{label}' command ({command_id}), found {len(matches)}. "
            f"Available command IDs: {available}"
        )
    return matches[0]


def _read_export(raw: Path) -> pd.DataFrame:
    content = raw.read_bytes()
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("cp950")
    records = list(csv.reader(io.StringIO(text.replace("\t", ""))))
    if not records:
        raise ValueError("XQ exported an empty file")
    header_index = next(
        (index for index, row in enumerate(records) if {"代碼", "代號"}.intersection(field.strip() for field in row)),
        None,
    )
    if header_index is None:
        raise ValueError(f"XQ export has no stock-code header: {records[:5]}")
    headers = [header.strip() for header in records[header_index]]
    rows = [
        (row + [""] * len(headers))[:len(headers)]
        for row in records[header_index + 1 :]
        if row and any(field.strip() for field in row)
    ]
    return pd.DataFrame(rows, columns=headers)


def export_active_xq(output: Path = CURRENT_XQ) -> bool:
    """Execute the selected XQ screener and export its results."""
    output = Path(output).resolve()
    raw = output.parent / f".xq_export_{uuid4().hex}.csv"
    try:
        desktop = Desktop(backend="win32")
        spec = desktop.window(title_re="^選股中心.*")
        spec.wait("exists", timeout=10)
        window = spec.wrapper_object()
        if window.is_minimized():
            window.restore()
        execute = _toolbar_button(window, "執行選股")
        if not execute.is_enabled():
            raise RuntimeError("XQ execute button is disabled; select a screener first")
        print("XQ: clicking 執行選股", flush=True)
        execute.click()
        time.sleep(1)
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            export = _toolbar_button(window, "匯出")
            if _toolbar_button(window, "執行選股").is_enabled() and export.is_enabled():
                break
            time.sleep(1)
        else:
            raise RuntimeError("XQ screening did not finish within 120 seconds")
        output.parent.mkdir(parents=True, exist_ok=True)
        print("XQ: clicking 匯出", flush=True)
        export.click()
        dialog_spec = desktop.window(
            title_re="^(匯出選股結果|另存新檔|Save.*|Export.*)$",
            process=window.process_id(),
        )
        dialog_spec.wait("visible", timeout=30)
        # XQ opens the modern Windows Save dialog, whose filename edit is 1001.
        filename = dialog_spec.child_window(control_id=1001, class_name="Edit")
        filename.wait("visible", timeout=5)
        filename.set_edit_text(str(raw))
        print(f"XQ: saving {raw}", flush=True)
        save = dialog_spec.child_window(control_id=1, class_name="Button").wrapper_object()
        # Send IDOK directly; physical mouse input is unavailable to scheduled jobs.
        dialog_spec.wrapper_object().send_message(0x0111, 1, save.handle)  # WM_COMMAND
        deadline, last_size, stable = time.monotonic() + 20, -1, 0
        while time.monotonic() < deadline:
            size = raw.stat().st_size if raw.exists() else 0
            stable = stable + 1 if size > 0 and size == last_size else 0
            if stable >= 2:
                break
            last_size = size
            time.sleep(0.5)
        else:
            raise RuntimeError("XQ did not finish writing the export file")
        frame = _read_export(raw)
        atomic_csv_write(frame, output)
        raw.unlink()
        print(f"XQ: exported {len(frame)} rows to {output}", flush=True)
        return True
    except Exception as exc:
        print(f"XQ export failed: {type(exc).__name__}: {exc}", flush=True)
        if raw.exists():
            print(f"Raw export retained for diagnosis: {raw}", flush=True)
        return False
