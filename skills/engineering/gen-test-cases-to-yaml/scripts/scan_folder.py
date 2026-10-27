#!/usr/bin/env python3
"""Scan a folder of QA test-case files and extract every case row.

Usage:
  scan_folder.py <folder-or-file>... [--json OUT.json] [--format md|none]
                                     [--recursive] [--quiet]

Produces two things:
  * a JSON inventory (--json) used later by reconcile.py for no-loss accounting
  * a markdown dump (--format md, the default) of every extracted row, written
    to stdout, for reading while converting

Reads .xlsx/.xlsm (openpyxl) and .csv/.tsv (stdlib). Files it cannot read are
listed with status `unreadable` and a reason instead of being skipped silently.

Needs openpyxl for Excel input; prints install instructions if missing.
"""

import argparse
import csv
import json
import re
import sys
from pathlib import Path

EXCEL_SUFFIXES = {".xlsx", ".xlsm", ".xltx", ".xltm"}
TEXT_SUFFIXES = {".csv", ".tsv"}

# Column synonyms, normalized (lowercase, whitespace and punctuation stripped).
SYNONYMS = {
    "seq": ["ลำดับ", "ลำดับที่", "no", "no.", "#", "item", "ข้อ"],
    "test_type": ["ประเภทการทดสอบ", "testtype", "typeoftest", "ประเภท"],
    "tc_id": ["tcid", "testcaseid", "caseid", "tcno", "testcaseno", "รหัสกรณีทดสอบ"],
    "title": ["หัวข้อ", "หัวข้อการทดสอบ", "title", "testcasename", "scenario", "description", "คำอธิบาย"],
    "precondition": [
        "เงื่อนไขก่อนทดสอบ", "เงื่อนไข", "precondition", "preconditions",
        "prerequisite", "prerequisites", "given", "ข้อกำหนดเบื้องต้น",
    ],
    "steps": [
        "กรณีทดสอบและขั้นตอนการทดสอบ", "ขั้นตอนการทดสอบ", "ขั้นตอน", "กรณีทดสอบ",
        "steps", "teststeps", "stepstoreproduce", "when", "testprocedure",
    ],
    "expected": [
        "ผลการทดสอบที่คาดหวัง", "ผลลัพธ์ที่คาดหวัง", "ผลลัพธ์หน้าจอ", "ผลที่คาดหวัง",
        "expectedresult", "expectedresults", "expected", "expectedui", "then",
    ],
    "status": ["สถานะ", "status", "ผลการทดสอบ", "result", "testresult"],
    "tester": ["tester", "ผู้ทดสอบ"],
    "test_date": ["testdate", "วันที่ทดสอบ", "date"],
    "note": ["หมายเหตุ", "note", "notes", "comment"],
    "priority": ["ระดับความสำคัญ", "priority", "severity"],
    "remark": ["remark", "remarkforpasswithcondition", "remarks"],
}

# Fields that carry test content: a row is a case row when any of them is set.
CONTENT_FIELDS = ("tc_id", "title", "steps", "expected", "precondition")

# Fields that are QA run tracking, not case content. Named here so the report
# can say explicitly that they were excluded by design.
RUN_METADATA_FIELDS = ("status", "tester", "test_date", "priority", "test_type")

# Issue keys as trackers write them: JIRA-123, TCK 1042, ABC-7.  The project
# part is 2-10 letters so ordinary words do not match; --ticket-pattern
# overrides it for a tracker that numbers differently.
TICKET_RE = re.compile(r"\b([A-Za-z]{2,10})\s*-?\s*(\d{1,6})\b")


def norm(text):
    return re.sub(r"[\s​_\-/:().]+", "", str(text or "")).strip().lower()


def match_field(header):
    n = norm(header)
    if not n:
        return None
    for field, names in SYNONYMS.items():
        for name in names:
            if n == norm(name):
                return field
    for field, names in SYNONYMS.items():
        for name in names:
            nn = norm(name)
            if len(nn) >= 4 and (nn in n or n in nn):
                return field
    return None


def ticket_of(path, pattern=TICKET_RE):
    """Best-effort issue key from a filename: `… - ALC - 2275 - …` -> `ALC-2275`."""
    m = pattern.search(path.name)
    if not m:
        return None
    if m.lastindex and m.lastindex >= 2:
        return f"{m.group(1).upper()}-{m.group(2)}"
    return m.group(m.lastindex or 0)


def cell_text(value):
    if value is None:
        return ""
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value).replace("\r\n", "\n").replace("\r", "\n").strip()


