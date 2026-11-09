#!/usr/bin/env python3
"""Prove that no source test case was dropped on the way into staged YAML.

Usage:
  reconcile.py --source source.json --map mapping.csv --staging <dir>
               [--allow-unreadable] [--allow-skipped]

mapping.csv columns (header required, extra columns ignored):
  source_file,sheet,source_row,source_tc_id,new_id,target_path,note

  source_file   basename as it appears in source.json
  sheet         sheet name the row came from
  source_row    1-based spreadsheet row number from the scan
  source_tc_id  the sheet's TC ID for that row (preferred row identity)
  new_id        target case id, or SKIPPED (then `note` must give the reason)
  target_path   staged YAML file holding that case, relative to --staging
                (absolute or repo-relative paths are accepted too)

A mapping row is matched to its source row by `source_tc_id` when that TC ID is
unique in its sheet; otherwise by `source_row`. Keying on the TC ID rather than
the row number means a re-run survives QA inserting or reordering rows — the
row still resolves, so an unchanged case needs no new mapping line and no
re-conversion.

Checks, all of them fatal unless a flag says otherwise:
  1. every case row in source.json appears exactly once in the mapping
  2. every mapping row points at a real source row
  3. every mapped id exists in the staged YAML, in the file target_path names
  4. every case in the staged YAML appears in the mapping (no invented cases)
  5. ids are unique in the mapping
  6. unreadable source files are unresolved        (--allow-unreadable)
  7. rows mapped to SKIPPED carry a reason          (--allow-skipped)

Exit 0 means every source row is accounted for.
"""

import argparse
import csv
import json
import re
import sys
from pathlib import Path

ID_LINE_RE = re.compile(r"^\s*(?:-\s*)?id:\s*[\"']?([A-Za-z0-9][A-Za-z0-9-]*)[\"']?\s*$")
SKIP_TOKENS = {"skipped", "skip", "none", "-"}


def source_rows(report):
    """{(file, sheet, row): tc_id} for every extracted case row."""
    rows = {}
    for f in report["files"]:
        for sheet in f["sheets"]:
            if sheet["kind"] != "cases":
                continue
            for record in sheet["rows"]:
                rows[(f["name"], sheet["name"], int(record["row"]))] = record.get("tc_id", "")
    return rows


def source_index(report):
    """Resolve a mapping row to a source row key.

    Returns ``(by_tc, by_row, tc_counts)`` where ``by_tc[(file, sheet, tc_id)]``
    is the source key when that TC ID is unique within its sheet, and
    ``by_row`` is every key for the row-number fallback. A TC ID reused within a
    sheet (the colliding-rows case) is left out of ``by_tc`` so the row number
    decides — the mapping note for those rows records the numbering agreed with
    the user.
    """
    by_row = source_rows(report)
    counts = {}
    for (_file, _sheet, _row), tc_id in by_row.items():
        if tc_id:
            counts[(_file, _sheet, tc_id)] = counts.get((_file, _sheet, tc_id), 0) + 1
    by_tc = {}
    for (file, sheet, row), tc_id in by_row.items():
        if tc_id and counts[(file, sheet, tc_id)] == 1:
            by_tc[(file, sheet, tc_id)] = (file, sheet, row)
    return by_tc, by_row, counts


def resolve_row(entry, by_tc, by_row):
    """Return (key_or_None, why). Prefer unique TC ID, else row number."""
    tc_id = entry.get("source_tc_id", "")
    if tc_id:
        key = by_tc.get((entry["source_file"], entry["sheet"], tc_id))
        if key is not None:
            return key, "tc_id"
    try:
        row = int(entry["source_row"])
    except (ValueError, TypeError):
        return None, "bad_row"
    key = (entry["source_file"], entry["sheet"], row)
    if key in by_row:
        # If the sheet row carries a different TC ID than the mapping claims,
        # flag it rather than silently accepting a mismatched row.
        return key, "row"
    return None, "missing"


def staged_ids(staging):
    """{case id: [files]} for every id in the staged tree."""
    ids = {}
    for path in sorted(Path(staging).rglob("*.yaml")):
        for line in path.read_text(encoding="utf-8").splitlines():
            m = ID_LINE_RE.match(line)
            if m:
                ids.setdefault(m.group(1), []).append(path)
    return ids


