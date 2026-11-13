#!/usr/bin/env python3
"""Write reviewed changes back into the workbook, in place.

A reviewer's note is prose ("ข้อ 3 ของ expected ให้เปลี่ยนเป็น …"), so this
script never interprets it — Claude reads the notes and hands over an explicit
edit list of whole cell values. The script's job is the part that must not go
wrong: back up first, touch only named cells of named cases, keep the
workbook's own formatting, and account for every case afterwards.

Edits file (JSON list). Three operations, and no fourth:

  {"tc_id": "…-004", "field": "expected", "value": "1. …\n2. …"}

rewrites one cell of an existing case (`op: "edit"` is the default),

  {"op": "add", "tc_id": "…-064", "topic": "…", "steps": "…",
   "expected": "…", "note": "…", "priority": "High"}

appends a new case after the last one, carrying the previous row's formatting
and the `ลำดับ` formula — `add` is what makes a split possible, one case
becomes three and the two new ones say in their note where they came from —
and

  {"op": "remove", "tc_id": "…-032"}

deletes that case's row and closes the gap behind it. Removal is the one
operation the user has to ask for in words: a review note that says to drop a
case is reported to them, never acted on by itself.

Closing the gap is four things, not one, and all four happen here: the row
goes, every later TC ID moves down by one, column A's `ลำดับ` formula is
rewritten per row, and references to the moved cases inside other cells
(`เคส 041`, `เคส 045–047`, a full `PREFIX-041`) are shifted to match. Pass
`--keep-numbers` to delete the row and leave the numbering alone instead.
`--renumber-out` writes the old → new map, which is what a caller needs to
move review state that is keyed by TC ID.

`field` is one of topic, steps, expected, note, priority, status.

Usage:
  python3 apply_review.py --input "<workbook>" --edits edits.json \
      --backup-dir <dir> [--applied-out applied.json] \
      [--renumber-out renumber.json] [--keep-numbers] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import os
import re
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
TEXT_COLS = (FIELDS["topic"], FIELDS["steps"], FIELDS["expected"], FIELDS["note"])
LAST_COL = 12
ADD_DEFAULTS = {"priority": "Medium", "status": "Waiting to test", "type": "System Test"}

# A TC ID is anything ending in digits: "FEATURE-AREA-041", "TC-7".
ID_SHAPE = re.compile(r"^(.*?)(\d+)$")
# Bare references to a case by number, as a reviewer writes them.
REF_WORD = r"(?:เคส|ข้อ|case|Case|TC)"
DASHES = "–—-"


def split_id(tc: str):
    m = ID_SHAPE.match(tc or "")
    return (m.group(1), int(m.group(2)), len(m.group(2))) if m else None


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


def last_data_row(ws) -> int:
    r = FIRST_DATA_ROW
    while ws.cell(r, COL_TC_ID).value:
        r += 1
    return r - 1


def renumber(ws, removed: list[str]) -> dict[str, str]:
    """Close the gaps left by `removed`; return the old -> new TC ID map."""
    gone: dict[str, list[int]] = {}
    for tc in removed:
        parts = split_id(tc)
        if parts:
            gone.setdefault(parts[0], []).append(parts[1])

    renamed: dict[str, str] = {}
    last = last_data_row(ws)
    for row in range(FIRST_DATA_ROW, last + 1):
        tc = str(ws.cell(row, COL_TC_ID).value or "")
        parts = split_id(tc)
        if not parts:
            continue
        prefix, num, width = parts
        shift = sum(1 for n in gone.get(prefix, []) if n < num)
        if shift:
            new = f"{prefix}{num - shift:0{width}d}"
            ws.cell(row, COL_TC_ID).value = new
            renamed[tc] = new
    return renamed


def reference_fixer(removed: list[str], renamed: dict[str, str], dangling: list):
    """A function that rewrites in-cell references to the cases that moved.

    References to a case that was removed cannot be rewritten — there is
    nothing left to point at — so they are kept as they are and collected in
    `dangling` for the report. Somebody has to decide what those sentences
    should say now. With no renaming to do (--keep-numbers) the function still
    runs, purely to find those.
    """
    families: dict[str, tuple[list[int], int]] = {}
    for tc in removed:
        parts = split_id(tc)
        if parts:
            nums, _ = families.setdefault(parts[0], ([], parts[2]))
            nums.append(parts[1])
    # Bare "เคส 041" references can only be resolved against one numbering.
    bare = None
    if len(families) == 1:
        (nums, width), = families.values()
        bare = (sorted(nums), width)

    def shifted(num: int) -> int | None:
        nums, _ = bare
        if num in nums:
            return None
        return num - sum(1 for n in nums if n < num)

    dead_ids = [re.compile(re.escape(tc) + r"(?![0-9])") for tc in removed]
    full = re.compile(
        "(?:" + "|".join(re.escape(k) for k in sorted(renamed, key=len, reverse=True))
        + r")(?![0-9])") if renamed else None

    def fix(text: str) -> str:
        for tc, pat in zip(removed, dead_ids):
            if pat.search(text):
                dangling.append(tc)
        if bare:
            width = bare[1]
            for m in re.finditer(rf"{REF_WORD}\s*(?<![0-9])(\d{{{width}}})(?![0-9])", text):
                if shifted(int(m.group(1))) is None:
                    dangling.append(m.group(0).strip())
        if full:
            text = full.sub(lambda m: renamed[m.group(0)], text)
        if not (bare and renamed):
            return text
        width = bare[1]
        digits = rf"(?<![0-9])(\d{{{width}}})(?![0-9])"

        def one(m):
            new = shifted(int(m.group(2)))
            return m.group(1) + (f"{new:0{width}d}" if new is not None else m.group(2))

        def pair(m):
            lo, hi = shifted(int(m.group(2))), shifted(int(m.group(4)))
            if lo is None or hi is None:
                return m.group(0)
            return f"{m.group(1)}{lo:0{width}d}{m.group(3)}{hi:0{width}d}"

        text = re.sub(rf"({REF_WORD}\s*){digits}(\s*[{DASHES}]\s*){digits}", pair, text)
        return re.sub(rf"({REF_WORD}\s*){digits}", one, text)

    return fix


def retune_validation(ws, last: int) -> None:
    """Keep single-column dropdowns covering exactly the data rows."""
    shape = re.compile(rf"^([A-Z]+){FIRST_DATA_ROW}:\1\d+$")
    for dv in ws.data_validations.dataValidation:
        parts = [p for p in str(dv.sqref).split() if p]
        fixed = [shape.sub(rf"\g<1>{FIRST_DATA_ROW}:\g<1>{last}", p) for p in parts]
        if fixed != parts:
            dv.sqref = " ".join(fixed)


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
    ap.add_argument("--renumber-out", help="write the removed / old->new map here")
    ap.add_argument("--keep-numbers", action="store_true",
                    help="after a remove, leave the TC IDs as they are (gap stays)")
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
    adding, removing = [], []
    for i, e in enumerate(edits):
        if not isinstance(e, dict):
            problems.append(f"[{i}] not an object")
            continue
        tc = e.get("tc_id")
        op = e.get("op", "edit")
        if op == "add":
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
        if op == "remove":
            if tc not in rows:
                problems.append(f"[{i}] unknown TC ID: {tc!r}")
            elif tc in removing:
                problems.append(f"[{i}] removed twice: {tc!r}")
            else:
                removing.append(tc)
            for k in e:
                if k not in ("op", "tc_id", "reason"):
                    problems.append(f"[{i}] remove got an unknown field: {k!r}")
            continue
        if op != "edit":
            problems.append(f"[{i}] op must be edit, add or remove; got {op!r}")
            continue
        fld = e.get("field")
        if tc not in rows:
            problems.append(f"[{i}] unknown TC ID: {tc!r}")
        if fld not in FIELDS:
            problems.append(f"[{i}] field must be one of {', '.join(FIELDS)}; got {fld!r}")
        if "value" not in e:
            problems.append(f"[{i}] no value")
    for tc in removing:
        if any(e.get("tc_id") == tc and e.get("op", "edit") == "edit" for e in edits):
            problems.append(f"{tc} is both edited and removed — pick one")
    if problems:
        sys.exit("ไม่ได้แก้อะไรเลย — edits มีปัญหา:\n  " + "\n  ".join(problems))

    applied = []
    next_row = FIRST_DATA_ROW + total
    for e in edits:
        op = e.get("op", "edit")
        if op == "add":
            applied.append({
                "tc_id": e["tc_id"], "row": next_row, "field": "เคสใหม่",
                "before": "", "after": e.get("topic", ""), "changed": True,
            })
            if not args.dry_run:
                append_case(ws, next_row, e)
            next_row += 1
            continue
        if op == "remove":
            row = rows[e["tc_id"]]
            applied.append({
                "tc_id": e["tc_id"], "row": row, "field": "เคสที่ลบ",
                "before": str(ws.cell(row, FIELDS["topic"]).value or ""),
                "after": "", "changed": True,
            })
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

    renamed: dict[str, str] = {}
    dangling: list[str] = []
    refs_touched = 0
    if removing and not args.dry_run:
        for row in sorted((rows[tc] for tc in removing), reverse=True):
            ws.delete_rows(row, 1)
        if not args.keep_numbers:
            renamed = renumber(ws, removing)
        last = last_data_row(ws)
        fix = reference_fixer(removing, renamed, dangling)
        for row in range(FIRST_DATA_ROW, last + 1):
            ws.cell(row, 1).value = f'=IF(B{row}="","",ROW()-{FIRST_DATA_ROW - 1})'
            for col in TEXT_COLS:
                v = ws.cell(row, col).value
                if isinstance(v, str):
                    nv = fix(v)
                    if nv != v:
                        ws.cell(row, col).value = nv
                        refs_touched += 1
        retune_validation(ws, last)

    changed = [a for a in applied if a["changed"]]

    if args.dry_run:
        print(f"dry run · {len(changed)} / {len(applied)} edits would change a cell")
        if removing:
            print(f"  จะลบ {len(removing)} เคส: {', '.join(removing)}"
                  + ("" if args.keep_numbers else " แล้ว renumber ที่เหลือให้ต่อเนื่อง"))
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
        if removing:
            print(f"ลบ {len(removing)} เคส · renumber {len(renamed)} เคส · "
                  f"แก้อ้างอิงข้ามเคส {refs_touched} เซลล์")
            if dangling:
                print("  ⚠️  ยังมีประโยคที่อ้างถึงเคสที่ถูกลบ ชี้ไปที่เดิมไม่ได้แล้ว: "
                      + ", ".join(sorted(set(dangling))) + " — ต้องอ่านแล้วเขียนใหม่เอง")

    # every case is accounted for: the count moves by the adds minus the removes
    expect_total = total if args.dry_run else total + len(adding) - len(removing)
    wb2 = load_workbook(path)
    ws2 = wb2[SHEET]
    r = FIRST_DATA_ROW
    after_total = 0
    while ws2.cell(r, COL_TC_ID).value:
        after_total += 1
        r += 1
    if after_total != expect_total:
        sys.exit(f"จำนวนเคสควรเป็น {expect_total} แต่ได้ {after_total} — หยุดและตรวจไฟล์สำรอง")
    if (adding or removing) and not args.dry_run:
        print(f"เคส {total} → {after_total} "
              f"(เพิ่ม {len(adding)} · ลบ {len(removing)} ตามที่สั่งพอดี)")
    else:
        print(f"เคสครบ {after_total} เคสเท่าเดิม")

    if args.applied_out:
        stamped = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        for a in applied:
            a["applied_at"] = stamped
        with open(args.applied_out, "w", encoding="utf-8") as fh:
            json.dump(applied, fh, ensure_ascii=False, indent=1)
        print(f"-> {args.applied_out}")

    if args.renumber_out:
        with open(args.renumber_out, "w", encoding="utf-8") as fh:
            json.dump({"removed": removing, "renamed": renamed,
                       "dangling_refs": sorted(set(dangling))}, fh,
                      ensure_ascii=False, indent=1)
        print(f"-> {args.renumber_out}")

    for a in changed:
        print(f"  {a['tc_id']} · {a['field']} · แถว {a['row']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