def grid_from_excel_sheet(ws, merged_ranges):
    rows = [[cell_text(c.value) for c in row] for row in ws.iter_rows()]
    # read_only=False is required for merged ranges; spread the anchor value
    # across every cell of the range so merged headers and merged data cells
    # are not read as empty.
    for rng in merged_ranges:
        r0, r1 = rng.min_row - 1, rng.max_row - 1
        c0, c1 = rng.min_col - 1, rng.max_col - 1
        if r0 >= len(rows) or c0 >= len(rows[r0]):
            continue
        value = rows[r0][c0]
        if not value:
            continue
        for r in range(r0, min(r1 + 1, len(rows))):
            for c in range(c0, min(c1 + 1, len(rows[r]))):
                if not rows[r][c]:
                    rows[r][c] = value
    while rows and not any(x.strip() for x in rows[-1]):
        rows.pop()
    return rows


def find_header(rows, limit=20):
    """Return (index, {col_index: field}) for the best header row, or (None, {})."""
    best = (None, {}, 0)
    for i, row in enumerate(rows[:limit]):
        mapping, hits = {}, 0
        for j, header in enumerate(row):
            field = match_field(header)
            if field:
                mapping[j] = field
                hits += 1
        if hits > best[2]:
            best = (i, mapping, hits)
    if best[2] >= 3:
        return best[0], best[1]
    return None, {}


def extract_rows(rows, header_index, mapping, headers):
    """Turn data rows below the header into case records."""
    out = []
    for i in range(header_index + 1, len(rows)):
        row = rows[i]
        record = {"row": i + 1, "extra": {}, "expected_columns": []}
        for field in SYNONYMS:
            record[field] = ""
        for j, value in enumerate(row):
            value = value.strip()
            field = mapping.get(j)
            header = headers[j] if j < len(headers) else f"column{j + 1}"
            if field == "expected":
                if value:
                    record["expected_columns"].append({"header": header, "text": value})
                    record["expected"] = (
                        record["expected"] + "\n" + value if record["expected"] else value
                    )
            elif field:
                if value and record[field]:
                    record[field] = record[field] + "\n" + value
                elif value:
                    record[field] = value
            elif value:
                record["extra"][header or f"column{j + 1}"] = value
        if any(record[f] for f in CONTENT_FIELDS):
            out.append(record)
    return out


def scan_excel(path):
    try:
        from openpyxl import load_workbook
    except ImportError:
        sys.exit(
            "openpyxl is not installed. Run: pip3 install --user openpyxl"
        )
    try:
        wb = load_workbook(path, data_only=True)
    except Exception as exc:  # noqa: BLE001 - report, never drop the file
        reason = str(exc)
        hint = ""
        if "not a zip file" in reason.lower() or "CDFV2" in reason:
            hint = (
                " The file is probably password-protected or saved in a legacy/"
                "encrypted format. Ask QA to re-export it as a plain .xlsx, or "
                "install msoffcrypto-tool and decrypt it first."
            )
        return {"status": "unreadable", "reason": reason + hint, "sheets": []}

    sheets = []
    for ws in wb.worksheets:
        merged = list(ws.merged_cells.ranges)
        rows = grid_from_excel_sheet(ws, merged)
        if not rows:
            sheets.append({"name": ws.title, "kind": "empty", "rows": []})
            continue
        header_index, mapping = find_header(rows)
        if header_index is None:
            sheets.append(
                {
                    "name": ws.title,
                    "kind": "non-case",
                    "reason": "no test-case header row found (lookup/legend sheet?)",
                    "preview": [r for r in rows[:6]],
                    "rows": [],
                }
            )
            continue
        headers = rows[header_index]
        records = extract_rows(rows, header_index, mapping, headers)
        sheets.append(
            {
                "name": ws.title,
                "kind": "cases",
                "header_row": header_index + 1,
                "columns": {headers[j] or f"column{j + 1}": f for j, f in sorted(mapping.items())},
                "unmapped_columns": sorted(
                    {
                        (headers[j] or f"column{j + 1}")
                        for j in range(len(headers))
                        if j not in mapping and headers[j].strip()
                    }
                ),
                "rows": records,
            }
        )
    return {"status": "ok", "sheets": sheets}


def scan_text(path):
    delimiter = "\t" if path.suffix.lower() == ".tsv" else ","
    try:
        text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        text = path.read_text(encoding="cp874", errors="replace")
    rows = [[cell_text(c) for c in r] for r in csv.reader(text.splitlines(), delimiter=delimiter)]
    while rows and not any(x.strip() for x in rows[-1]):
        rows.pop()
    if not rows:
        return {"status": "ok", "sheets": [{"name": path.name, "kind": "empty", "rows": []}]}
    header_index, mapping = find_header(rows)
    if header_index is None:
        return {
            "status": "unreadable",
            "reason": "no test-case header row found; convert the file by hand or fix its headers",
            "sheets": [],
        }
    headers = rows[header_index]
    return {
        "status": "ok",
        "sheets": [
            {
                "name": path.name,
                "kind": "cases",
                "header_row": header_index + 1,
                "columns": {headers[j] or f"column{j + 1}": f for j, f in sorted(mapping.items())},
                "unmapped_columns": [],
                "rows": extract_rows(rows, header_index, mapping, headers),
            }
        ],
    }