def read_mapping(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        required = {"source_file", "sheet", "source_row", "new_id", "target_path"}
        missing = required - {(c or "").strip() for c in (reader.fieldnames or [])}
        if missing:
            sys.exit(f"{path}: mapping is missing column(s) {sorted(missing)}")
        return [{(k or "").strip(): (v or "").strip() for k, v in row.items()} for row in reader]


def resolve_target(raw, staging):
    candidate = Path(raw)
    if candidate.is_absolute() and candidate.exists():
        return candidate
    for base in (Path(staging), Path.cwd()):
        guess = base / raw
        if guess.exists():
            return guess
    # Last resort: match by basename inside staging.
    matches = [p for p in Path(staging).rglob("*.yaml") if p.name == candidate.name]
    return matches[0] if len(matches) == 1 else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True)
    ap.add_argument("--map", dest="mapping", required=True)
    ap.add_argument("--staging", required=True)
    ap.add_argument("--allow-unreadable", action="store_true")
    ap.add_argument("--allow-skipped", action="store_true")
    args = ap.parse_args()

    report = json.loads(Path(args.source).read_text(encoding="utf-8"))
    rows = source_rows(report)
    by_tc, by_row, _tc_counts = source_index(report)
    mapping = read_mapping(args.mapping)
    staged = staged_ids(args.staging)

    errors, warnings = [], []
    seen_keys, seen_ids, skipped = {}, {}, []

    for i, entry in enumerate(mapping, start=2):  # +2: header plus 1-based
        key, how = resolve_row(entry, by_tc, by_row)
        if key is None:
            if how == "bad_row":
                errors.append(
                    f"mapping.csv:{i}: source_row `{entry['source_row']}` is not a number "
                    f"and source_tc_id `{entry.get('source_tc_id', '')}` matched no source row"
                )
            else:
                errors.append(
                    f"mapping.csv:{i}: no such source row — source_tc_id "
                    f"`{entry.get('source_tc_id', '')}` / source_row `{entry['source_row']}` "
                    f"in {entry['source_file']!r} sheet {entry['sheet']!r}"
                )
            continue
        if how == "row":
            sheet_tc = by_row.get(key, "")
            claimed = entry.get("source_tc_id", "")
            if claimed and sheet_tc and claimed != sheet_tc:
                errors.append(
                    f"mapping.csv:{i}: source_row {key[2]} in {key[0]!r} carries TC "
                    f"`{sheet_tc}`, but the mapping claims `{claimed}` — resolve by row failed"
                )
                continue
        seen_keys.setdefault(key, []).append(i)

        new_id = entry["new_id"]
        if new_id.lower() in SKIP_TOKENS:
            if not entry.get("note"):
                errors.append(f"mapping.csv:{i}: SKIPPED row {key} has no reason in `note`")
            skipped.append((key, entry.get("note", "")))
            continue
        seen_ids.setdefault(new_id, []).append(i)
        if new_id not in staged:
            errors.append(f"mapping.csv:{i}: id `{new_id}` is not in any staged YAML under {args.staging}")
            continue
        target = resolve_target(entry["target_path"], args.staging)
        if target is None:
            errors.append(f"mapping.csv:{i}: target_path `{entry['target_path']}` not found under {args.staging}")
        elif target.resolve() not in {p.resolve() for p in staged[new_id]}:
            where = ", ".join(str(p) for p in staged[new_id])
            errors.append(f"mapping.csv:{i}: id `{new_id}` lives in {where}, not in {target}")

    for key, lines in seen_keys.items():
        if len(lines) > 1:
            errors.append(f"source row {key} mapped {len(lines)} times (mapping.csv lines {lines})")
    for new_id, lines in seen_ids.items():
        if len(lines) > 1:
            errors.append(f"id `{new_id}` used {len(lines)} times in the mapping (lines {lines})")

    for key, tc_id in sorted(rows.items()):
        if key not in seen_keys:
            errors.append(f"UNACCOUNTED source row {key} (TC `{tc_id}`) — not in the mapping")

    for new_id, paths in sorted(staged.items()):
        if new_id not in seen_ids:
            errors.append(
                f"staged id `{new_id}` ({paths[0]}) is in no mapping row — "
                "it traces back to no source case"
            )
        if len(paths) > 1:
            errors.append(f"staged id `{new_id}` appears in {len(paths)} files: {paths}")

    for f in report["files"]:
        if f["status"] != "ok":
            msg = f"source file `{f['name']}` was unreadable: {f['reason']}"
            (warnings if args.allow_unreadable else errors).append(msg)

    if skipped and not args.allow_skipped:
        for key, note in skipped:
            errors.append(f"source row {key} deliberately not converted ({note}) — pass --allow-skipped to accept")

    for w in warnings:
        print(f"WARN  {w}")
    for e in errors:
        print(f"ERROR {e}")

    converted = len(seen_ids)
    print(
        f"\n{len(rows)} source case row(s), {converted} converted, {len(skipped)} skipped, "
        f"{len(staged)} staged id(s), {len(errors)} error(s)"
    )
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
