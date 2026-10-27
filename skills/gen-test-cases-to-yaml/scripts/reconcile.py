#!/usr/bin/env python3
"""Prove that no source test case was dropped on the way into staged YAML.

Usage:
  reconcile.py --source source.json --map mapping.csv --staging <dir>
               [--allow-unreadable] [--allow-skipped]

mapping.csv columns (header required, extra columns ignored):
  source_file,sheet,source_row,source_tc_id,new_id,target_path,note

  source_file  basename as it appears in source.json
  sheet        sheet name the row came from
  source_row   1-based spreadsheet row number from the scan
  new_id       target case id, or SKIPPED (then `note` must give the reason)
  target_path  staged YAML file holding that case, relative to --staging
               (absolute or repo-relative paths are accepted too)

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
    mapping = read_mapping(args.mapping)
    staged = staged_ids(args.staging)

    errors, warnings = [], []
    seen_keys, seen_ids, skipped = {}, {}, []

    for i, entry in enumerate(mapping, start=2):  # +2: header plus 1-based
        try:
            key = (entry["source_file"], entry["sheet"], int(entry["source_row"]))
        except ValueError:
            errors.append(f"mapping.csv:{i}: source_row `{entry['source_row']}` is not a number")
            continue
        if key not in rows:
            errors.append(f"mapping.csv:{i}: no such source row {key} in the scan")
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
