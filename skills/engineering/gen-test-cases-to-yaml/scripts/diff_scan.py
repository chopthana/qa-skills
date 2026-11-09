#!/usr/bin/env python3
"""Diff two scan_folder.py inventories so a re-run converts only what changed.

Usage:
  diff_scan.py --old baseline.json --new current.json [--json OUT.json]
                                                   [--format md|none] [--quiet]

`baseline.json` is a previous scan of the same source folder (keep it in the
staging dir). `current.json` is a fresh scan. The diff classifies, per file:

  unchanged  same fingerprint -> copy the previous staged YAML, convert nothing
  changed    fingerprint differs -> convert only the added/changed rows
  added      new file -> convert all rows
  removed    file gone -> delete its staged YAML

and per row inside a changed file: unchanged / changed / added / removed.

Row identity is the sheet's `TC ID` when it is non-empty and unique on its side;
otherwise the row's content fingerprint. That is what lets a row keep its
identity when QA inserts or reorders rows: a case that only moved is
`unchanged`, only its content edit is `changed`.

Exit 0 whenever both inputs are valid scans; changes are the normal output,
not an error. Exit 2 on a bad input.
"""

import argparse
import json
import sys
from pathlib import Path


def load(path):
    try:
        report = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        sys.exit(f"cannot read scan {path}: {exc}")
    if not isinstance(report, dict) or "files" not in report:
        sys.exit(f"{path} is not a scan_folder.py inventory (no `files`)")
    return report


def all_rows(f):
    """Flat list of case rows across a file's case sheets."""
    return [
        {
            "sheet": sheet["name"],
            "row": int(record["row"]),
            "tc_id": record.get("tc_id", ""),
            "fingerprint": record.get("fingerprint", ""),
        }
        for sheet in f.get("sheets", [])
        if sheet.get("kind") == "cases"
        for record in sheet.get("rows", [])
    ]


def unique_tc_ids(rows):
    counts = {}
    for r in rows:
        if r["tc_id"]:
            counts[r["tc_id"]] = counts.get(r["tc_id"], 0) + 1
    return {tc for tc, n in counts.items() if n == 1}


def diff_rows(old_rows, new_rows):
    """Return (entries, counts). Match by unique TC ID first, then fingerprint."""
    old_free, new_free = list(old_rows), list(new_rows)
    entries = []

    # Pass 1: unique TC ID on both sides.
    old_by_tc = {r["tc_id"]: r for r in old_free if r["tc_id"] in unique_tc_ids(old_rows)}
    new_by_tc = {r["tc_id"]: r for r in new_free if r["tc_id"] in unique_tc_ids(new_rows)}
    for tc in sorted(set(old_by_tc) & set(new_by_tc)):
        o, n = old_by_tc[tc], new_by_tc[tc]
        state = "unchanged" if o["fingerprint"] == n["fingerprint"] else "changed"
        entries.append(
            {"tc_id": tc, "sheet": n["sheet"], "old_row": o["row"], "new_row": n["row"],
             "state": state, "matched_by": "tc_id"}
        )
        old_free.remove(o)
        new_free.remove(n)

    # Pass 2: content fingerprint among the rest (row had no usable TC ID, or it
    # collided). A unique fingerprint on both sides means the same content moved.
    old_by_fp, new_by_fp = {}, {}
    for r in old_free:
        key = r["fingerprint"] or None
        if key:
            old_by_fp.setdefault(key, []).append(r)
        else:
            old_by_fp.setdefault(None, []).append(r)
    for r in new_free:
        key = r["fingerprint"] or None
        if key:
            new_by_fp.setdefault(key, []).append(r)
        else:
            new_by_fp.setdefault(None, []).append(r)

    def pop_matched(old_bucket, new_bucket):
        pairs = []
        for key in set(old_bucket) & set(new_bucket):
            if key is None:
                continue
            olds, news = old_bucket[key], new_bucket[key]
            while olds and news:
                pairs.append((olds.pop(), news.pop()))
        return pairs

    for o, n in pop_matched(old_by_fp, new_by_fp):
        entries.append(
            {"tc_id": n["tc_id"] or o["tc_id"], "sheet": n["sheet"],
             "old_row": o["row"], "new_row": n["row"],
             "state": "unchanged", "matched_by": "fingerprint"}
        )
        old_free.remove(o)
        new_free.remove(n)

    for o in old_free:
        entries.append(
            {"tc_id": o["tc_id"], "sheet": o["sheet"], "old_row": o["row"],
             "new_row": None, "state": "removed", "matched_by": "none"}
        )
    for n in new_free:
        entries.append(
            {"tc_id": n["tc_id"], "sheet": n["sheet"], "old_row": None,
             "new_row": n["row"], "state": "added", "matched_by": "none"}
        )

    entries.sort(key=lambda e: (e["new_row"] is None, e["new_row"] or e["old_row"] or 0))
    counts = {s: sum(1 for e in entries if e["state"] == s)
              for s in ("unchanged", "changed", "added", "removed")}
    return entries, counts


