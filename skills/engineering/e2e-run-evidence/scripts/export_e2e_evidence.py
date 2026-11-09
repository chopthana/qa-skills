#!/usr/bin/env python3
"""Export Playwright JSON results to a preserved OOXML workbook and self-contained WebM HTML."""
from __future__ import annotations

import argparse
import base64
import html
import json
import posixpath
import re
import sys
import shutil
import tempfile
import zipfile
from pathlib import Path
from urllib.parse import quote
import xml.etree.ElementTree as ET

SHEET_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
DOC_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
DRAW_NS = "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
SHEET_REL = f"{DOC_REL_NS}/worksheet"
DRAW_REL = f"{DOC_REL_NS}/drawing"
IMAGE_REL = f"{DOC_REL_NS}/image"
SHEET_CT = "application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"
DRAW_CT = "application/vnd.openxmlformats-officedocument.drawing+xml"
EMU = 9525

# `<CASE-ID>-<kind>`: the input file a case reads, attached before its result
# (utils.showWorkbook writes `-excel`; any other file uses its type or `-input`).
# A picture is embedded as is; a text file (CSV, TXT, JSON or a raw body) is
# drawn into one first. Both go in the case's Image cell, above the result.
INPUT_KINDS = ("excel", "csv", "tsv", "txt", "text", "json", "input", "file")
IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg")
# Fonts with Thai glyphs, tried in order; E2E_EVIDENCE_FONT overrides.
TEXT_FONTS = (
    "/System/Library/Fonts/Supplemental/Tahoma.ttf",
    "/System/Library/Fonts/Thonburi.ttc",
    "C:/Windows/Fonts/tahoma.ttf",
    "C:/Windows/Fonts/leelawad.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansThai-Regular.ttf",
    "/usr/share/fonts/truetype/tlwg/Garuda.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
)


def register_namespaces() -> None:
    """Pin the prefixes of the XML this script writes. Importing openpyxl
    afterwards re-registers SpreadsheetML as `s:`, so this runs again right
    before a part is serialised."""
    ET.register_namespace("", SHEET_NS)
    ET.register_namespace("r", DOC_REL_NS)
    ET.register_namespace("xdr", DRAW_NS)
    ET.register_namespace("a", A_NS)
    ET.register_namespace("rel", PKG_REL_NS)
    ET.register_namespace("ct", CT_NS)


register_namespaces()


def xml_bytes(root: ET.Element) -> bytes:
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def validate_ignorable_prefixes(workbook_xml: str) -> None:
    match = re.search(r"<([\w.-]+:)?workbook\b[^>]*>", workbook_xml, re.S)
    if match is None:
        raise ValueError("xl/workbook.xml has no workbook root")
    root = match.group(0)
    declared = set(re.findall(r"xmlns:([\w.-]+)=", root)) | set(
        re.findall(r"xmlns=\"([^\"]+)\"", root)
    )
    for value in re.findall(r"(?:^|\s)(?:[\w.-]+:)?Ignorable=\"([^\"]*)\"", root):
        missing = set(value.split()) - declared
        if missing:
            raise ValueError(f"xl/workbook.xml has undeclared Ignorable prefixes: {sorted(missing)}")


def column_index(name: str) -> int:
    index = 0
    for char in name:
        index = index * 26 + ord(char) - 64
    return index


def column_name(index: int) -> str:
    result = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result
    return result


def case_ids(text: str, prefix: str) -> list[str]:
    match = re.search(rf"(?<![A-Z0-9]){re.escape(prefix)}-(\d+)(?![A-Z0-9])", text or "")
    if not match:
        return []
    # A title that names a RANGE of cases carries no single case ID. Ranges are
    # written with an en/em dash, `..`/`…`, `to`, or `- <n>` (a spaced ASCII
    # hyphen). A BARE `-<n>` straight after the ID is a per-screen suffix, not a
    # range: a suite that reads several screens for one case titles a held
    # bullet `<ID>-<screen>: HELD (drift)` and its reading steps `<ID>-<screen>`,
    # where `<screen>` is a longer code than the case number.
    # Only treat `-<n>` as a range when
    # the number is not longer than the ID it follows (an increment like
    # `-001-005`), so the held case keeps its own ID and its drift reason.
    tail = (text or "")[match.end():]
    if re.match(r"\s*(?:\.{2,}|…|–|—|to\b)", tail, re.I):
        return []
    hyphen_range = re.match(r"\s*-\s*(\d+)", tail)
    if hyphen_range and len(hyphen_range.group(1)) <= len(match.group(1)):
        return []
    result = [f"{prefix}-{match.group(1)}"]
    suffix = re.compile(r"\s*(?:\+|/\s*-?)\s*(\d+)(?![A-Z0-9])")
    cursor = match.end()
    while group := suffix.match(text, cursor):
        result.append(f"{prefix}-{group.group(1)}")
        cursor = group.end()
    return result


def read_cases(source: Path, sheet_name: str, first_row: int, id_col: str,
               topic_col: str, prefix: str, expected_col: str | None = None) -> list[dict]:
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        import openpyxl
        workbook = openpyxl.load_workbook(source, read_only=True, data_only=False)
    try:
        if sheet_name not in workbook.sheetnames:
            raise SystemExit(f"worksheet {sheet_name!r} missing; found {workbook.sheetnames}")
        sheet = workbook[sheet_name]
        valid_id = re.compile(rf"{re.escape(prefix)}-\d+")
        cases, seen = [], set()
        for row in range(first_row, sheet.max_row + 1):
            value = sheet[f"{id_col}{row}"].value
            if not isinstance(value, str) or not valid_id.fullmatch(value.strip()):
                continue
            case_id = value.strip()
            if case_id in seen:
                raise SystemExit(f"duplicate case ID at {sheet_name}!{id_col}{row}: {case_id}")
            seen.add(case_id)
            expected = sheet[f"{expected_col}{row}"].value if expected_col else ""
            cases.append({"id": case_id, "row": row,
                          "topic": str(sheet[f"{topic_col}{row}"].value or "").strip(),
                          "expected": str(expected or "").replace("\r\n", "\n").strip()})
        return cases
    finally:
        workbook.close()


def conflict_notes(test: dict) -> list[str]:
    """Why a test holds a case bullet: its `drift` annotations.

    A spec holds a bullet the app cannot satisfy as `test.fixme(title,
    { annotation: { type: 'drift', description } }, …)`; the description is the
    reviewer-facing reason (expected, actual, why, who rules)."""
    annotations = [*test.get("annotations", []),
                   *(a for result in test.get("results", []) for a in result.get("annotations", []))]
    drift = [a["description"].strip() for a in annotations
             if a.get("type") == "drift" and (a.get("description") or "").strip()]
    return list(dict.fromkeys(drift))


