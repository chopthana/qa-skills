#!/usr/bin/env python3
"""Read a QA test-case workbook into review.json, verbatim.

The review page shows every cell exactly as the workbook holds it — no
abbreviating, no truncating, no folding of repeated preconditions. This script
is the only place that reads the workbook, so the "verbatim" rule lives here:
nothing in it rewrites, strips or shortens a cell's text. Newlines are kept as
newlines so the page can render them with `white-space: pre-wrap`.

Usage:
  python3 extract_cases.py --input "<workbook>" --output review.json
  python3 extract_cases.py --input "<workbook>" --quiet      # counts only

`--input` may omit the .xlsx extension (a path pasted from a Jira title often
does). The script refuses to read a workbook Excel still holds open, because a
later --apply pass would be clobbered when Excel saves.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

try:
    from openpyxl import load_workbook
except ImportError:  # pragma: no cover
    sys.exit("openpyxl is required: pip install openpyxl")

# --- the team's workbook layout (same constants as testcase-coverage-audit) ---
SHEET = "TestResult"
HEADER_ROW = 4
FIRST_DATA_ROW = 5
COL_TYPE = 2
COL_TC_ID = 3
COL_TOPIC = 4
COL_STEPS = 5
COL_EXPECTED = 6
COL_STATUS = 7
COL_NOTE = 10
COL_PRIORITY = 11
PROGRAM_CELL = "G2"


def resolve_input(path: str) -> str:
    """Accept a path with or without the .xlsx extension."""
    if os.path.isfile(path):
        return path
    if not path.lower().endswith(".xlsx") and os.path.isfile(path + ".xlsx"):
        return path + ".xlsx"
    sys.exit(f"not found: {path}")


def lock_file_for(path: str) -> str | None:
    """Excel's own lock file sits beside the workbook as ~$<name>."""
    folder, name = os.path.split(path)
    candidate = os.path.join(folder, "~$" + name)
    return candidate if os.path.exists(candidate) else None


def card_id(name: str) -> str:
    """Pull 'ALC-2520' out of a workbook filename, else ''."""
    m = re.search(r"([A-Z]{2,5})\s*-\s*(\d{3,6})", name)
    return f"{m.group(1)}-{m.group(2)}" if m else ""


def text(cell) -> str:
    """A cell as the workbook holds it. Only None becomes ''."""
    v = cell.value
    if v is None:
        return ""
    if isinstance(v, str):
        return v
    return str(v)


def extract(path: str) -> dict:
    wb = load_workbook(path, data_only=True)
    if SHEET not in wb.sheetnames:
        sys.exit(f"sheet {SHEET!r} not found; sheets are {wb.sheetnames}")
    ws = wb[SHEET]

    headers = [text(ws.cell(HEADER_ROW, c)) for c in range(1, 13)]

    cases = []
    r = FIRST_DATA_ROW
    while text(ws.cell(r, COL_TC_ID)):
        cases.append({
            "row": r,
            "tc_id": text(ws.cell(r, COL_TC_ID)),
            "type": text(ws.cell(r, COL_TYPE)),
            "topic": text(ws.cell(r, COL_TOPIC)),
            "steps": text(ws.cell(r, COL_STEPS)),
            "expected": text(ws.cell(r, COL_EXPECTED)),
            "status": text(ws.cell(r, COL_STATUS)),
            "note": text(ws.cell(r, COL_NOTE)),
            "priority": text(ws.cell(r, COL_PRIORITY)),
        })
        r += 1

    if not cases:
        sys.exit(f"no cases found: {SHEET} row {FIRST_DATA_ROW} has no TC ID")

    name = os.path.basename(path)
    return {
        "source": os.path.abspath(path),
        "file_name": name,
        "card": card_id(name),
        "program": text(ws[PROGRAM_CELL]),
        "headers": headers,
        "count": len(cases),
        "cases": cases,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", required=True, help="the .xlsx (extension optional)")
    ap.add_argument("--output", help="where to write review.json")
    ap.add_argument("--quiet", action="store_true", help="print counts only")
    args = ap.parse_args()

    path = resolve_input(args.input)
    lock = lock_file_for(path)
    if lock:
        sys.exit(f"workbook is open in Excel ({os.path.basename(lock)} exists) — "
                 "close it first, or a later --apply will be overwritten on save")

    data = extract(path)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=1)

    print(f"card {data['card'] or '?'} · {data['count']} cases · {data['file_name']}")
    if not args.quiet:
        blank_steps = [c["tc_id"] for c in data["cases"] if not c["steps"].strip()]
        blank_exp = [c["tc_id"] for c in data["cases"] if not c["expected"].strip()]
        dupes = sorted({c["tc_id"] for c in data["cases"]
                        if [x["tc_id"] for x in data["cases"]].count(c["tc_id"]) > 1})
        if blank_steps:
            print(f"  ⚠️  steps ว่าง: {', '.join(blank_steps)}")
        if blank_exp:
            print(f"  ⚠️  expected ว่าง: {', '.join(blank_exp)}")
        if dupes:
            print(f"  ⚠️  TC ID ซ้ำ: {', '.join(dupes)}")
        if args.output:
            print(f"  -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
