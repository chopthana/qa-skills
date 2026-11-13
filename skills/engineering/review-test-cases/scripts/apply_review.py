#!/usr/bin/env python3
"""Write reviewed changes back into the workbook, in place.

A reviewer's note is prose ("ข้อ 3 ของ expected ให้เปลี่ยนเป็น …"), so this
script never interprets it — Claude reads the notes and hands over an explicit
edit list of whole cell values. The script's job is the part that must not go
wrong: back up first, edit only named cells of named cases, keep the workbook's
own formatting, and never remove a row.

Edits file (JSON list). Two operations, and no third:

  {"tc_id": "…-004", "field": "expected", "value": "1. …\n2. …"}

rewrites one cell of an existing case (`op: "edit"` is the default), and

  {"op": "add", "tc_id": "…-064", "topic": "…", "steps": "…",
   "expected": "…", "note": "…", "priority": "High"}

appends a new case after the last one, carrying the previous row's formatting
and the `ลำดับ` formula. `add` is what makes a split possible — one case
becomes three, and the two new ones say in their note which case they came
from.

`field` is one of topic, steps, expected, note, priority, status. There is
deliberately no delete operation: an existing case is rewritten, never removed,
and a new case only ever lands at the end.

Usage:
  python3 apply_review.py --input "<workbook>" --edits edits.json \
      --backup-dir <dir> [--applied-out applied.json] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from copy import copy

try:
    from openpyxl import load_workbook
except ImportError:  # pragma: no cover
    sys.exit("openpyxl is required: pip install openpyxl")

SHEET = "TestResult"
FIRST_DATA_ROW = 5
COL_TYPE = 2
COL_TC_ID = 3
FIELDS = {
    "topic": 4,
    "steps": 5,
    "expected": 6,
    "status": 7,
    "note": 10,
    "priority": 11,
}
LAST_COL = 12
ADD_DEFAULTS = {"priority": "Medium", "status": "Waiting to test", "type": "System Test"}


def append_case(ws, row: int, entry: dict) -> None:
    """Write a new case at `row`, wearing the previous row's clothes."""
    src = row - 1
    for col in range(1, LAST_COL + 1):
        cell = ws.cell(row, col)
        if src >= FIRST_DATA_ROW:
            cell._style = copy(ws.cell(src, col)._style)
        cell.value = None
    ws.row_dimensions[row].height = None
    ws.cell(row, 1).value = f'=IF(B{row}="","",ROW()-{FIRST_DATA_ROW - 1})'
    ws.cell(row, COL_TYPE).value = entry.get("type", ADD_DEFAULTS["type"])
    ws.cell(row, COL_TC_ID).value = entry["tc_id"]
    for field, col in FIELDS.items():
        if field in entry:
            ws.cell(row, col).value = entry[field]
        elif field in ADD_DEFAULTS:
            ws.cell(row, col).value = ADD_DEFAULTS[field]


def resolve_input(path: str) -> str:
    if os.path.isfile(path):
        return path
    if not path.lower().endswith(".xlsx") and os.path.isfile(path + ".xlsx"):
        return path + ".xlsx"
    sys.exit(f"not found: {path}")