def diff_reports(old, new):
    old_files = {f["name"]: f for f in old["files"]}
    new_files = {f["name"]: f for f in new["files"]}
    files = []

    for name in sorted(set(old_files) | set(new_files), key=str.lower):
        o, n = old_files.get(name), new_files.get(name)
        if o and not n:
            files.append({
                "name": name, "old_path": o["path"], "new_path": None,
                "state": "removed", "reuse_previous": False,
                "old_fingerprint": o.get("fingerprint", ""), "new_fingerprint": None,
                "counts": {}, "rows": [],
            })
            continue
        if n and not o:
            rows = all_rows(n)
            files.append({
                "name": name, "old_path": None, "new_path": n["path"],
                "state": "added", "reuse_previous": False,
                "old_fingerprint": None, "new_fingerprint": n.get("fingerprint", ""),
                "counts": {"added": len(rows)}, "rows": [
                    {"tc_id": r["tc_id"], "sheet": r["sheet"], "old_row": None,
                     "new_row": r["row"], "state": "added", "matched_by": "none"}
                    for r in rows
                ],
            })
            continue

        # Both sides: compare file content.
        old_fp, new_fp = o.get("fingerprint", ""), n.get("fingerprint", "")
        if old_fp and old_fp == new_fp:
            entries, counts = [], {"unchanged": sum(1 for _ in all_rows(n))}
            state = "unchanged"
        else:
            entries, counts = diff_rows(all_rows(o), all_rows(n))
            state = "changed"
        files.append({
            "name": name, "old_path": o["path"], "new_path": n["path"],
            "state": state, "reuse_previous": state == "unchanged",
            "old_fingerprint": old_fp, "new_fingerprint": new_fp,
            "counts": counts, "rows": entries,
        })

    totals = {
        "files": {s: sum(1 for f in files if f["state"] == s)
                  for s in ("unchanged", "changed", "added", "removed")},
        "rows": {s: sum(f["counts"].get(s, 0) for f in files)
                 for s in ("unchanged", "changed", "added", "removed")},
    }
    return {"baseline": old.get("source", ""), "current": new.get("source", ""),
            "files": files, "totals": totals}


def dump_markdown(d):
    t = d["totals"]
    print(f"# Scan diff: {d['current']}\n")
    print(f"against baseline: {d['baseline'] or '(first run)'}\n")
    print(f"files: {t['files']}  |  rows: {t['rows']}\n")
    reuse = [f for f in d["files"] if f["reuse_previous"]]
    print(f"REUSE AS-IS (convert nothing): {len(reuse)} file(s) — "
          f"{', '.join(f['name'] for f in reuse) or 'none'}\n")
    for f in d["files"]:
        if f["state"] == "unchanged":
            continue
        head = f"## [{f['state']}] {f['name']}"
        if f["state"] == "changed":
            head += f"  ({f['counts']})"
        print(head)
        if f["state"] == "removed":
            print("- delete its staged YAML (source file is gone)\n")
            continue
        for e in f["rows"]:
            if f["state"] == "added" or e["state"] != "unchanged":
                where = f"row {e['old_row']}->{e['new_row']}" if e["old_row"] and e["new_row"] \
                    else f"row {e['new_row'] or e['old_row']}"
                print(f"- {e['state']:<8} {e['tc_id'] or '(no TC ID)':<28} {where}")
        print()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--old", required=True, help="previous scan JSON (baseline)")
    ap.add_argument("--new", required=True, help="fresh scan JSON (current)")
    ap.add_argument("--json", dest="json_out")
    ap.add_argument("--format", choices=["md", "none"], default="md")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    old, new = load(args.old), load(args.new)
    d = diff_reports(old, new)

    if args.json_out:
        out = Path(args.json_out).expanduser()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
        if not args.quiet:
            print(f"wrote {out}", file=sys.stderr)
    if args.format == "md" and not args.quiet:
        dump_markdown(d)

    t = d["totals"]
    print(
        f"{t['files']['unchanged']} unchanged file(s) (reuse), "
        f"{t['files']['changed']} changed, {t['files']['added']} added, "
        f"{t['files']['removed']} removed; "
        f"{t['rows']['unchanged']} unchanged row(s), {t['rows']['changed']} changed, "
        f"{t['rows']['added']} added, {t['rows']['removed']} removed",
        file=sys.stderr,
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