def result_map(report_path: Path, prefix: str) -> dict[str, dict]:
    data = json.loads(report_path.read_text(encoding="utf-8"))
    rank = {"Skipped": 0, "Passed": 1, "Failed": 2}
    status_names = {"passed": "Passed", "expected": "Passed", "failed": "Failed",
                    "timedOut": "Failed", "interrupted": "Failed", "skipped": "Skipped"}
    results: dict[str, dict] = {}
    forced_skip: set[str] = set()

    def record(case_id: str, status: str, attachments: list[dict], reasons: list[str] | None = None) -> None:
        row = results.setdefault(case_id, {"status": "Not run", "rank": -1, "image": None, "video": None,
                                           "reasons": [], "inputs": []})
        if rank[status] > row["rank"]:
            row["status"], row["rank"] = status, rank[status]
        for reason in reasons or []:
            if reason and reason not in row["reasons"]:
                row["reasons"].append(reason)
        exact = re.compile(rf"{re.escape(case_id)}(?!\d)")
        any_case = re.compile(rf"{re.escape(prefix)}-\d+(?!\d)")
        input_name = re.compile(rf"{re.escape(case_id)}-(?:{'|'.join(INPUT_KINDS)})")
        pngs, videos = [], []
        for attachment in attachments:
            path = attachment.get("path")
            label = f"{attachment.get('name', '')} {path or ''}"
            # The input file (a picture of it, or the file itself), possibly an inline body.
            if input_name.fullmatch(attachment.get("name", "")):
                key = (attachment.get("name"), path, attachment.get("body"))
                if key not in {(a.get("name"), a.get("path"), a.get("body")) for a in row["inputs"]}:
                    row["inputs"].append(attachment)
                continue
            if not path:
                continue
            if path.lower().endswith(".png") and any_case.search(label):
                pngs.append(path)
                if exact.search(label):
                    row["image"] = path
            elif path.lower().endswith(".webm"):
                videos.append(path)
        if row["image"] is None and pngs:
            row["image"] = pngs[-1]
        if videos:
            row["video"] = videos[-1]

    notes: dict[str, list[str]] = {}

    def visit(suite: dict) -> None:
        for spec in suite.get("specs", []):
            for test in spec.get("tests", []):
                title = test.get("title") or spec.get("title", "")
                test_ids = case_ids(title, prefix)
                for note in conflict_notes(test):
                    for case_id in test_ids:
                        if note not in notes.setdefault(case_id, []):
                            notes[case_id].append(note)
                for result in test.get("results", []):
                    attachments = result.get("attachments", [])
                    parent_status = status_names.get(result.get("status"), "Skipped")
                    steps: list[dict] = []
                    def visit_steps(items: list[dict]) -> None:
                        for step in items or []:
                            steps.append(step)
                            visit_steps(step.get("steps", []))
                    visit_steps(result.get("steps", []))
                    outcomes: dict[str, list[str]] = {}
                    step_reasons: dict[str, list[str]] = {}
                    for step in steps:
                        for case_id in case_ids(step.get("title", ""), prefix):
                            outcomes.setdefault(case_id, []).append("Failed" if step.get("error") else "Passed")
                            if step.get("error"):
                                step_reasons.setdefault(case_id, []).append(error_reason(step["error"]))
                    # Why a test failed from outside its titled steps: its own errors.
                    test_errors = [error_reason(e) for e in result.get("errors") or ([result["error"]] if result.get("error") else [])]
                    skipped = set()
                    skip_notes: dict[str, str] = {}
                    test_skip_note = ""
                    for annotation in [*test.get("annotations", []), *result.get("annotations", [])]:
                        kind, description = annotation.get("type", ""), annotation.get("description", "") or ""
                        if kind in ("skip", "fixme") or "not tested" in kind.lower():
                            # A skip/fixme/"NOT TESTED" note belongs to the test's own case(s).
                            label = {"fixme": "test.fixme", "skip": "test.skip"}.get(kind, kind)
                            test_skip_note = f"{label}: {description}".strip(": ") if description else label
                        if kind != "skip-shape":
                            continue
                        ids = case_ids(description, prefix)
                        if not ids and (match := re.match(r"\s*(\d{2,3})(?!\d)", description)):
                            ids = [f"{prefix}-{match.group(1)}"]
                        skipped.update(ids)
                        for case_id in ids:
                            skip_notes[case_id] = description
                    forced_skip.update(skipped)
                    # A test that did not run (skipped / fixme) explains itself.
                    parent_note = [test_skip_note] if parent_status == "Skipped" and test_skip_note else []
                    for case_id in test_ids:
                        if case_id not in outcomes:
                            note = [skip_notes[case_id]] if case_id in skip_notes else parent_note
                            reasons = test_errors if parent_status == "Failed" else note
                            record(case_id, "Skipped" if case_id in skipped else parent_status, attachments, reasons)
                    for case_id, statuses in outcomes.items():
                        # A test that is this one case also fails it from outside
                        # its titled steps (an assertion between them); a grouped
                        # test keeps per-step outcomes so one case's failure does
                        # not fail its siblings.
                        reasons = list(step_reasons.get(case_id, []))
                        if test_ids == [case_id] and parent_status != "Skipped":
                            statuses = [*statuses, parent_status]
                            if parent_status == "Failed":
                                reasons += test_errors
                        record(case_id, "Skipped" if case_id in skipped else max(statuses, key=rank.__getitem__), attachments,
                               [skip_notes[case_id]] if case_id in skip_notes else reasons)
                    for case_id in skipped - set(test_ids) - set(outcomes):
                        record(case_id, "Skipped", attachments, [skip_notes.get(case_id, "")])
        for child in suite.get("suites", []):
            visit(child)

    for suite in data.get("suites", []):
        visit(suite)
    for case_id in forced_skip:
        results.setdefault(case_id, {"status": "Skipped", "rank": 0, "image": None, "video": None,
                                     "reasons": [], "inputs": []})
        results[case_id]["status"] = "Skipped"
    for case_id, case_notes in notes.items():
        results.setdefault(case_id, {"status": "Not run", "image": None, "video": None, "reasons": [], "inputs": []})
        results[case_id]["notes"] = case_notes
    for row in results.values():
        row.pop("rank", None)
    return results


ANSI = re.compile(r"\x1b\[[0-9;]*m")


def error_reason(error: dict | str, limit: int = 700) -> str:
    """A Playwright error as a short reason a reviewer can read in a cell: the
    assertion's own message, expected/received lines, no ANSI, no call log."""
    text = error if isinstance(error, str) else (error.get("message") or error.get("value") or "")
    lines = []
    for line in ANSI.sub("", text).replace("\r", "").split("\n"):
        line = line.strip()
        if re.match(r"(Call log|Locator:|Timeout:|at\s|\d+\s*\||>\s*\d+\s*\|)", line, re.I):
            if line.lower().startswith("call log"):
                break
            continue
        if line:
            lines.append(line)
    reason = "\n".join(lines)
    return reason if len(reason) <= limit else reason[: limit - 1].rstrip() + "…"


def display_status(status: str, notes: list[str] | tuple = ()) -> str:
    """The case workbook's own status for one case: `Passed` or `Not pass`.

    `Passed` requires a clean pass — the run passed AND no bullet is held. A
    held bullet is the app contradicting the case (a drift `test.fixme`), so
    the case cannot be confirmed and it is `Not pass`. Everything the run did
    not pass is also `Not pass`, because "could not be tested" is not a pass:
    a failure (`Failed`), a skip/`test.fixme`, or a case no test in this run
    carries. `Waiting to test` is never emitted."""
    return "Passed" if status == "Passed" and not notes else "Not pass"


def display_reason(status: str, reasons: list[str], notes: list[str] | tuple = ()) -> str:
    """Why a case is `Not pass`: the held bullet's drift reason (why the app
    contradicts the case), the failure, or why it could not be tested."""
    if display_status(status, notes) == "Passed":
        return ""
    if notes:
        reasons = [*notes, *(r for r in reasons if r not in notes and r != "test.fixme")]
    if reasons:
        return "\n".join(reasons)
    if status == "Failed":
        return "The test failed (no error message in the report)."
    if status == "Skipped":
        return "The automated test was skipped (no reason in the report)."
    return "Not automated: no test in this run carries this case ID."


def text_font(size: int):
    """A TrueType font with Thai glyphs (E2E_EVIDENCE_FONT first), else Pillow's own."""
    import os
    from PIL import ImageFont
    for candidate in (os.environ.get("E2E_EVIDENCE_FONT"), *TEXT_FONTS):
        if candidate and Path(candidate).is_file():
            try:
                return ImageFont.truetype(candidate, size)
            except OSError:
                continue
    print("warning: no Thai-capable font found; set E2E_EVIDENCE_FONT", file=sys.stderr)
    return ImageFont.load_default(size=size)


