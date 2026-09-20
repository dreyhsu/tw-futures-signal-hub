from __future__ import annotations

import csv
import sys
import time
from pathlib import Path

import pandas as pd
from pywinauto import Desktop

from .settings import CURRENT_XQ


def _button_near(window, x: int, y: int, tolerance: int = 18):
    rect = window.rectangle()
    for button in window.descendants(control_type="Button"):
        point = button.rectangle()
        if abs((point.left - rect.left) - x) <= tolerance and abs((point.top - rect.top) - y) <= tolerance:
            return button
    return None


def export_active_xq(output: Path = CURRENT_XQ) -> bool:
    """Run the open XQ screener and save its CSV as a UTF-8-SIG file."""
    desktop = Desktop(backend="uia")
    window = desktop.window(title_re="^選股中心.*")
    if not window.exists(timeout=10):
        print("XQ screener window was not found.")
        return False
    window.set_focus()
    execute = _button_near(window, 544, 50)
    if execute is None:
        print("XQ execute button was not found.")
        return False
    execute.click_input()
    deadline, export = time.time() + 120, None
    while time.time() < deadline:
        export = _button_near(window, 205, 448)
        if export is not None and export.is_enabled(): break
        time.sleep(1)
    if export is None or not export.is_enabled():
        print("XQ export button did not become available.")
        return False
    export.click_input()
    dialog, deadline = None, time.time() + 30
    while time.time() < deadline and dialog is None:
        dialog = next((candidate for candidate in desktop.windows() if any(label in candidate.window_text() for label in ("匯出選股結果", "另存新檔", "Save", "Export"))), None)
        if dialog is None:
            time.sleep(0.5)
    if dialog is None:
        print("XQ export dialog was not found.")
        return False
    raw = output.parent / ".xq_raw_export.csv"
    raw.unlink(missing_ok=True)
    edit = next(control for control in dialog.descendants(control_type="Edit") if control.window_text() == "檔案名稱:")
    edit.click_input(); edit.type_keys("^a"); edit.type_keys(str(raw), with_spaces=True)
    next(button for button in dialog.descendants(control_type="Button") if button.window_text().startswith(("存檔", "Save"))).click_input()
    deadline = time.time() + 20
    while time.time() < deadline and not raw.exists(): time.sleep(0.5)
    if not raw.exists():
        print("XQ did not create the export file.")
        return False
    lines = raw.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    headers, rows = next(csv.reader([lines[0]])), []
    for line in lines[1:]:
        fields = next(csv.reader([line.replace("\t", "")]))
        rows.append((fields + [""] * len(headers))[:len(headers)])
    output.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=[header.strip() for header in headers]).to_csv(output, index=False, encoding="utf-8-sig")
    raw.unlink(missing_ok=True)
    return True
