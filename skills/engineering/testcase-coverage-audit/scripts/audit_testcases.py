#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extract an existing test-case set and run the mechanical conflict pass.

Reads the common two-sheet QA workbook format (a results sheet whose header
row is not row 1 — `TestResult` by name where present, else the first sheet), a CSV,
or a Markdown table, and prints:

  1. every case as  id | topic | steps | expected | note
  2. the candidates each mechanical check flagged, with the reason

The checks catch shape, never meaning. Read every candidate by hand before it
becomes a finding; read the whole set by hand for what no pattern can see.

Usage:
  python3 audit_testcases.py --input cases.xlsx
  python3 audit_testcases.py --input cases.xlsx --only two-data-values,phased
  python3 audit_testcases.py --input cases.xlsx --quiet      # candidates only
"""
from __future__ import annotations

import argparse
import csv
import difflib
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

# ── the workbook's own column order (header row 4) ───────────────────────────
COL_TC_ID, COL_TOPIC, COL_STEPS, COL_EXPECTED, COL_NOTE = 3, 4, 5, 6, 10
HEADER_ROW = 4

NEAR_DUPLICATE_RATIO = 0.90
OVERSTUFFED_LINES = 5


@dataclass
class Case:
    row: int
    tc_id: str
    topic: str
    steps: str
    expected: str
    note: str
    flags: list[tuple[str, str]] = field(default_factory=list)

    def flag(self, check: str, why: str) -> None:
        self.flags.append((check, why))

    @property
    def expected_lines(self) -> list[str]:
        return [ln.strip() for ln in self.expected.splitlines() if ln.strip()]

    @property
    def body(self) -> str:
        return f"{self.topic}\n{self.steps}\n{self.expected}"


# ── readers ─────────────────────────────────────────────────────────────────
def read_xlsx(path: Path) -> list[Case]:
    try:
        import openpyxl
    except ImportError:
        sys.exit("needs openpyxl: pip install openpyxl")
    wb = openpyxl.load_workbook(path, data_only=False)
    ws = wb["TestResult"] if "TestResult" in wb.sheetnames else wb.worksheets[0]
    cases: list[Case] = []
    for row in range(HEADER_ROW + 1, ws.max_row + 1):
        tc_id = ws.cell(row, COL_TC_ID).value
        if not tc_id:
            continue
        cases.append(
            Case(
                row=row,
                tc_id=str(tc_id).strip(),
                topic=str(ws.cell(row, COL_TOPIC).value or "").strip(),
                steps=str(ws.cell(row, COL_STEPS).value or "").strip(),
                expected=str(ws.cell(row, COL_EXPECTED).value or "").strip(),
                note=str(ws.cell(row, COL_NOTE).value or "").strip(),
            )
        )
    return cases


def _pick(header: list[str], *names: str) -> int | None:
    lowered = [h.strip().lower() for h in header]
    for name in names:
        for index, cell in enumerate(lowered):
            if name in cell:
                return index
    return None


def read_csv(path: Path) -> list[Case]:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.reader(fh))
    if not rows:
        return []
    header = rows[0]
    idx = {
        "id": _pick(header, "tc id", "tc_id", "id"),
        "topic": _pick(header, "หัวข้อ", "topic", "title"),
        "steps": _pick(header, "ขั้นตอน", "steps", "step"),
        "expected": _pick(header, "คาดหวัง", "expected"),
        "note": _pick(header, "หมายเหตุ", "note", "remark"),
    }
    cases = []
    for number, row in enumerate(rows[1:], 2):
        get = lambda key: (row[idx[key]].strip() if idx[key] is not None and idx[key] < len(row) else "")
        if not get("id") and not get("topic"):
            continue
        cases.append(Case(number, get("id") or f"row{number}", get("topic"),
                          get("steps"), get("expected"), get("note")))
    return cases


def read_markdown(path: Path) -> list[Case]:
    lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip().startswith("|")]
    rows = [[cell.strip() for cell in ln.strip().strip("|").split("|")] for ln in lines]
    rows = [r for r in rows if not all(set(c) <= set("-: ") for c in r)]
    if not rows:
        return []
    header, body = rows[0], rows[1:]
    idx = {
        "id": _pick(header, "tc id", "tc_id", "id"),
        "topic": _pick(header, "หัวข้อ", "topic", "title"),
        "steps": _pick(header, "ขั้นตอน", "steps", "step"),
        "expected": _pick(header, "คาดหวัง", "expected"),
        "note": _pick(header, "หมายเหตุ", "note", "remark"),
    }
    cases = []
    for number, row in enumerate(body, 2):
        get = lambda key: (row[idx[key]].strip() if idx[key] is not None and idx[key] < len(row) else "")
        if not get("id") and not get("topic"):
            continue
        cases.append(Case(number, get("id") or f"row{number}", get("topic"),
                          get("steps"), get("expected"), get("note")))
    return cases


def read_cases(path: Path) -> list[Case]:
    suffix = path.suffix.lower()
    if suffix in (".xlsx", ".xlsm"):
        return read_xlsx(path)
    if suffix == ".csv":
        return read_csv(path)
    if suffix in (".md", ".markdown"):
        return read_markdown(path)
    sys.exit(f"unsupported input: {suffix} (want .xlsx / .csv / .md)")


# ── the mechanical checks ───────────────────────────────────────────────────
SAVED = ("บันทึกสำเร็จ", "บันทึกได้", "สร้างสำเร็จ", "เพิ่มสำเร็จ", "saved", "success")
NOT_SAVED = ("ไม่บันทึก", "บันทึกไม่ได้", "ไม่สามารถบันทึก", "ไม่ถูกบันทึก", "not saved", "rejected")
QUANTITY = re.compile(r"(\d+)\s*(หลัก|ตัว|ตัวอักษร|อักขระ|ค่า|รายการ|บรรทัด|chars?|digits?)")
CASE_PREFIX = re.compile(r"^(?:\d+\.\s*)?กรณี[^:：]{1,40}[:：]")
PHASE_PREFIX = re.compile(r"^(?:\d+\.\s*)?(?:ขั้น(?:ที่)?\s*\d+|step\s*\d+)\s*[:：]", re.IGNORECASE)
CONDITIONAL = re.compile(r"(หาก|ถ้า[^ไ]|\(ถ้า[^)]*\)|ในกรณีที่|if\s)")
DISABLED = ("disable", "disabled", "กดไม่ได้", "ปิดการใช้งาน")
ERROR_SHOWN = ("ขอบแดง", "แสดงข้อความ", "error", "โปรดเลือก", "โปรดระบุ")
FLAGGY = ("⚠️", "TBC", "tbd", "ต้องยืนยัน", "ระบุให้ชัด")
CLEAN_NOTE = ("กรณีปกติราบรื่น", "normal", "happy")
# a value the expected quotes that the steps ought to have entered
QUOTED = re.compile(r"[“\"']([^“”\"']{2,24})[”\"']")
# a quoted string these words introduce is a string being asserted, not data the
# steps should have entered — so it is never step-expected drift
STRING_ASSERTION = ("label", "placeholder", "error", "banner", "toast", "tooltip",
                    "aria", "ข้อความ", "หัวข้อ", "ปุ่ม", "คำ", "สะกด", "wording",
                    "แสดง", "แจ้ง", "ไม่ใช้", "ไม่มีคำ", "ไม่ปรากฏ", "เรียก")
# a case whose whole subject is wording asserts strings everywhere by design
WORDING_CASE = ("[wording]", "wording", "สะกด", "typo", "ข้อความ", "label")


def check_success_and_failure(case: Case) -> None:
    text = case.expected
    if any(w in text for w in SAVED) and any(w in text for w in NOT_SAVED):
        case.flag("success+failure",
                  "expected asserts both a save and a non-save — one row cannot hold two verdicts")


def check_two_data_values(case: Case) -> None:
    found = {(m.group(1), m.group(2)) for m in QUANTITY.finditer(case.expected)}
    by_unit: dict[str, set[str]] = {}
    for amount, unit in found:
        by_unit.setdefault(unit, set()).add(amount)
    for unit, amounts in by_unit.items():
        if len(amounts) > 1:
            case.flag("two-data-values",
                      f"expected carries {len(amounts)} different values for one field: "
                      + ", ".join(f"{a} {unit}" for a in sorted(amounts, key=int)))


def check_case_prefixed(case: Case) -> None:
    hits = [ln for ln in case.expected_lines if CASE_PREFIX.match(ln)]
    if hits:
        case.flag("case-prefixed",
                  f"{len(hits)} expected line(s) open with 'กรณี …:' — each is its own scenario")


def check_conditional(case: Case) -> None:
    hits = [ln for ln in case.expected_lines if CONDITIONAL.search(ln)]
    if hits:
        case.flag("conditional",
                  f"expected hedged with a condition, unverifiable as written: “{hits[0][:70]}”")


def check_phased(case: Case) -> None:
    hits = [ln for ln in case.expected_lines if PHASE_PREFIX.match(ln)]
    if len(hits) > 1:
        case.flag("phased",
                  f"expected split into {len(hits)} step phases — keep only if it is one "
                  "progressive flow, else split")


def check_overstuffed(case: Case) -> None:
    count = len(case.expected_lines)
    if count > OVERSTUFFED_LINES:
        case.flag("overstuffed", f"{count} expected lines — check it is still one behavior")


def check_clean_note_dirty_expected(case: Case) -> None:
    note_is_clean = ((any(w in case.note for w in CLEAN_NOTE) or not case.note)
                     and not any(w in case.note for w in FLAGGY))
    expected_is_flaggy = any(w in case.expected for w in FLAGGY)
    if note_is_clean and expected_is_flaggy:
        case.flag("clean-note-dirty-expected",
                  "expected carries a ⚠️/TBC marker but the note says the case is clean")


def check_unreachable_hint(case: Case) -> None:
    for line in case.expected_lines:
        # a negative ("ยังไม่แสดงขอบแดง") is consistent with disabled, not a conflict
        if any(w in line for w in ("ไม่แสดง", "ไม่มี", "ยังไม่")):
            continue
        if any(w in line for w in DISABLED) and any(w in line for w in ERROR_SHOWN):
            case.flag("unreachable-hint",
                      "one expected line calls a field disabled AND asserts an error on it — "
                      f"confirm that state is reachable: “{line[:70]}”")
            return


def check_step_expected_drift(case: Case) -> None:
    topic = case.topic.lower()
    if any(w in topic for w in WORDING_CASE):
        return  # a wording case quotes strings by design
    steps = case.steps
    missing: list[str] = []
    for line in case.expected_lines:
        if any(w in line.lower() for w in STRING_ASSERTION):
            continue  # the line is asserting a string, not using data
        for match in QUOTED.finditer(line):
            value = match.group(1)
            if (len(value) >= 3 and value not in steps and value not in case.topic
                    and not value.startswith(("โปรด", "ไม่", "เนื่องจาก"))
                    and value not in missing):
                missing.append(value)
    if missing:
        case.flag("step-expected-drift",
                  "value(s) asserted in expected that no step enters: "
                  + ", ".join(f"“{m}”" for m in sorted(missing)[:4]))


PER_CASE_CHECKS = {
    "success+failure": check_success_and_failure,
    "two-data-values": check_two_data_values,
    "case-prefixed": check_case_prefixed,
    "conditional": check_conditional,
    "phased": check_phased,
    "overstuffed": check_overstuffed,
    "clean-note-dirty-expected": check_clean_note_dirty_expected,
    "unreachable-hint": check_unreachable_hint,
    "step-expected-drift": check_step_expected_drift,
}


def check_near_duplicates(cases: list[Case], only: set[str] | None) -> list[str]:
    if only and "near-duplicate" not in only:
        return []
    pairs = []
    for i, left in enumerate(cases):
        for right in cases[i + 1:]:
            ratio = difflib.SequenceMatcher(None, left.body, right.body).ratio()
            if ratio >= NEAR_DUPLICATE_RATIO:
                pairs.append(f"  near-duplicate  {left.tc_id} ↔ {right.tc_id}  "
                             f"({ratio:.0%} similar)\n"
                             f"      {left.topic[:72]}\n      {right.topic[:72]}")
    return pairs


# ── output ──────────────────────────────────────────────────────────────────
def dump(cases: list[Case]) -> None:
    for case in cases:
        print(f"ROW {case.row} | {case.tc_id}")
        print(f"TOPIC: {case.topic}")
        print(f"STEPS: {case.steps}")
        print(f"EXPECTED: {case.expected}")
        print(f"NOTE: {case.note}")
        print("-" * 70)


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit an existing test-case set.")
    parser.add_argument("--input", required=True, help=".xlsx / .csv / .md test-case file")
    parser.add_argument("--only", help="comma-separated check names to run")
    parser.add_argument("--quiet", action="store_true", help="skip the full case dump")
    args = parser.parse_args()

    path = Path(args.input).expanduser()
    if not path.exists():
        sys.exit(f"not found: {path}")
    only = {name.strip() for name in args.only.split(",")} if args.only else None

    cases = read_cases(path)
    if not cases:
        sys.exit("no cases found — check the sheet name and that the header is on row 4")

    if not args.quiet:
        dump(cases)

    for case in cases:
        for name, check in PER_CASE_CHECKS.items():
            if only and name not in only:
                continue
            check(case)

    flagged = [c for c in cases if c.flags]
    duplicate_pairs = check_near_duplicates(cases, only)

    print(f"\n=== {len(cases)} cases · {len(flagged)} flagged · "
          f"{len(duplicate_pairs)} near-duplicate pair(s) ===\n")
    for case in flagged:
        print(f"{case.tc_id}  (row {case.row})  {case.topic[:64]}")
        for name, why in case.flags:
            print(f"  {name:28} {why}")
        print()
    for line in duplicate_pairs:
        print(line + "\n")
    if duplicate_pairs:
        print("  (cases that differ only in which field is under test are parallel by\n"
              "   design, not duplicates — a dirty-state case per control is coverage.)\n")

    tally: dict[str, int] = {}
    for case in flagged:
        for name, _ in case.flags:
            tally[name] = tally.get(name, 0) + 1
    if tally:
        print("by check:")
        for name, count in sorted(tally.items(), key=lambda kv: -kv[1]):
            print(f"  {count:3}  {name}")

    print("\nThese are candidates, not findings. Read each one, then read the whole")
    print("set by hand for internal contradictions, unreachable states, cross-case")
    print("disagreements and the coverage buckets in SKILL.md § 4.")


if __name__ == "__main__":
    main()