def render_text(title: str, text: str, output: Path, max_lines: int = 40, max_chars: int = 140) -> Path:
    """Draw a text input (CSV, TXT, JSON, a raw body) the way an editor shows it:
    a title bar with the file name, line numbers, the first `max_lines` lines."""
    from PIL import Image, ImageDraw
    font, small = text_font(18), text_font(15)
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    shown = [line.replace("\t", "    ")[:max_chars] for line in lines[:max_lines]] or [""]
    if len(lines) > max_lines:
        shown.append(f"… อีก {len(lines) - max_lines} บรรทัด")
    probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    gutter = 16 + round(probe.textlength(str(len(shown)), font=small))
    line_h, pad, bar = 28, 14, 40
    width = max(640, min(1280, gutter + 2 * pad + max(round(probe.textlength(s, font=font)) for s in shown)))
    height = bar + 2 * pad + line_h * len(shown)
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, width, bar), fill="#3a3a3a")
    draw.text((pad, 10), f"{title} — ไฟล์ที่อัปโหลด", font=font, fill="white")
    draw.rectangle((0, bar, gutter + 6, height), fill="#f1f1f1")
    for i, line in enumerate(shown):
        y = bar + pad + i * line_h
        draw.text((gutter - 4, y + 2), str(i + 1), font=small, fill="#888888", anchor="ra")
        draw.text((gutter + 6 + pad, y), line, font=font, fill="#1f1f1f")
    image.save(output)
    return output


