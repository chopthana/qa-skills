#!/usr/bin/env python3
"""Write a QA test-case workbook from a JSON case list.

Reproduces the two-sheet layout documented in
references/template-format.md (the team's own template file is the authority):
  - sheet `list`      : dropdown sources (status, test type, priority)
  - sheet `TestResult`: one row per case, yellow header, borders, `ลำดับ`
                        formula, `ประเภทการทดสอบ` + priority data validation.

Usage:
  python3 build_workbook.py --input cases.json --output out.xlsx [--program NAME]

cases.json:
  {
    "program": "ตั้งค่ารหัสกะการทำงาน",      # optional; written to G2
    "type": "System Test",                    # optional default for every case
    "cases": [
      {
        "tc_id": "PROMO-CODE-SETTING-001",
        "topic": "...",
        "steps":   ["...", "..."],            # or a single string with newlines
        "expected":["...", "..."],
        "note": "กรณีปกติราบรื่น",             # optional
        "priority": "Medium",                 # High | Medium | Low (default Medium)
        "status": "Waiting to test",          # optional
        "type": "System Test"                 # optional per-case override
      }
    ]
  }

Needs openpyxl (pip install openpyxl).
"""
from __future__ import annotations

import argparse
import json
import sys

try:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter
    from openpyxl.workbook.defined_name import DefinedName
    from openpyxl.worksheet.datavalidation import DataValidation
except ImportError:  # pragma: no cover
    sys.exit("openpyxl is required: pip install openpyxl")

# --- template constants -----------------------------------------------------
GREEN = "FF007635"
HEADER_FILL = "FFFFFF66"
CELL_FILL = "FFF9FAFB"

THIN = Side(style="thin")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

COLUMN_WIDTHS = {
    "A": 11.0,
    "B": 21.0,
    "C": 13.0,
    "D": 73.0,
    "E": 87.85546875,
    "F": 13.0,
    "G": 17.5703125,
    "H": 16.42578125,
    "I": 22.5703125,
    "J": 42.85546875,
    "K": 18.28515625,
    "L": 37.140625,
}

HEADERS = [
    "ลำดับ",
    "ประเภทการทดสอบ",
    "TC ID",
    "หัวข้อ",
    "กรณีทดสอบและขั้นตอนการทดสอบ",
    "ผลการทดสอบที่คาดหวัง",
    "สถานะ",
    "Tester",
    "Test date",
    "หมายเหตุ",
    "ระดับความสำคัญ",
    "Remark for Pass with Condition",
]

VALID_STATUS = ["Passed", "Passed with condition", "Not pass", "Waiting to test"]
VALID_TYPE = ["Unit Test", "Integration Test", "System Test", "System Integration Test", "UAT"]
VALID_PRIORITY = ["High", "Medium", "Low"]


def _numbered(lines) -> str:
    """Join steps/expected into '1. a\\n2. b', matching the source workbooks."""
    if lines is None:
        return ""
    if isinstance(lines, str):
        return lines.strip()
    out = []
    for i, line in enumerate(lines, start=1):
        text = str(line).rstrip()
        out.append(f"{i}. {text}" if text else "")
    return "\n".join(out)


def _fmt(cell, *, font=None, fill=None, align=None, border=True):
    if font:
        cell.font = font
    if fill:
        cell.fill = PatternFill("solid", fgColor=fill)
    if align:
        cell.alignment = align
    if border:
        cell.border = BORDER


