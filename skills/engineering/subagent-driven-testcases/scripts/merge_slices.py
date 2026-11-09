#!/usr/bin/env python3
"""Merge slice case files into one set: real IDs, duplicate scan, coverage proof.

    python3 merge_slices.py --workspace <dir> --prefix TC-PROMO \
        [--inventory <dir>/inventory.md] [--meta-file <dir>/meta.json] \
        [--out <dir>/merged.cases.json] [--coverage <dir>/coverage.md] \
        [--start 1] [--pad 3] [--dup-threshold 0.88] [--check-only]

Reads every ``slice-<N>-cases.json`` in the workspace, in slice order. Each file
is either ``{"slice": "3", "covers": [...], "cases": [...]}`` or a bare list of
cases. A case is an object in whatever shape the producer skill's generator
consumes: this script rewrites only its ID field and passes everything else
through byte-for-byte.

Prints the three numbers the controller has to read — unclaimed inventory items,
near-duplicate cases, and the ID map — and writes them to the coverage report.
Stdlib only. No case text is printed, only IDs and counts.
"""

import argparse
import difflib
import json
import re
import sys
from pathlib import Path

ID_FIELDS = ("tc_id", "tcid", "id", "case_id", "caseId", "testcase_id", "TC ID")
TOPIC_FIELDS = ("topic", "title", "name", "scenario", "summary", "หัวข้อ")
STEP_FIELDS = ("steps", "step", "test_steps", "procedure", "กรณีทดสอบและขั้นตอนการทดสอบ")
EXPECT_FIELDS = ("expected", "expected_result", "expectedResult", "result",
                 "ผลการทดสอบที่คาดหวัง")

SLICE_FILE = re.compile(r"^slice-(\d+)-cases\.json$")
PLACEHOLDER = re.compile(r"^\{\{\s*S(\d+)\s*\}\}-(\d+)([A-Za-z]?)$")
# An inventory item line: a table row or a bullet whose first cell is the ID.
ITEM_ID = re.compile(
    r"^\s*(?:\|\s*|[-*]\s+)[`*_]{0,3}"
    r"([A-Z]{1,3}-[A-Za-z0-9][A-Za-z0-9._-]*)"
    r"[`*_]{0,3}\s*(?:\||$|—|-\s|:)"
)


def pick(case, names):
    for n in names:
        if n in case:
            return n
    return None


def text_of(value):
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)):
        return "\n".join(text_of(v) for v in value)
    if isinstance(value, dict):
        return "\n".join(text_of(v) for v in value.values())
    return str(value)


def normalize(s):
    return re.sub(r"\s+", " ", s.replace(" ", " ")).strip().lower()


def fingerprint(case):
    """Normalized topic / steps / expected for duplicate detection.

    Falls back to every string in the case, so an unfamiliar case shape still
    gets compared instead of silently skipped.
    """
    t = pick(case, TOPIC_FIELDS)
    s = pick(case, STEP_FIELDS)
    e = pick(case, EXPECT_FIELDS)
    if not (t or s or e):
        whole = normalize(text_of({k: v for k, v in case.items()
                                   if k not in ID_FIELDS}))
        return whole, whole, whole
    return (normalize(text_of(case.get(t))) if t else "",
            normalize(text_of(case.get(s))) if s else "",
            normalize(text_of(case.get(e))) if e else "")


def load_slices(workspace):
    found = []
    for path in sorted(workspace.iterdir()):
        m = SLICE_FILE.match(path.name)
        if m:
            found.append((int(m.group(1)), path))
    found.sort(key=lambda p: p[0])
    slices = []
    for num, path in found:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise SystemExit("error: %s is not readable JSON: %s" % (path.name, exc))
        if isinstance(data, list):
            cases, covers, declared = data, [], None
        elif isinstance(data, dict):
            cases = data.get("cases")
            covers = data.get("covers") or []
            declared = data.get("slice")
            if not isinstance(cases, list):
                raise SystemExit("error: %s has no 'cases' list" % path.name)
        else:
            raise SystemExit("error: %s is neither an object nor a list" % path.name)
        if declared is not None and str(declared).strip() != str(num):
            print("warn: %s declares slice '%s' — using %d from the file name"
                  % (path.name, declared, num), file=sys.stderr)
        if not isinstance(covers, list):
            raise SystemExit("error: %s has a 'covers' that is not a list" % path.name)
        slices.append({"n": num, "path": path, "cases": cases,
                       "covers": [str(c).strip().strip("`") for c in covers]})
    return slices