def lock_file_for(path: str) -> str | None:
    folder, name = os.path.split(path)
    candidate = os.path.join(folder, "~$" + name)
    return candidate if os.path.exists(candidate) else None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", required=True, help="the workbook to edit in place")
    ap.add_argument("--edits", required=True, help="JSON list of {tc_id, field, value}")
    ap.add_argument("--backup-dir", required=True, help="where the pre-edit copy goes")
    ap.add_argument("--applied-out", help="write before/after per case here")
    ap.add_argument("--dry-run", action="store_true", help="report, change nothing")
    args = ap.parse_args()

    path = resolve_input(args.input)
    lock = lock_file_for(path)
    if lock:
        sys.exit(f"workbook is open in Excel ({os.path.basename(lock)} exists) — "
                 "close it, then run again")

    with open(args.edits, encoding="utf-8") as fh:
        edits = json.load(fh)
    if not isinstance(edits, list) or not edits:
        sys.exit("--edits must be a non-empty JSON list")

    wb = load_workbook(path)
    if SHEET not in wb.sheetnames:
        sys.exit(f"sheet {SHEET!r} not found; sheets are {wb.sheetnames}")
    ws = wb[SHEET]

    # TC ID -> row, from the live sheet
    rows: dict[str, int] = {}
    r = FIRST_DATA_ROW
    while ws.cell(r, COL_TC_ID).value:
        rows[str(ws.cell(r, COL_TC_ID).value)] = r
        r += 1
    total = len(rows)

    # --- validate the whole batch before touching anything ----------------
    problems = []
    adding = []
    for i, e in enumerate(edits):
        if not isinstance(e, dict):
            problems.append(f"[{i}] not an object")
            continue
        tc = e.get("tc_id")
        if e.get("op") == "add":
            if not tc:
                problems.append(f"[{i}] add needs a tc_id")
            elif tc in rows or tc in adding:
                problems.append(f"[{i}] TC ID already exists: {tc!r}")
            else:
                adding.append(tc)
            for k in e:
                if k not in ("op", "tc_id", "type") and k not in FIELDS:
                    problems.append(f"[{i}] add got an unknown field: {k!r}")
            continue
        fld = e.get("field")
        if tc not in rows:
            problems.append(f"[{i}] unknown TC ID: {tc!r}")
        if fld not in FIELDS:
            problems.append(f"[{i}] field must be one of {', '.join(FIELDS)}; got {fld!r}")
        if "value" not in e:
            problems.append(f"[{i}] no value")
    if problems:
        sys.exit("ไม่ได้แก้อะไรเลย — edits มีปัญหา:\n  " + "\n  ".join(problems))

    applied = []
    next_row = FIRST_DATA_ROW + total
    for e in edits:
        if e.get("op") == "add":
            applied.append({
                "tc_id": e["tc_id"], "row": next_row, "field": "เคสใหม่",
                "before": "", "after": e.get("topic", ""), "changed": True,
            })
            if not args.dry_run:
                append_case(ws, next_row, e)
            next_row += 1
            continue
        row = rows[e["tc_id"]]
        col = FIELDS[e["field"]]
        before = ws.cell(row, col).value
        before = "" if before is None else str(before)
        after = "" if e["value"] is None else str(e["value"])
        applied.append({
            "tc_id": e["tc_id"], "row": row, "field": e["field"],
            "before": before, "after": after, "changed": before != after,
        })
        if not args.dry_run and before != after:
            ws.cell(row, col).value = after

    changed = [a for a in applied if a["changed"]]

    if args.dry_run:
        print(f"dry run · {len(changed)} / {len(applied)} edits would change a cell")
    else:
        os.makedirs(args.backup_dir, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        backup = os.path.join(
            args.backup_dir,
            f"{os.path.splitext(os.path.basename(path))[0]}.before-{stamp}.xlsx")
        shutil.copy2(path, backup)
        wb.save(path)
        print(f"สำรองไว้ที่ {backup}")
        print(f"แก้ {len(changed)} เซลล์ · {len(applied) - len(changed)} เคสค่าเดิมอยู่แล้ว")

    # a case may be appended, never lost: the count moves by exactly the adds
    expect_total = total if args.dry_run else total + len(adding)
    wb2 = load_workbook(path)
    ws2 = wb2[SHEET]
    r = FIRST_DATA_ROW
    after_total = 0
    while ws2.cell(r, COL_TC_ID).value:
        after_total += 1
        r += 1
    if after_total != expect_total:
        sys.exit(f"จำนวนเคสควรเป็น {expect_total} แต่ได้ {after_total} — หยุดและตรวจไฟล์สำรอง")
    if adding and not args.dry_run:
        print(f"เคส {total} → {after_total} (เพิ่มใหม่ {len(adding)} ไม่มีเคสเดิมหาย)")
    else:
        print(f"เคสครบ {after_total} เคสเท่าเดิม")

    if args.applied_out:
        stamped = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        for a in applied:
            a["applied_at"] = stamped
        with open(args.applied_out, "w", encoding="utf-8") as fh:
            json.dump(applied, fh, ensure_ascii=False, indent=1)
        print(f"-> {args.applied_out}")

    for a in changed:
        print(f"  {a['tc_id']} · {a['field']} · แถว {a['row']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