def build(data: dict, output: str, program_override: str | None = None) -> int:
    cases = data.get("cases") or []
    if not cases:
        sys.exit("no cases in input")
    default_type = data.get("type", "System Test")
    program = program_override or data.get("program", "")

    wb = Workbook()
    ws_list = wb.active
    ws_list.title = "list"
    ws_tr = wb.create_sheet("TestResult")

    # --- list sheet ---------------------------------------------------------
    for i, value in enumerate(VALID_STATUS, start=1):
        ws_list.cell(i, 1, value)
    for i, value in enumerate(VALID_TYPE, start=1):
        ws_list.cell(i, 2, value)
    for i, value in enumerate(VALID_PRIORITY, start=1):
        ws_list.cell(i, 3, value)

    # --- TestResult chrome --------------------------------------------------
    for r in range(1, 4):
        for c in range(1, 13):
            ws_tr.cell(r, c).fill = PatternFill("solid", fgColor=GREEN)
    ws_tr.row_dimensions[1].height = 30
    ws_tr.row_dimensions[2].height = 30
    ws_tr.row_dimensions[3].height = 30
    ws_tr.row_dimensions[4].height = 24
    ws_tr["F2"] = "โปรแกรม:"
    ws_tr["F2"].font = Font(name="Tahoma", size=16)
    ws_tr["F2"].alignment = Alignment(horizontal="right", vertical="center")
    if program:
        ws_tr["G2"] = program
        ws_tr["G2"].font = Font(name="Tahoma", size=16)
        ws_tr["G2"].alignment = Alignment(horizontal="left", vertical="center")

    header_font = Font(name="Tahoma", size=11)
    header_align = Alignment(horizontal="center", vertical="center")
    for c, title in enumerate(HEADERS, start=1):
        cell = ws_tr.cell(4, c, title)
        _fmt(cell, font=header_font, fill=HEADER_FILL, align=header_align)

    for col, width in COLUMN_WIDTHS.items():
        ws_tr.column_dimensions[col].width = width

    # --- cases --------------------------------------------------------------
    first_row = 5
    for offset, case in enumerate(cases):
        r = first_row + offset
        ws_tr.row_dimensions[r].height = None  # let Excel size to wrapped text

        # A: sequence formula
        a = ws_tr.cell(r, 1, f'=IF(B{r}="","",ROW()-{first_row - 1})')
        _fmt(a, font=Font(name="Tahoma", size=11, bold=True),
             align=Alignment(horizontal="center", vertical="top"))

        b = ws_tr.cell(r, 2, case.get("type", default_type))
        _fmt(b, font=Font(name="Tahoma", size=11),
             align=Alignment(horizontal="center", vertical="top"))

        c = ws_tr.cell(r, 3, case.get("tc_id", ""))
        _fmt(c, font=Font(name="Calibri", size=11, bold=True),
             align=Alignment(horizontal="center", vertical="top"))

        d = ws_tr.cell(r, 4, case.get("topic", ""))
        _fmt(d, font=Font(name="Calibri", size=10), fill=CELL_FILL,
             align=Alignment(horizontal="left", vertical="top", wrap_text=True))

        e = ws_tr.cell(r, 5, _numbered(case.get("steps")))
        _fmt(e, font=Font(name="Calibri", size=10), fill=CELL_FILL,
             align=Alignment(horizontal="left", vertical="top", wrap_text=True))

        f = ws_tr.cell(r, 6, _numbered(case.get("expected")))
        _fmt(f, font=Font(name="Calibri", size=10), fill=CELL_FILL,
             align=Alignment(horizontal="left", vertical="top", wrap_text=True))

        g = ws_tr.cell(r, 7, case.get("status", "Waiting to test"))
        _fmt(g, font=Font(name="Tahoma", size=11),
             align=Alignment(horizontal="center", vertical="top"))

        h = ws_tr.cell(r, 8, case.get("tester"))
        _fmt(h, font=Font(name="Tahoma", size=11),
             align=Alignment(horizontal="center", vertical="top", wrap_text=True))

        i = ws_tr.cell(r, 9, case.get("test_date"))
        _fmt(i, font=Font(name="Tahoma", size=11),
             align=Alignment(horizontal="center", vertical="top", wrap_text=True))

        j = ws_tr.cell(r, 10, case.get("note", ""))
        _fmt(j, font=Font(name="Segoe UI", size=10), fill=CELL_FILL,
             align=Alignment(horizontal="left", vertical="top", wrap_text=True))

        k = ws_tr.cell(r, 11, case.get("priority", "Medium"))
        _fmt(k, font=Font(name="Tahoma", size=11),
             align=Alignment(horizontal="left", vertical="top"))

        l = ws_tr.cell(r, 12, case.get("remark"))
        _fmt(l, font=Font(name="Tahoma", size=11),
             align=Alignment(horizontal="left", vertical="top"))

    last_row = first_row + len(cases) - 1

    # --- named range + validation (mirror the template) ---------------------
    wb.defined_names.add(
        DefinedName("test", attr_text="TestResult!$B$1:$B$5")
    )
    type_dv = DataValidation(type="list", formula1="test", allow_blank=True)
    ws_tr.add_data_validation(type_dv)
    type_dv.add(f"B{first_row}:B{last_row}")

    priority_dv = DataValidation(type="list", formula1="$D$1:$D$3", allow_blank=True)
    ws_tr.add_data_validation(priority_dv)
    priority_dv.add("K4")
    priority_dv.add(f"K{first_row}:K1048576")

    ws_tr.freeze_panes = "E5"
    ws_tr.auto_filter.ref = f"A1:K{last_row}"

    wb.save(output)
    return len(cases)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", required=True, help="cases.json")
    ap.add_argument("--output", required=True, help=".xlsx to write")
    ap.add_argument("--program", default=None, help="program name for G2")
    args = ap.parse_args()

    with open(args.input, encoding="utf-8") as fh:
        data = json.load(fh)

    count = build(data, args.output, args.program)
    print(f"wrote {count} cases -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