def collect_paths(targets, recursive):
    paths = []
    for target in targets:
        p = Path(target).expanduser()
        if p.is_dir():
            globber = p.rglob if recursive else p.glob
            for child in sorted(globber("*")):
                if child.name.startswith("~$") or child.name.startswith("."):
                    continue
                if child.suffix.lower() in EXCEL_SUFFIXES | TEXT_SUFFIXES:
                    paths.append(child)
        elif p.exists():
            paths.append(p)
        else:
            print(f"ERROR no such path: {p}", file=sys.stderr)
    return paths


def dump_markdown(report):
    print(f"# Source scan: {report['source']}\n")
    print(
        f"{report['totals']['files']} file(s), "
        f"{report['totals']['case_rows']} case row(s), "
        f"{report['totals']['unreadable']} unreadable\n"
    )
    for f in report["files"]:
        print(f"## {f['name']}")
        print(f"- path: `{f['path']}`")
        print(f"- ticket: {f['ticket'] or 'unknown'}")
        if f["status"] != "ok":
            print(f"- **UNREADABLE**: {f['reason']}\n")
            continue
        print(f"- case rows: {f['case_rows']}\n")
        for sheet in f["sheets"]:
            if sheet["kind"] != "cases":
                reason = sheet.get("reason", sheet["kind"])
                print(f"### Sheet `{sheet['name']}` — not case data ({reason})")
                for row in sheet.get("preview", []):
                    cells = " | ".join(c for c in row if c.strip())
                    if cells:
                        print(f"- {cells}")
                print()
                continue
            print(f"### Sheet `{sheet['name']}` — {len(sheet['rows'])} case row(s)")
            print(f"- header row: {sheet['header_row']}")
            print(f"- mapped columns: {sheet['columns']}")
            if sheet.get("unmapped_columns"):
                print(f"- UNMAPPED columns (check for content): {sheet['unmapped_columns']}")
            print()
            for record in sheet["rows"]:
                label = record["tc_id"] or record["title"][:40] or f"row {record['row']}"
                print(f"#### row {record['row']} — `{label}`")
                for field in ("seq", "test_type", "tc_id", "title", "priority", "status"):
                    if record[field]:
                        print(f"- {field}: {record[field]}")
                for field in ("precondition", "steps"):
                    if record[field]:
                        print(f"- {field}:")
                        for line in record[field].split("\n"):
                            if line.strip():
                                print(f"    {line.strip()}")
                for column in record["expected_columns"]:
                    print(f"- expected ({column['header']}):")
                    for line in column["text"].split("\n"):
                        if line.strip():
                            print(f"    {line.strip()}")
                for field in ("note", "remark"):
                    if record[field]:
                        print(f"- {field}: {record[field]}")
                if record["extra"]:
                    print(f"- other columns: {record['extra']}")
                print()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("targets", nargs="+")
    ap.add_argument("--json", dest="json_out")
    ap.add_argument("--format", choices=["md", "none"], default="md")
    ap.add_argument("--recursive", action="store_true")
    ap.add_argument(
        "--ticket-pattern",
        help="regex for the issue key in a filename; group 1+2 are joined as KEY-NUM, "
             "a single group is used verbatim (default: a JIRA-style key)",
    )
    args = ap.parse_args()

    ticket_re = re.compile(args.ticket_pattern) if args.ticket_pattern else TICKET_RE
    paths = collect_paths(args.targets, args.recursive)
    files, case_rows, unreadable = [], 0, 0
    for path in paths:
        if path.suffix.lower() in EXCEL_SUFFIXES:
            result = scan_excel(path)
        else:
            result = scan_text(path)
        count = sum(len(s["rows"]) for s in result["sheets"])
        case_rows += count
        if result["status"] != "ok":
            unreadable += 1
        files.append(
            {
                "path": str(path),
                "name": path.name,
                "ticket": ticket_of(path, ticket_re),
                "status": result["status"],
                "reason": result.get("reason", ""),
                "case_rows": count,
                "sheets": result["sheets"],
            }
        )

    report = {
        "source": ", ".join(str(Path(t).expanduser()) for t in args.targets),
        "run_metadata_fields": list(RUN_METADATA_FIELDS),
        "totals": {"files": len(files), "case_rows": case_rows, "unreadable": unreadable},
        "files": files,
    }

    if args.json_out:
        out = Path(args.json_out).expanduser()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"wrote {out}", file=sys.stderr)
    if args.format == "md":
        dump_markdown(report)
    sys.exit(1 if unreadable else 0)


if __name__ == "__main__":
    main()