def inventory_items(path):
    items, seen = [], set()
    for line in path.read_text(encoding="utf-8").splitlines():
        m = ITEM_ID.match(line)
        if m:
            item = m.group(1)
            if item.upper() in ("ID", "IDS"):
                continue
            if item not in seen:
                seen.add(item)
                items.append(item)
    return items


def duplicates(flat, threshold):
    pairs = []
    fps = [fingerprint(c["case"]) for c in flat]
    for i in range(len(flat)):
        ti, si, ei = fps[i]
        for j in range(i + 1, len(flat)):
            tj, sj, ej = fps[j]
            topic = difflib.SequenceMatcher(None, ti, tj).ratio() if ti and tj else 0.0
            if topic >= threshold:
                pairs.append((flat[i], flat[j], "topic", topic))
                continue
            if si and sj and ei and ej:
                steps = difflib.SequenceMatcher(None, si, sj).quick_ratio()
                if steps < threshold:
                    continue
                steps = difflib.SequenceMatcher(None, si, sj).ratio()
                exp = difflib.SequenceMatcher(None, ei, ej).ratio()
                if steps >= threshold and exp >= threshold:
                    pairs.append((flat[i], flat[j], "steps+expected",
                                  (steps + exp) / 2))
    return pairs


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workspace", required=True, type=Path)
    ap.add_argument("--prefix", required=True,
                    help="confirmed TC ID prefix, e.g. TC-PROMO")
    ap.add_argument("--inventory", type=Path,
                    help="inventory.md; omitted skips the coverage proof")
    ap.add_argument("--meta-file", type=Path,
                    help="JSON object of top-level fields the producer's "
                         "generator expects beside 'cases'")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--coverage", type=Path)
    ap.add_argument("--start", type=int, default=1)
    ap.add_argument("--pad", type=int, default=3)
    ap.add_argument("--dup-threshold", type=float, default=0.88)
    ap.add_argument("--check-only", action="store_true",
                    help="report, write nothing")
    args = ap.parse_args()

    ws = args.workspace
    if not ws.is_dir():
        raise SystemExit("error: no such workspace: %s" % ws)
    out = args.out or ws / "merged.cases.json"
    cov = args.coverage or ws / "coverage.md"

    slices = load_slices(ws)
    if not slices:
        raise SystemExit("error: no slice-<N>-cases.json in %s" % ws)

    # Renumber in slice order. Placeholders are checked, not trusted.
    flat, id_map, bad_ids = [], [], []
    seq = args.start
    for sl in slices:
        for pos, case in enumerate(sl["cases"], 1):
            if not isinstance(case, dict):
                raise SystemExit("error: %s case %d is not an object"
                                 % (sl["path"].name, pos))
            field = pick(case, ID_FIELDS)
            old = str(case.get(field, "")).strip() if field else ""
            if not field:
                field = ID_FIELDS[0]
                bad_ids.append((sl["n"], pos, "no ID field"))
            else:
                m = PLACEHOLDER.match(old)
                if not m:
                    bad_ids.append((sl["n"], pos, "not a {{S%d}}-nnn placeholder: %r"
                                    % (sl["n"], old)))
                elif int(m.group(1)) != sl["n"]:
                    bad_ids.append((sl["n"], pos, "placeholder names slice %s: %r"
                                    % (m.group(1), old)))
            new = "%s-%0*d" % (args.prefix, args.pad, seq)
            seq += 1
            merged = dict(case)
            merged[field] = new
            flat.append({"slice": sl["n"], "pos": pos, "old": old or "(none)",
                         "new": new, "case": merged})
            id_map.append((sl["n"], old or "(none)", new))

    dups = duplicates(flat, args.dup_threshold)

    claimed, claim_owner = [], {}
    for sl in slices:
        for item in sl["covers"]:
            claim_owner.setdefault(item, []).append(sl["n"])
            if item not in claimed:
                claimed.append(item)
    items = inventory_items(args.inventory) if args.inventory else []
    unclaimed = [i for i in items if i not in claim_owner]
    unknown = [i for i in claimed if items and i not in items]
    multi = {i: ns for i, ns in claim_owner.items() if len(ns) > 1}

    # ---- stdout: counts and IDs only, never case text ----
    print("slices: %d  (%s)" % (len(slices), ", ".join("S%d:%d" % (s["n"], len(s["cases"]))
                                                       for s in slices)))
    print("cases: %d  →  %s-%0*d .. %s-%0*d"
          % (len(flat), args.prefix, args.pad, args.start,
             args.prefix, args.pad, seq - 1))
    if items:
        print("inventory: %d items — claimed %d, unclaimed %d"
              % (len(items), len(items) - len(unclaimed), len(unclaimed)))
    else:
        print("inventory: not checked (no --inventory)")
    print("near-duplicates: %d pair(s) at threshold %.2f" % (len(dups), args.dup_threshold))
    print("placeholder problems: %d" % len(bad_ids))

    if unclaimed or dups or bad_ids or unknown or multi:
        print("\nACTION REQUIRED")
        for item in unclaimed:
            print("  unclaimed item   %s — no slice wrote a case for it" % item)
        for item in unknown:
            print("  unknown item     %s — claimed by S%s, not in the inventory"
                  % (item, ",".join(str(n) for n in claim_owner[item])))
        for item, ns in multi.items():
            print("  double-claimed   %s — slices %s"
                  % (item, ", ".join("S%d" % n for n in ns)))
        for a, b, why, score in dups:
            print("  near-duplicate   %s (S%d, was %s)  ~  %s (S%d, was %s)  "
                  "[%s %.2f]" % (a["new"], a["slice"], a["old"],
                                 b["new"], b["slice"], b["old"], why, score))
        for n, pos, why in bad_ids:
            print("  placeholder      S%d case %d — %s" % (n, pos, why))

    if args.check_only:
        print("\ncheck-only: nothing written")
        return 0

    payload = {}
    if args.meta_file:
        meta = json.loads(args.meta_file.read_text(encoding="utf-8"))
        if not isinstance(meta, dict):
            raise SystemExit("error: --meta-file must hold a JSON object")
        payload.update(meta)
    payload["cases"] = [f["case"] for f in flat]
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")

    lines = ["# Merge report", ""]
    lines.append("- slices: %d" % len(slices))
    lines.append("- cases: %d (%s-%0*d .. %s-%0*d)"
                 % (len(flat), args.prefix, args.pad, args.start,
                    args.prefix, args.pad, seq - 1))
    if items:
        lines.append("- coverage: claimed %d/%d, unclaimed %d"
                     % (len(items) - len(unclaimed), len(items), len(unclaimed)))
    lines.append("- near-duplicates: %d" % len(dups))
    lines.append("- placeholder problems: %d" % len(bad_ids))
    lines.append("")
    if unclaimed:
        lines += ["## Unclaimed inventory items", ""] + \
                 ["- `%s`" % i for i in unclaimed] + [""]
    if unknown:
        lines += ["## Claimed but not in the inventory", ""] + \
                 ["- `%s` (S%s)" % (i, ",".join(str(n) for n in claim_owner[i]))
                  for i in unknown] + [""]
    if multi:
        lines += ["## Double-claimed items", ""] + \
                 ["- `%s` — %s" % (i, ", ".join("S%d" % n for n in ns))
                  for i, ns in multi.items()] + [""]
    if dups:
        lines += ["## Near-duplicate cases", ""] + \
                 ["- `%s` (S%d) ~ `%s` (S%d) — %s %.2f"
                  % (a["new"], a["slice"], b["new"], b["slice"], why, score)
                  for a, b, why, score in dups] + [""]
    if bad_ids:
        lines += ["## Placeholder problems", ""] + \
                 ["- S%d case %d — %s" % (n, pos, why) for n, pos, why in bad_ids] + [""]
    lines += ["## ID map", "", "| slice | placeholder | final |", "| --- | --- | --- |"]
    lines += ["| S%d | `%s` | `%s` |" % (n, old, new) for n, old, new in id_map]
    lines.append("")
    cov.write_text("\n".join(lines), encoding="utf-8")

    print("\nwrote %s" % out)
    print("wrote %s" % cov)
    return 0


if __name__ == "__main__":
    sys.exit(main())