def input_picture(attachment: dict, report: Path, video_root: Path, workdir: Path) -> Path | None:
    """The input attachment as a picture: an image as is, text drawn by render_text."""
    name = attachment.get("name") or "input"
    path = find_artifact(attachment.get("path"), report, video_root) if attachment.get("path") else None
    if path is not None and path.suffix.lower() in IMAGE_SUFFIXES:
        return path
    if path is not None and path.suffix.lower() in (".xlsx", ".xlsm", ".xls"):
        print(f"warning: {name} is a workbook, not a picture of it; "
              "capture it with utils.showWorkbook instead", file=sys.stderr)
        return None
    if path is not None:
        raw, title = path.read_bytes(), path.name
    elif attachment.get("body"):
        raw, title = base64.b64decode(attachment["body"]), name
    else:
        return None
    for encoding in ("utf-8-sig", "cp874", "latin-1"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    safe = re.sub(r"[^\w.-]+", "_", name)
    return render_text(title, text, workdir / f"{safe}.png")


def merged_results(reports: list[Path], prefix: str) -> dict[str, dict]:
    """result_map over several reports (separate runs, e.g. one per seeded suite).

    A case takes its result from the last report that ran it; a report that
    skipped it (its suite was not seeded there) or never saw it does not
    override one that did. Conflict notes are pooled. Each result keeps the
    report it came from, so its artifacts resolve against that report."""
    weight = {"Not run": 0, "Skipped": 1, "Passed": 2, "Failed": 2}
    merged: dict[str, dict] = {}
    for report in reports:
        for case_id, row in result_map(report, prefix).items():
            current = merged.get(case_id)
            notes = list(dict.fromkeys([*(current or {}).get("notes", []), *row.get("notes", [])]))
            if current is None or weight[row["status"]] >= weight[current["status"]]:
                merged[case_id] = {**row, "report": report}
            merged[case_id]["notes"] = notes
    return merged


def find_artifact(value: str | None, report: Path, video_root: Path) -> Path | None:
    if not value:
        return None
    candidate = Path(value).expanduser()
    possibilities = [candidate] if candidate.is_absolute() else [Path.cwd() / candidate, report.parent / candidate, video_root / candidate]
    for path in possibilities:
        if path.is_file():
            return path.resolve()
    print(f"warning: report artifact unavailable: {value}", file=sys.stderr)
    return None


def next_number(names: list[str], pattern: str) -> int:
    found = [int(match.group(1)) for name in names if (match := re.fullmatch(pattern, name))]
    return max(found, default=0) + 1


HEADERS = ("ID", "Topic", "Expected result", "Status", "Reason", "Image")
COLUMN_WIDTHS = (30, 50, 55, 16, 55, 68)
IMAGE_COL = HEADERS.index("Image")  # zero-based column the screenshot is anchored to


def add_alignment_styles(parts: dict[str, bytes]) -> tuple[int, int]:
    """Append the two cell formats the sheet uses to xl/styles.xml and return
    their indexes: top-left wrapped (ID, Topic, Expected result, Reason) and
    centred (Status)."""
    styles = parts["xl/styles.xml"].decode("utf-8")
    match = re.search(r"<cellXfs\b[^>]*\bcount=\"(\d+)\"[^>]*>", styles)
    if match is None or "</cellXfs>" not in styles:
        raise SystemExit("xl/styles.xml has no <cellXfs> to add the cell alignments to")
    count = int(match.group(1))
    top_left = (f'<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1">'
                f'<alignment horizontal="left" vertical="top" wrapText="1"/></xf>')
    centre = (f'<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1">'
              f'<alignment horizontal="center" vertical="center" wrapText="1"/></xf>')
    styles = styles.replace(match.group(0), match.group(0).replace(f'count="{count}"', f'count="{count + 2}"'), 1)
    styles = styles.replace("</cellXfs>", top_left + centre + "</cellXfs>", 1)
    parts["xl/styles.xml"] = styles.encode("utf-8")
    return count, count + 1


def row_height(has_image: bool, *texts: str) -> int:
    """Tall enough for the screenshot and for the longest wrapped text cell."""
    lines = max((sum(max(1, -(-len(line) // 38)) for line in (text or "").split("\n")) for text in texts), default=1)
    return min(409, max(205 if has_image else 30, 15 * lines + 6))


def set_or_insert_cell(row_xml: str, ref: str, text: str, prefix: str, style_from: str) -> str:
    """Set a cell that may not exist in the row yet (an empty column a sheet never
    wrote). A new cell takes the style of `style_from`'s cell in the same row, so
    it carries the neighbouring cells' borders, and goes in column order."""
    p = re.escape(prefix)
    if re.search(rf'<{p}c\b[^>]*\br="{ref}"', row_xml):
        return set_cell(row_xml, ref, text, prefix)
    style = re.search(rf'<{p}c\b[^>]*\br="{style_from}"[^>]*?\bs="(\d+)"', row_xml)
    style_attr = f' s="{style.group(1)}"' if style else ""
    cell = (f'<{prefix}c r="{ref}"{style_attr} t="inlineStr"><{prefix}is><{prefix}t xml:space="preserve">'
            f"{html.escape(text, quote=False)}</{prefix}t></{prefix}is></{prefix}c>")
    wanted = column_index(re.match(r"[A-Z]+", ref).group(0))
    for later in re.finditer(rf'<{p}c\b[^>]*\br="([A-Z]+)\d+"', row_xml):
        if column_index(later.group(1)) > wanted:
            return row_xml[:later.start()] + cell + row_xml[later.start():]
    closing = f"</{prefix}row>"
    return row_xml[: row_xml.rindex(closing)] + cell + closing


def sync_test_result(parts: dict[str, bytes], sheet_name: str, status_col: str,
                     updates: list[dict], pass_label: str,
                     tester: str | None = None, tester_col: str = "H",
                     fail_label: str = "Not pass", date_col: str | None = None,
                     test_date: str | None = None) -> dict[str, bytes]:
    """Put the automated outcome on the case's own row of the source sheet:
    `Passed` -> the workbook's pass label, otherwise `Not pass` -> the fail
    label, with the tester's name in the Tester column and the run date in the
    Test date column. Every case that got an outcome is stamped; there is no
    `Waiting to test` and no held-case exception, because a case that could not
    be confirmed is itself a `Not pass`. Only those cells change."""
    sheet_part = sheet_part_for(parts, sheet_name)
    sheet = parts[sheet_part].decode("utf-8")
    prefix = sheet_prefix(sheet)
    p = re.escape(prefix)
    for update in updates:
        shown = display_status(update["status"], update.get("notes", []))
        number = update["row"]
        match = re.search(rf'<{p}row\b[^>]*\br="{number}"[^>]*>.*?</{p}row>', sheet, re.S)
        if match is None:
            raise SystemExit(f"row {number} ({update['id']}) not found in {sheet_part}")
        row_xml = set_cell(match.group(0), f"{status_col}{number}", pass_label if shown == "Passed" else fail_label, prefix)
        if tester:
            row_xml = set_or_insert_cell(row_xml, f"{tester_col}{number}", tester, prefix, f"{status_col}{number}")
        if date_col and test_date:
            row_xml = set_or_insert_cell(row_xml, f"{date_col}{number}", test_date, prefix, f"{status_col}{number}")
        sheet = sheet[:match.start()] + row_xml + sheet[match.end():]
    parts[sheet_part] = sheet.encode("utf-8")
    return parts


def add_sheet(parts: dict[str, bytes], source_infos: dict[str, zipfile.ZipInfo],
              sheet_name: str, rows: list[dict]) -> dict[str, bytes]:
    register_namespaces()
    workbook_xml = parts["xl/workbook.xml"].decode("utf-8")
    validate_ignorable_prefixes(workbook_xml)
    if re.search(rf'<sheet\b[^>]*\bname="{re.escape(sheet_name)}"', workbook_xml):
        raise SystemExit(f"source already contains worksheet {sheet_name!r}")
    names = list(parts)
    sheet_no = next_number(names, r"xl/worksheets/sheet(\d+)\.xml")
    drawing_no = next_number(names, r"xl/drawings/drawing(\d+)\.xml")
    image_no = next_number(names, r"xl/media/image(\d+)\.[A-Za-z0-9]+")
    sheet_part = f"xl/worksheets/sheet{sheet_no}.xml"
    drawing_part = f"xl/drawings/drawing{drawing_no}.xml"
    rels_part = f"xl/worksheets/_rels/sheet{sheet_no}.xml.rels"
    top_left, centre = add_alignment_styles(parts)
    values = [HEADERS] + [(r["id"], r["topic"], r["expected"], display_status(r["status"], r.get("notes", [])),
                           display_reason(r["status"], r["reasons"], r.get("notes", [])),
                           "" if r["image"] else "No screenshot captured") for r in rows]
    styles_of = (top_left, top_left, top_left, centre, top_left, top_left)
    last = column_name(len(HEADERS))
    root = ET.Element(f"{{{SHEET_NS}}}worksheet", {f"{{{DOC_REL_NS}}}dummy": ""})
    root.attrib.pop(f"{{{DOC_REL_NS}}}dummy")
    ET.SubElement(root, f"{{{SHEET_NS}}}dimension", {"ref": f"A1:{last}{len(values)}"})
    views = ET.SubElement(root, f"{{{SHEET_NS}}}sheetViews")
    view = ET.SubElement(views, f"{{{SHEET_NS}}}sheetView", {"workbookViewId": "0"})
    ET.SubElement(view, f"{{{SHEET_NS}}}pane", {"ySplit": "1", "topLeftCell": "A2", "activePane": "bottomLeft", "state": "frozen"})
    ET.SubElement(view, f"{{{SHEET_NS}}}selection", {"pane": "bottomLeft", "activeCell": "A2", "sqref": "A2"})
    ET.SubElement(root, f"{{{SHEET_NS}}}sheetFormatPr", {"defaultRowHeight": "15"})
    cols = ET.SubElement(root, f"{{{SHEET_NS}}}cols")
    for i, width in enumerate(COLUMN_WIDTHS, 1):
        ET.SubElement(cols, f"{{{SHEET_NS}}}col", {"min": str(i), "max": str(i), "width": str(width), "customWidth": "1"})
    sheet_data = ET.SubElement(root, f"{{{SHEET_NS}}}sheetData")
    drawing = ET.Element(f"{{{DRAW_NS}}}wsDr")
    drawing_rels = ET.Element(f"{{{PKG_REL_NS}}}Relationships")
    def place(image: Path, rno: int, rel_id: str, pic_id: int, name: str,
              box_height: int = 270, y_offset: int = 0) -> int:
        """Anchor `image` in the row's Image cell, `y_offset` px below its top; its height in px."""
        nonlocal image_no
        from PIL import Image
        media_name = f"xl/media/image{image_no}.{image.suffix.lstrip('.')}"
        parts[media_name] = image.read_bytes()
        with Image.open(image) as opened:
            width, height = opened.size
        scale = min(480 / width, box_height / height, 1)
        width, height = round(width * scale), round(height * scale)
        ext = {"cx": str(width * EMU), "cy": str(height * EMU)}
        anchor = ET.SubElement(drawing, f"{{{DRAW_NS}}}oneCellAnchor")
        start = ET.SubElement(anchor, f"{{{DRAW_NS}}}from")
        for tag, val in (("col", str(IMAGE_COL)), ("colOff", "0"), ("row", str(rno - 1)), ("rowOff", str(y_offset * EMU))):
            ET.SubElement(start, f"{{{DRAW_NS}}}{tag}").text = val
        ET.SubElement(anchor, f"{{{DRAW_NS}}}ext", ext)
        pic = ET.SubElement(anchor, f"{{{DRAW_NS}}}pic")
        nonvisual = ET.SubElement(pic, f"{{{DRAW_NS}}}nvPicPr")
        ET.SubElement(nonvisual, f"{{{DRAW_NS}}}cNvPr", {"id": str(pic_id), "name": name})
        pic_props = ET.SubElement(nonvisual, f"{{{DRAW_NS}}}cNvPicPr")
        ET.SubElement(pic_props, f"{{{A_NS}}}picLocks", {"noChangeAspect": "1"})
        fill = ET.SubElement(pic, f"{{{DRAW_NS}}}blipFill")
        ET.SubElement(fill, f"{{{A_NS}}}blip", {f"{{{DOC_REL_NS}}}embed": rel_id})
        stretch = ET.SubElement(fill, f"{{{A_NS}}}stretch")
        ET.SubElement(stretch, f"{{{A_NS}}}fillRect")
        shape = ET.SubElement(pic, f"{{{DRAW_NS}}}spPr")
        transform = ET.SubElement(shape, f"{{{A_NS}}}xfrm")
        ET.SubElement(transform, f"{{{A_NS}}}off", {"x": "0", "y": "0"})
        ET.SubElement(transform, f"{{{A_NS}}}ext", ext)
        geometry = ET.SubElement(shape, f"{{{A_NS}}}prstGeom", {"prst": "rect"})
        ET.SubElement(geometry, f"{{{A_NS}}}avLst")
        ET.SubElement(anchor, f"{{{DRAW_NS}}}clientData")
        ET.SubElement(drawing_rels, f"{{{PKG_REL_NS}}}Relationship", {"Id": rel_id, "Type": IMAGE_REL, "Target": f"../media/image{image_no}.{image.suffix.lstrip('.')}"})
        image_no += 1
        return height

    # The Image cell stacks a case's pictures top to bottom: its input files
    # first (what went in), the result frame last (what came out), within
    # 540 px so the row stays under Excel's 409 pt limit.
    gap, column_px = 8, 540
    for rno, row_values in enumerate(values, 1):
        record = rows[rno - 2] if rno > 1 else None
        pictures = [p for p in (record.get("pictures") or [record["image"]]) if p] if record else []
        stacked = 0
        if pictures:
            box = min(270, (column_px - gap * (len(pictures) - 1)) // len(pictures))
            for k, picture in enumerate(pictures):
                stacked += place(picture, rno, f"rId{rno}" if k == 0 else f"rId{rno}_{k}", rno * 100 + k,
                                 record["id"] if picture == record["image"] else f"{record['id']}-input",
                                 box, stacked + gap * k)
            stacked += gap * (len(pictures) - 1)
        if rno == 1:
            height = "24"
        else:
            text_pt = row_height(False, row_values[2], row_values[4])
            height = str(min(409, max(text_pt, round(stacked * 0.75) + 4 if pictures else 0)))
        row = ET.SubElement(sheet_data, f"{{{SHEET_NS}}}row", {"r": str(rno), "ht": height, "customHeight": "1"})
        for col, value in enumerate(row_values, 1):
            attrs = {"r": f"{column_name(col)}{rno}", "t": "inlineStr"}
            if rno > 1:
                attrs["s"] = str(styles_of[col - 1])
            cell = ET.SubElement(row, f"{{{SHEET_NS}}}c", attrs)
            inline = ET.SubElement(cell, f"{{{SHEET_NS}}}is")
            ET.SubElement(inline, f"{{{SHEET_NS}}}t", {"{http://www.w3.org/XML/1998/namespace}space": "preserve"}).text = value
    ET.SubElement(root, f"{{{SHEET_NS}}}autoFilter", {"ref": f"A1:{last}{len(values)}"})
    if len(drawing):
        parts[drawing_part] = xml_bytes(drawing)
        parts[f"xl/drawings/_rels/drawing{drawing_no}.xml.rels"] = xml_bytes(drawing_rels)
        ET.SubElement(root, f"{{{SHEET_NS}}}drawing", {f"{{{DOC_REL_NS}}}id": "rId1"})
        sheet_rel = ET.Element(f"{{{PKG_REL_NS}}}Relationships")
        ET.SubElement(sheet_rel, f"{{{PKG_REL_NS}}}Relationship", {"Id": "rId1", "Type": DRAW_REL, "Target": f"../drawings/drawing{drawing_no}.xml"})
        parts[rels_part] = xml_bytes(sheet_rel)
    parts[sheet_part] = xml_bytes(root)
    rels_xml = parts["xl/_rels/workbook.xml.rels"].decode("utf-8")
    rel_ids = [int(match.group(1)) for match in re.finditer(r'Id="rId(\d+)"', rels_xml)]
    rid = f"rId{max(rel_ids, default=0) + 1}"
    relationship = (
        f'<Relationship Id="{rid}" Type="{SHEET_REL}" '
        f'Target="worksheets/sheet{sheet_no}.xml"/>'
    )
    parts["xl/_rels/workbook.xml.rels"] = rels_xml.replace(
        "</Relationships>", relationship + "</Relationships>", 1
    ).encode()

    sheet_ids = [int(match.group(1)) for match in re.finditer(r'sheetId="(\d+)"', workbook_xml)]
    sheet_id = max(sheet_ids, default=0) + 1
    sheet_entry = (
        f'<sheet name="{sheet_name}" sheetId="{sheet_id}" '
        f'r:id="{rid}"/>'
    )
    parts["xl/workbook.xml"] = workbook_xml.replace(
        "</sheets>", sheet_entry + "</sheets>", 1
    ).encode()

    content_types_xml = parts["[Content_Types].xml"].decode("utf-8")
    overrides = f'<Override PartName="/{sheet_part}" ContentType="{SHEET_CT}"/>'
    if len(drawing):
        overrides += f'<Override PartName="/{drawing_part}" ContentType="{DRAW_CT}"/>'
    # A part with no content type makes Excel offer to "repair" the workbook:
    # the source may declare only the image types it already holds (jpeg).
    for suffix in sorted({p.suffix.lstrip(".").lower() for r in rows
                          for p in (r.get("pictures") or [r["image"]]) if p}):
        if not re.search(rf'<Default\b[^>]*Extension="{suffix}"', content_types_xml, re.I):
            overrides = f'<Default Extension="{suffix}" ContentType="image/{suffix}"/>' + overrides
    parts["[Content_Types].xml"] = content_types_xml.replace(
        "</Types>", overrides + "</Types>", 1
    ).encode()
    return parts


def read_parts(source: Path) -> tuple[dict[str, bytes], dict[str, zipfile.ZipInfo]]:
    with zipfile.ZipFile(source) as archive:
        parts = {name: archive.read(name) for name in archive.namelist()}
        infos = {info.filename: info for info in archive.infolist()}
    return parts, infos


def write_xlsx(source: Path, output: Path, sheet_name: str, rows: list[dict],
               source_sheet: str, status_col: str, pass_label: str,
               tester: str | None, tester_col: str, fail_label: str = "Not pass",
               date_col: str | None = None, test_date: str | None = None) -> None:
    parts, infos = read_parts(source)
    parts = add_sheet(parts, infos, sheet_name, rows)
    parts = sync_test_result(parts, source_sheet, status_col, rows, pass_label, tester, tester_col,
                             fail_label, date_col, test_date)
    write_parts(output, parts, infos)


def write_parts(output: Path, parts: dict[str, bytes], infos: dict[str, zipfile.ZipInfo]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = output.with_suffix(".tmp.xlsx")
    with zipfile.ZipFile(temp, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in parts.items():
            if name in infos:
                archive.writestr(infos[name], data)
            else:
                archive.writestr(name, data)
    shutil.move(temp, output)


def part_target(parts: dict[str, bytes], rels_part: str, rel_type: str, rel_id: str | None = None) -> str | None:
    """The package path a relationship points to, resolved against its rels part."""
    if rels_part not in parts:
        return None
    # A rels part may prefix its tags (`<rel:Relationship>`), as this
    # script's own ElementTree output does until Excel re-saves it.
    for match in re.finditer(r"<(?:[\w.-]+:)?Relationship\b[^>]*>", parts[rels_part].decode("utf-8")):
        tag = match.group(0)
        if f'Type="{rel_type}"' not in tag or (rel_id and f'Id="{rel_id}"' not in tag):
            continue
        target = re.search(r'Target="([^"]+)"', tag).group(1)
        if target.startswith("/"):
            return target[1:]
        # X/_rels/Y.rels describes X/Y: targets are relative to X.
        return posixpath.normpath(posixpath.join(posixpath.dirname(posixpath.dirname(rels_part)), target))
    return None


def sheet_part_for(parts: dict[str, bytes], sheet_name: str) -> str:
    workbook_xml = parts["xl/workbook.xml"].decode("utf-8")
    entry = re.search(rf'<sheet\b[^>]*\bname="{re.escape(sheet_name)}"[^>]*/>', workbook_xml)
    if entry is None:
        raise SystemExit(f"--update needs an existing worksheet {sheet_name!r}")
    rel_id = re.search(r'\b[\w.-]+:id="([^"]+)"', entry.group(0)).group(1)
    target = part_target(parts, "xl/_rels/workbook.xml.rels", SHEET_REL, rel_id)
    if target is None or target not in parts:
        raise SystemExit(f"worksheet {sheet_name!r} has no part")
    return target


def read_recorded(source: Path, sheet_name: str, prefix: str) -> tuple[list[dict], dict[str, str]]:
    """Rows of an existing Automated sheet and the column letter of each of its
    headers. Both layouts are read: ID/Topic/Status/Image (first exports) and
    ID/Topic/Expected result/Status/Reason/Image."""
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        import openpyxl
        workbook = openpyxl.load_workbook(source, read_only=True, data_only=False)
    try:
        sheet = workbook[sheet_name]
        valid_id = re.compile(rf"{re.escape(prefix)}-\d+")
        rows, columns = [], {}
        for number, values in enumerate(sheet.iter_rows(min_row=1, values_only=True), 1):
            if number == 1:
                headers = [str(v) if v is not None else "" for v in values]
                columns = {h: column_name(i) for i, h in enumerate(headers, 1) if h}
                if not {"ID", "Topic", "Status", "Image"} <= set(columns):
                    raise SystemExit(f"{sheet_name!r} headers are {headers}, not ID/Topic/Status/Image")
                continue
            def cell(header: str) -> str:
                letter = columns.get(header)
                index = openpyxl.utils.column_index_from_string(letter) - 1 if letter else None
                return str(values[index] or "") if index is not None and index < len(values) else ""
            case_id = cell("ID").strip()
            if valid_id.fullmatch(case_id):
                rows.append({"id": case_id, "topic": cell("Topic"), "status": cell("Status"), "row": number})
        return rows, columns
    finally:
        workbook.close()


def sheet_prefix(sheet_xml: str) -> str:
    """The worksheet's SpreadsheetML prefix with its colon (`s:`), or '' when
    the namespace is the default one. Some writers prefix every tag."""
    match = re.search(r"<(?:([\w.-]+):)?worksheet\b", sheet_xml)
    return f"{match.group(1)}:" if match and match.group(1) else ""


def set_cell(row_xml: str, ref: str, text: str, prefix: str = "") -> str:
    """Replace one cell with an inline string, keeping its style."""
    p = re.escape(prefix)
    pattern = re.compile(rf'<{p}c\b(?P<attrs>[^>]*?\br="{ref}"[^>]*?)(?:/>|>.*?</{p}c>)', re.S)
    match = pattern.search(row_xml)
    if match is None:
        raise SystemExit(f"cell {ref} not found")
    style = re.search(r'\bs="(\d+)"', match.group("attrs"))
    style_attr = f' s="{style.group(1)}"' if style else ""
    x = prefix
    cell = (f'<{x}c r="{ref}"{style_attr} t="inlineStr"><{x}is><{x}t xml:space="preserve">'
            f"{html.escape(text, quote=False)}</{x}t></{x}is></{x}c>")
    return row_xml[:match.start()] + cell + row_xml[match.end():]


def update_sheet(parts: dict[str, bytes], sheet_name: str, updates: list[dict],
                 columns: dict[str, str]) -> dict[str, bytes]:
    """Fill rows of an existing Automated sheet in place and add their images
    to the sheet's drawing. Every other row, cell, image and part is untouched,
    including edits made in Excel/WPS after the sheet was first exported."""
    sheet_part = sheet_part_for(parts, sheet_name)
    sheet = parts[sheet_part].decode("utf-8")
    prefix = sheet_prefix(sheet)
    p = re.escape(prefix)
    for update in updates:
        number = update["row"]
        match = re.search(rf'<{p}row\b[^>]*\br="{number}"[^>]*>.*?</{p}row>', sheet, re.S)
        if match is None:
            raise SystemExit(f"row {number} ({update['id']}) not found in {sheet_part}")
        shown = display_status(update["status"], update.get("notes", []))
        reason = display_reason(update["status"], update["reasons"], update.get("notes", []))
        row_xml = set_cell(match.group(0), f"{columns['Status']}{number}", shown, prefix)
        if "Reason" in columns:
            row_xml = set_cell(row_xml, f"{columns['Reason']}{number}", reason, prefix)
        row_xml = set_cell(row_xml, f"{columns['Image']}{number}", "" if update["image"] else "No screenshot captured", prefix)
        height = str(row_height(bool(update["image"]), update.get("expected", ""), reason))
        open_tag = re.match(rf"<{p}row\b[^>]*>", row_xml).group(0)
        if "ht=" in open_tag:
            new_tag = re.sub(r'\bht="[^"]*"', f'ht="{height}"', open_tag)
        else:
            new_tag = open_tag[:-1] + f' ht="{height}" customHeight="1">'
        row_xml = new_tag + row_xml[len(open_tag):]
        sheet = sheet[:match.start()] + row_xml + sheet[match.end():]
    parts[sheet_part] = sheet.encode("utf-8")

    pictures = [u for u in updates if u["image"]]
    if not pictures:
        return parts
    # Part names are POSIX paths on every OS: Path would join with "\" on Windows.
    sheet_rels = f"{posixpath.dirname(sheet_part)}/_rels/{posixpath.basename(sheet_part)}.rels"
    drawing_part = part_target(parts, sheet_rels, DRAW_REL)
    if drawing_part is None or drawing_part not in parts:
        raise SystemExit(f"{sheet_name!r} has no drawing to add images to; regenerate it without --update")
    drawing = parts[drawing_part].decode("utf-8")
    xdr = re.search(r"<([\w.-]+):wsDr\b", drawing)
    xdr = xdr.group(1) if xdr else None
    def prefix_of(namespace: str) -> str:
        found = re.search(rf'xmlns:([\w.-]+)="{re.escape(namespace)}"', drawing)
        if found is None:
            raise SystemExit(f"{drawing_part} does not declare {namespace}")
        return found.group(1)
    if xdr is None:
        raise SystemExit(f"{drawing_part} has no prefixed wsDr root")
    a, r = prefix_of(A_NS), prefix_of(DOC_REL_NS)
    # Excel/WPS re-saves can declare the relationships prefix on each
    # <a:blip> instead of the root, where it is out of scope for an appended
    # anchor: declare it on the new blip too, or the drawing will not parse.
    root_tag = re.search(rf"<{re.escape(xdr)}:wsDr\b[^>]*>", drawing).group(0)
    blip_ns = "" if f'xmlns:{r}="{DOC_REL_NS}"' in root_tag else f' xmlns:{r}="{DOC_REL_NS}"'
    drawing_rels = f"{posixpath.dirname(drawing_part)}/_rels/{posixpath.basename(drawing_part)}.rels"
    rels_xml = parts.get(drawing_rels, f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="{PKG_REL_NS}"></Relationships>'.encode()).decode("utf-8")
    rels_root = re.search(r"<(?:([\w.-]+):)?Relationships\b", rels_xml)
    rel = f"{rels_root.group(1)}:" if rels_root and rels_root.group(1) else ""
    next_rel = max([int(n) for n in re.findall(r'Id="rId(\d+)"', rels_xml)], default=0) + 1
    next_id = max([int(n) for n in re.findall(r'cNvPr\b[^>]*\bid="(\d+)"', drawing)], default=1) + 1
    image_no = next_number(list(parts), r"xl/media/image(\d+)\.[A-Za-z0-9]+")
    anchors, relationships = [], []
    from PIL import Image
    for update in pictures:
        image = update["image"]
        suffix = image.suffix.lstrip(".").lower()
        media = f"xl/media/image{image_no}.{suffix}"
        parts[media] = image.read_bytes()
        with Image.open(image) as opened:
            width, height = opened.size
        scale = min(480 / width, 270 / height, 1)
        cx, cy = round(width * scale) * EMU, round(height * scale) * EMU
        rel_id = f"rId{next_rel}"
        relationships.append(f'<{rel}Relationship Id="{rel_id}" Type="{IMAGE_REL}" Target="../media/image{image_no}.{suffix}"/>')
        # Declare the three namespaces on the anchor itself: a workbook Excel or
        # WPS re-saved often carries its drawing namespaces on the individual
        # picture elements instead of the `wsDr` root, so a prefix resolved from
        # the document is not necessarily in scope here — an undeclared `r:embed`
        # makes the part unparseable (Excel offers to "repair" the file).
        anchors.append(
            f'<{xdr}:oneCellAnchor xmlns:{xdr}="{DRAW_NS}" xmlns:{a}="{A_NS}" xmlns:{r}="{DOC_REL_NS}">'
            f"<{xdr}:from><{xdr}:col>{column_index(columns['Image']) - 1}</{xdr}:col><{xdr}:colOff>0</{xdr}:colOff>"
            f"<{xdr}:row>{update['row'] - 1}</{xdr}:row><{xdr}:rowOff>0</{xdr}:rowOff></{xdr}:from>"
            f'<{xdr}:ext cx="{cx}" cy="{cy}"/><{xdr}:pic><{xdr}:nvPicPr>'
            f'<{xdr}:cNvPr id="{next_id}" name="{html.escape(update["id"], quote=True)}"/>'
            f'<{xdr}:cNvPicPr><{a}:picLocks noChangeAspect="1"/></{xdr}:cNvPicPr></{xdr}:nvPicPr>'
            f'<{xdr}:blipFill><{a}:blip{blip_ns} {r}:embed="{rel_id}"/><{a}:stretch><{a}:fillRect/></{a}:stretch></{xdr}:blipFill>'
            f'<{xdr}:spPr><{a}:xfrm><{a}:off x="0" y="0"/><{a}:ext cx="{cx}" cy="{cy}"/></{a}:xfrm>'
            f'<{a}:prstGeom prst="rect"><{a}:avLst/></{a}:prstGeom></{xdr}:spPr></{xdr}:pic>'
            f"<{xdr}:clientData/></{xdr}:oneCellAnchor>"
        )
        next_rel, next_id, image_no = next_rel + 1, next_id + 1, image_no + 1
    closing = f"</{xdr}:wsDr>"
    if drawing.count(closing) != 1:
        raise SystemExit(f"{drawing_part} has no single {closing}")
    parts[drawing_part] = drawing.replace(closing, "".join(anchors) + closing).encode("utf-8")
    rels_closing = f"</{rel}Relationships>"
    parts[drawing_rels] = rels_xml.replace(rels_closing, "".join(relationships) + rels_closing, 1).encode("utf-8")
    content_types = parts["[Content_Types].xml"].decode("utf-8")
    for suffix in {u["image"].suffix.lstrip(".").lower() for u in pictures}:
        if not re.search(rf'<Default\b[^>]*Extension="{suffix}"', content_types, re.I):
            content_types = content_types.replace(
                "</Types>", f'<Default Extension="{suffix}" ContentType="image/{suffix}"/></Types>', 1)
    parts["[Content_Types].xml"] = content_types.encode("utf-8")
    return parts


def video_section(case_id: str, video: Path, note: str = "") -> str:
    encoded = base64.b64encode(video.read_bytes()).decode("ascii")
    case_id = html.escape(case_id, quote=True)
    conflict = (f'<p class="conflict"><strong>Conflict:</strong> '
                f'{html.escape(note).replace(chr(10), "<br>")}</p>') if note else ""
    return f'<section id="{case_id}"><h2>{case_id}</h2>{conflict}<video controls preload="metadata" width="800"><source src="data:video/webm;base64,{encoded}" type="video/webm">WebM video unsupported.</video></section>'


def group_video_section(group_id: str, label: str, video: Path, note: str = "") -> str:
    """One video the run recorded for a whole suite group. A suite whose cases
    all read one shared page may record a single video for the group rather
    than one per case, so it is labelled by group, not by case ID. Any held
    bullets in the workbook are listed above it, since the whole group shares
    the one recording."""
    encoded = base64.b64encode(video.read_bytes()).decode("ascii")
    reason = (f'<p class="conflict"><strong>Held (drift):</strong> '
              f'{html.escape(note).replace(chr(10), "<br>")}</p>') if note else ""
    return (f'<section id="{html.escape(group_id, quote=True)}"><h2>{html.escape(label)}</h2>{reason}'
            f'<video controls preload="metadata" width="800"><source src="data:video/webm;base64,{encoded}" '
            f'type="video/webm">WebM video unsupported.</video></section>')


def merge_viewer(base: Path | None, output: Path, order: list[str], new_videos: dict[str, Path]) -> tuple[int, int]:
    """An existing viewer's sections plus the new cases', in workbook order."""
    sections: dict[str, str] = {}
    if base is not None:
        text = base.read_text(encoding="utf-8")
        for match in re.finditer(r'<section id="([^"]+)">.*?</section>', text, re.S):
            sections[html.unescape(match.group(1))] = match.group(0)
    kept = len(sections)
    for case_id, video in new_videos.items():
        sections[case_id] = video_section(case_id, video)
    ordered = [sections[i] for i in order if i in sections]
    ordered += [s for i, s in sections.items() if i not in set(order)]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(viewer_page(ordered), encoding="utf-8")
    return kept, len(ordered)


def viewer_page(sections: list[str]) -> str:
    return ('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>Automated E2E videos</title><style>body{font:16px system-ui;max-width:900px;margin:2rem auto;padding:0 1rem}section{margin:2rem 0;border-bottom:1px solid #ddd;padding-bottom:1rem}video{max-width:100%;height:auto}.conflict{background:#fff4e5;border-left:4px solid #f59e0b;padding:.5rem .75rem}</style>'
            '<h1>Automated E2E videos</h1>' + ("".join(sections) or "<p>No successful videos captured.</p>") + "</html>")


def write_viewer(output: Path, rows: list[dict], group_videos: list[tuple[str, Path]] | None = None) -> int:
    sections = [video_section(row["id"], row["video"], "\n".join(row.get("notes", []))) for row in rows
                if display_status(row["status"], row.get("notes", [])) == "Passed" and row["video"] is not None]
    for group_id, video in group_videos or []:
        sections.append(group_video_section(group_id, group_id, video))
    page = viewer_page(sections)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(page, encoding="utf-8")
    return len(sections)


def resolve_test_date(value: str | None) -> str | None:
    """The date stamped in --date-col, as dd/mm/yyyy. `today` means the moment
    the results are collected; anything else is taken verbatim."""
    if value is None or value.strip() == "":
        return None
    if value.strip().lower() == "today":
        from datetime import date
        return date.today().strftime("%d/%m/%Y")
    return value.strip()


def parse_group_videos(values: list[str], video_root: Path) -> list[tuple[str, Path]]:
    """`LABEL=PATH` arguments as (label, existing file) pairs."""
    videos: list[tuple[str, Path]] = []
    for value in values:
        if "=" not in value:
            raise SystemExit(f"--group-video wants LABEL=PATH, got {value!r}")
        label, raw = value.split("=", 1)
        path = Path(raw).expanduser()
        if not path.is_file() and not path.is_absolute():
            candidate = video_root / path
            if candidate.is_file():
                path = candidate
        if not path.is_file():
            raise SystemExit(f"--group-video video not found: {raw}")
        videos.append((label, path.resolve()))
    return videos


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path, action="append",
                        help="a Playwright JSON report; repeat it to merge separate runs (e.g. one per seeded suite)")
    parser.add_argument("--evidence", default=Path("evidence"), type=Path)
    parser.add_argument("--video-root", default=Path("test-results"), type=Path)
    parser.add_argument("--video-html", type=Path)
    parser.add_argument("--sheet", required=True,
                        help="the source sheet holding the cases; read the workbook first "
                             "(its sheet names are printed when this one is not found)")
    parser.add_argument("--first-row", type=int, default=5)
    parser.add_argument("--id-col", default="C")
    parser.add_argument("--topic-col", default="D")
    parser.add_argument("--expected-col", default="F",
                        help="column of the source sheet holding the expected result (copied to the Automated sheet)")
    parser.add_argument("--status-col", default="G",
                        help="column of the source sheet holding each case's status; Passed and Not pass are written back here")
    parser.add_argument("--tester", help="the name stamped in --tester-col on every case that got a result "
                                         "(Pass / Not pass): the person who ran the tests and generates this file. "
                                         "Ask who it is before exporting")
    parser.add_argument("--no-tester", action="store_true",
                        help="export without stamping a tester (only when the person said to leave it blank)")
    parser.add_argument("--tester-col", default="H", help="column of the source sheet holding the Tester")
    parser.add_argument("--date-col", help="column of the source sheet holding the Test date; with --test-date "
                                           "each case that got a result is stamped there. Add --update to stamp "
                                           "existing Automated-sheet rows too")
    parser.add_argument("--test-date", help="the run date written to --date-col, as dd/mm/yyyy; pass 'today' to use "
                                            "the current date when the results are collected")
    parser.add_argument("--group-video", action="append", default=[], metavar="LABEL=PATH",
                        help="a run video recorded once for a whole suite group (the shared-page Configuration "
                             "suites' `group-video` directory), embedded in the viewer under LABEL. Repeat it.")
    parser.add_argument("--pass-label", default="Pass",
                        help="what the source sheet's status dropdown calls a pass (written to --status-col)")
    parser.add_argument("--fail-label", default="Not pass",
                        help="what the source sheet's status dropdown calls a failure (e.g. ไม่ผ่าน)")
    parser.add_argument("--no-input-image", action="store_true",
                        help="leave out the input-file pictures (`<CASE-ID>-excel`, `-csv`, `-txt`, `-input`, ...) "
                             "that otherwise sit above the result in the Image cell")
    parser.add_argument("--tc-prefix", required=True,
                        help="the case-ID family in this workbook, without the number "
                             "(IDs are matched as <prefix>-<number>). Read it off the source "
                             "sheet's ID column; there is no default")
    parser.add_argument("--update", action="store_true",
                        help="the source already has an Automated sheet: fill only its 'Not run' rows "
                             "that the current report covers, keep every other row and image, and "
                             "merge the new videos into --base-video-html")
    parser.add_argument("--base-video-html", type=Path,
                        help="with --update: the viewer delivered with the source workbook")
    args = parser.parse_args()
    source, output = args.source.expanduser(), args.out.expanduser()
    args.tester = (args.tester or "").strip() or None
    args.test_date = resolve_test_date(args.test_date)
    if args.test_date and not args.date_col:
        raise SystemExit("--test-date needs --date-col (the source sheet column to stamp)")
    if args.tester is None and not args.no_tester:
        raise SystemExit("--tester NAME is required: ask who is running these tests (their name goes in the "
                         "Tester column of every case with a result), or pass --no-tester if they said to leave it blank")
    if not source.is_file():
        raise SystemExit(f"source workbook not found: {source}")
    if source.resolve() == output.resolve():
        raise SystemExit("--out must not overwrite the source workbook")
    if args.update:
        return update_main(args, source, output)
    cases = read_cases(source, args.sheet, args.first_row, args.id_col, args.topic_col, args.tc_prefix, args.expected_col)
    if not cases:
        raise SystemExit(f"no IDs matching {args.tc_prefix}-<number> found in {args.sheet}")
    reports = [report.expanduser() for report in args.report]
    results = merged_results(reports, args.tc_prefix)
    video_root = args.video_root.expanduser()
    group_videos = parse_group_videos(args.group_video, video_root)
    with tempfile.TemporaryDirectory() as workdir:
        rows = []
        for case in cases:
            result = results.get(case["id"], {})
            report = result.get("report", reports[-1])
            image = find_artifact(result.get("image"), report, video_root)
            inputs = [] if args.no_input_image else [
                picture for attachment in result.get("inputs", [])
                if (picture := input_picture(attachment, report, video_root, Path(workdir))) is not None
            ]
            rows.append({
                "id": case["id"], "row": case["row"], "topic": case["topic"], "expected": case["expected"],
                "status": result.get("status", "Not run"), "reasons": result.get("reasons", []),
                "notes": result.get("notes", []),
                "image": image, "pictures": [*inputs, *([image] if image else [])],
                "video": find_artifact(result.get("video"), report, video_root),
            })
        write_xlsx(source, output, "Automated", rows, args.sheet, args.status_col, args.pass_label,
                   args.tester, args.tester_col, args.fail_label, args.date_col, args.test_date)
    viewer = args.video_html.expanduser() if args.video_html else output.with_name(f"{output.stem}_videos.html")
    videos = write_viewer(viewer, rows, group_videos)
    tally = {}
    for row in rows:
        shown = display_status(row["status"], row.get("notes", []))
        tally[shown] = tally.get(shown, 0) + 1
    print(f"cases            : {len(rows)} ({', '.join(f'{n} {k}' for k, n in sorted(tally.items()))})")
    print(f"Tester           : {args.tester or '(not stamped)'} -> column {args.tester_col} of {args.sheet}")
    if args.date_col:
        print(f"Test date        : {args.test_date or '(not stamped)'} -> column {args.date_col} of {args.sheet}")
    print(f"{args.sheet} status   : Passed -> {args.pass_label!r}, Not pass -> {args.fail_label!r} written to column {args.status_col}")
    held = [r["id"] for r in rows if r["notes"]]
    if held:
        print(f"held (drift)     : {held} — app contradicts the case; recorded as Not pass with the drift reason in the Reason column")
    print(f"workbook         : {output}")
    print(f"standalone videos: {viewer} ({videos} cases)")
    return 0


def update_main(args: argparse.Namespace, source: Path, output: Path) -> int:
    recorded, columns = read_recorded(source, "Automated", args.tc_prefix)
    if not recorded:
        raise SystemExit(f"no {args.tc_prefix}-<number> rows in the Automated sheet")
    cases = {c["id"]: c for c in read_cases(source, args.sheet, args.first_row, args.id_col,
                                              args.topic_col, args.tc_prefix, args.expected_col)}
    results = merged_results([report.expanduser() for report in args.report], args.tc_prefix)
    video_root = args.video_root.expanduser()
    updates = []
    # Only a row still waiting in the delivered sheet is filled; a row that
    # already carries Passed/Not pass keeps it. "Waiting to test"/"Not run" are
    # old spellings from workbooks delivered before every unconfirmed case
    # became Not pass, so updating one of those still fills the row.
    unfilled = ("Not run", "Waiting to test")
    for row in recorded:
        result = results.get(row["id"])
        if row["status"] not in unfilled or result is None:
            continue
        case = cases.get(row["id"], {})
        updates.append({
            **row, "status": result["status"], "reasons": result.get("reasons", []),
            "notes": result.get("notes", []),
            "expected": case.get("expected", ""), "source_row": case.get("row"),
            "image": find_artifact(result.get("image"), result["report"], video_root),
            "video": find_artifact(result.get("video"), result["report"], video_root),
        })
    with_inputs = sorted(u["id"] for u in updates if results[u["id"]].get("inputs"))
    if with_inputs:
        print(f"warning: --update embeds only the result frame; {with_inputs} also have input-file "
              "pictures — regenerate from the original workbook to show them", file=sys.stderr)
    already = sorted(i for i in results if i in {x["id"] for x in recorded if x["status"] not in unfilled})
    parts, infos = read_parts(source)
    parts = update_sheet(parts, "Automated", updates, columns)
    parts = sync_test_result(parts, args.sheet, args.status_col,
                             [{**u, "row": u["source_row"]} for u in updates if u["source_row"]], args.pass_label,
                             args.tester, args.tester_col, args.fail_label, args.date_col, args.test_date)
    write_parts(output, parts, infos)
    base = args.base_video_html.expanduser() if args.base_video_html else None
    if base is not None and not base.is_file():
        raise SystemExit(f"--base-video-html not found: {base}")
    viewer = args.video_html.expanduser() if args.video_html else output.with_name(f"{output.stem}_videos.html")
    if base is not None and viewer.resolve() == base.resolve():
        raise SystemExit("--video-html must not overwrite --base-video-html")
    new_videos = {u["id"]: u["video"] for u in updates if display_status(u["status"], u.get("notes", [])) == "Passed" and u["video"] is not None}
    kept, total = merge_viewer(base, viewer, [r["id"] for r in recorded], new_videos)
    print(f"filled rows      : {len(updates)} ({', '.join(u['id'] + '=' + display_status(u['status']) for u in updates)})")
    print(f"left as recorded : {len(already)} report case(s) already had a result {already}")
    print(f"workbook         : {output}")
    print(f"standalone videos: {viewer} ({kept} kept + {len(new_videos)} new = {total} cases)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
