#!/usr/bin/env python3
"""Case-to-spec coverage for an automated suite: which cases a test really owns.

    python3 coverage_e2e.py --cases <file|dir> --specs <dir|file> \
        [--inventory <dir>/inventory.md] [--report <playwright-report.json>] \
        [--out <dir>/coverage-e2e.md] [--id-pattern RE] [--spec-glob '*.spec.*']

Reads the case IDs from the case source, finds every ID mentioned in every spec,
and sorts each case into one bucket:

    green       an active test names it and the run report says it passed
    red         an active test names it and the run report says it failed
    flaky       an active test names it and the run report says flaky
    automated   an active test names it; no run evidence
    parked      only skip/fixme tests name it
    documented  only a header or comment names it — no test owns it
    missing     no spec mentions it (split: planned vs marked manual)
    orphan      a spec names an ID the case source does not have

`parked` and `documented` are not coverage. Counting them is how a suite reports
90% automated with a third of it switched off. Stdlib only.
"""

import argparse
import fnmatch
import json
import re
import sys
from pathlib import Path

DEFAULT_ID_RE = r"\b([A-Z][A-Z0-9]*(?:-[A-Z][A-Z0-9]*)*-\d{1,5})\b"
ID_FIELDS = ("tc_id", "tcid", "id", "case_id", "caseId", "testcase_id", "TC ID")
YAML_ID = re.compile(r"^\s*-?\s*id:\s*[\"']?([A-Za-z0-9._-]+)")

# An occurrence of an ID is classified by the line it sits on.
PARKED_LINE = re.compile(
    r"\b(?:test|it)(?:\.describe)?\s*\.\s*(?:skip|fixme|todo)\s*\(")
ACTIVE_LINE = re.compile(
    r"\b(?:test|it)(?:\.describe)?(?:\.(?:serial|parallel|only))*\s*\(|\.\s*step\s*\(")
# A bare disabling call marks whatever test encloses it — which line-level
# scanning cannot attribute. Reported as a caveat rather than guessed at.
BARE_DISABLE = re.compile(r"\b(?:test|it)\s*\.\s*(?:skip|fixme)\s*\(\s*(?:\)|[a-zA-Z_!(])")
NOT_PLANNED = re.compile(r"^(no|not\s+yet|manual|n/?a)\b[\s—:-]*(.*)$", re.I)


def read_text(path):
    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return ""


def walk_json_ids(node, out):
    if isinstance(node, dict):
        for field in ID_FIELDS:
            if field in node and isinstance(node[field], (str, int)):
                out.append(str(node[field]).strip())
                break
        for v in node.values():
            walk_json_ids(v, out)
    elif isinstance(node, list):
        for v in node:
            walk_json_ids(v, out)


def case_ids(source, id_re):
    """Case IDs in source order: JSON id fields, YAML `id:` keys, else a scan."""
    files = []
    if source.is_dir():
        for p in sorted(source.rglob("*")):
            if p.is_file() and p.suffix.lower() in (".json", ".yaml", ".yml", ".md",
                                                    ".csv", ".txt", ".tsv"):
                files.append(p)
    elif source.is_file():
        files = [source]
    else:
        raise SystemExit("error: no such case source: %s" % source)

    ids, seen, how = [], set(), {}

    def add(i, where):
        i = i.strip().strip("`\"'")
        if i and i not in seen:
            seen.add(i)
            ids.append(i)
            how[i] = where

    for p in files:
        if p.suffix.lower() == ".json":
            try:
                data = json.loads(read_text(p))
            except json.JSONDecodeError:
                continue
            found = []
            walk_json_ids(data, found)
            for i in found:
                add(i, p)
            continue
        text = read_text(p)
        hits = [m.group(1) for m in YAML_ID.finditer(text)] \
            if p.suffix.lower() in (".yaml", ".yml") else []
        if not hits:
            hits = id_re.findall(text)
        for i in hits:
            add(i, p)

    if not ids:
        raise SystemExit("error: found no case IDs in %s — check --id-pattern" % source)
    return ids, how


def spec_files(specs, glob):
    if specs.is_file():
        return [specs]
    if not specs.is_dir():
        raise SystemExit("error: no such spec path: %s" % specs)
    out = [p for p in sorted(specs.rglob("*"))
           if p.is_file() and fnmatch.fnmatch(p.name, glob)]
    if not out:
        raise SystemExit("error: no files matching %r under %s" % (glob, specs))
    return out


def scan_specs(files, id_re):
    """id -> {'active': [(file, line)], 'parked': [...], 'documented': [...]}"""
    mentions, caveats = {}, []
    for p in files:
        text = read_text(p)
        if BARE_DISABLE.search(text):
            caveats.append("%s has a bare test.skip()/test.fixme() — line scanning "
                           "cannot say which test it disables; check it by hand" % p.name)
        for lineno, line in enumerate(text.splitlines(), 1):
            found = set(id_re.findall(line))
            if not found:
                continue
            if PARKED_LINE.search(line):
                kind = "parked"
            elif ACTIVE_LINE.search(line):
                kind = "active"
            else:
                kind = "documented"
            for i in found:
                mentions.setdefault(i, {"active": [], "parked": [], "documented": []})
                mentions[i][kind].append((p, lineno))
    return mentions, caveats


def walk_report(node, titles, trail=()):
    """Collect (full title, status) for every spec, test and step in a report."""
    if isinstance(node, dict):
        if "specs" in node or "suites" in node:
            here = trail + ((node.get("title") or "",) if node.get("title") else ())
            for spec in node.get("specs") or []:
                walk_report(spec, titles, here)
            for suite in node.get("suites") or []:
                walk_report(suite, titles, here)
            return
        title = node.get("title") or ""
        here = trail + ((title,) if title else ())
        statuses = []
        for t in node.get("tests") or []:
            if t.get("status"):
                statuses.append(str(t["status"]))
            for r in t.get("results") or []:
                if r.get("status"):
                    statuses.append(str(r["status"]))
                for step in r.get("steps") or []:
                    walk_report(step, titles, here)
        if node.get("status"):
            statuses.append(str(node["status"]))
        if title:
            titles.append((" > ".join(here), statuses))
        for step in node.get("steps") or []:
            walk_report(step, titles, here)
    elif isinstance(node, list):
        for v in node:
            walk_report(v, titles, trail)


def report_status(path, ids, id_re):
    try:
        data = json.loads(read_text(path))
    except json.JSONDecodeError as exc:
        raise SystemExit("error: --report is not readable JSON: %s" % exc)
    titles = []
    walk_report(data, titles)
    per_id = {}
    for full, statuses in titles:
        # Orphan IDs are collected too: a run naming a case the source lost is
        # a finding, not something to drop here.
        for i in set(id_re.findall(full)):
            per_id.setdefault(i, []).extend(statuses)
    out = {}
    for i, statuses in per_id.items():
        s = {x.lower() for x in statuses}
        if "flaky" in s:
            out[i] = "flaky"
        elif s & {"failed", "unexpected", "timedout", "interrupted"}:
            out[i] = "red"
        elif s & {"passed", "expected"}:
            out[i] = "green"
        elif s & {"skipped"}:
            out[i] = "skipped"
    return out, len(titles)


def inventory_plan(path, id_re):
    """id -> (planned: bool, reason: str) from the inventory's own rows."""
    plan = {}
    for line in read_text(path).splitlines():
        found = id_re.findall(line)
        if not found:
            continue
        item = found[0]
        cells = [c for c in (c.strip().strip("`") for c in line.split("|")) if c]
        planned, reason = True, ""
        for idx, c in enumerate(cells):
            if idx == 0 and item in c:
                continue
            m = NOT_PLANNED.match(c)
            if not m:
                continue
            planned = False
            detail = (m.group(2) or "").strip(" —-:")
            # The trailing cell is usually the Note column: the real reason.
            note = cells[-1] if cells[-1] not in (c, "—", "-") else ""
            reason = " — ".join(p for p in (detail, note) if p) or m.group(1)
            break
        plan[item] = (planned, reason)
    return plan


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cases", required=True, type=Path)
    ap.add_argument("--specs", required=True, type=Path)
    ap.add_argument("--inventory", type=Path)
    ap.add_argument("--report", type=Path, help="Playwright JSON report")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--id-pattern", default=DEFAULT_ID_RE)
    ap.add_argument("--spec-glob", default="*.spec.*")
    args = ap.parse_args()

    id_re = re.compile(args.id_pattern)
    ids, _ = case_ids(args.cases, id_re)
    files = spec_files(args.specs, args.spec_glob)
    mentions, caveats = scan_specs(files, id_re)
    statuses, n_titles = report_status(args.report, set(ids), id_re) \
        if args.report else ({}, 0)
    plan = inventory_plan(args.inventory, id_re) if args.inventory else {}

    buckets = {k: [] for k in ("green", "red", "flaky", "automated", "parked",
                               "documented", "missing", "not_planned")}
    where = {}
    for i in ids:
        m = mentions.get(i)
        planned, reason = plan.get(i, (True, ""))
        if not m:
            buckets["missing" if planned else "not_planned"].append((i, reason))
            continue
        if m["active"]:
            where[i] = m["active"][0]
            st = statuses.get(i)
            buckets[st if st in ("green", "red", "flaky") else "automated"].append(
                (i, "run says skipped" if st == "skipped" else ""))
        elif m["parked"]:
            where[i] = m["parked"][0]
            buckets["parked"].append((i, "%s:%d" % (m["parked"][0][0].name,
                                                    m["parked"][0][1])))
        else:
            where[i] = m["documented"][0]
            buckets["documented"].append((i, "%s:%d" % (m["documented"][0][0].name,
                                                        m["documented"][0][1])))
    orphans = sorted(set(mentions) - set(ids))

    # "Owned" counts every case an active test names, red included — a failing
    # test is automation that works. "Passing" is the number QA acts on, and it
    # never counts parked or documented-only cases.
    owned = (len(buckets["green"]) + len(buckets["red"]) + len(buckets["flaky"])
             + len(buckets["automated"]))
    total = len(ids)
    pct = (100.0 * owned / total) if total else 0.0
    passing = len(buckets["green"])
    pct_pass = (100.0 * passing / total) if total else 0.0

    print("cases: %d from %s" % (total, args.cases))
    print("specs: %d file(s) matching %r" % (len(files), args.spec_glob))
    if args.report:
        print("report: %d titles read from %s" % (n_titles, args.report.name))
    print()
    print("COVERAGE  owned by an active test: %d/%d (%.0f%%)" % (owned, total, pct))
    if args.report:
        print("          passing in this run:    %d/%d (%.0f%%)"
              % (passing, total, pct_pass))
    for k in ("green", "red", "flaky", "automated", "parked", "documented",
              "missing", "not_planned"):
        print("  %-11s %d" % (k, len(buckets[k])))
    if orphans:
        print("  %-11s %d" % ("orphan", len(orphans)))

    needs = (buckets["red"] + buckets["flaky"] + buckets["parked"]
             + buckets["documented"] + buckets["missing"])
    if needs or orphans or caveats:
        print("\nACTION REQUIRED")
        for i, why in buckets["red"]:
            print("  red          %s — a test owns it and the run failed" % i)
        for i, why in buckets["flaky"]:
            print("  flaky        %s — passed on retry; not a pass" % i)
        for i, why in buckets["parked"]:
            print("  parked       %s — only skip/fixme names it (%s)" % (i, why))
        for i, why in buckets["documented"]:
            print("  documented   %s — named in a header, no test owns it (%s)" % (i, why))
        for i, why in buckets["missing"]:
            print("  missing      %s — no spec mentions it%s"
                  % (i, (" (%s)" % why) if why else ""))
        for i in orphans:
            print("  orphan       %s — a spec names it, the case source does not" % i)
        for c in caveats:
            print("  caveat       %s" % c)

    if args.out:
        lines = ["# E2E coverage", "",
                 "- cases: %d (`%s`)" % (total, args.cases),
                 "- specs: %d file(s)" % len(files)]
        if args.report:
            lines.append("- run report: `%s`" % args.report.name)
        lines.append("- **owned by an active test: %d/%d (%.0f%%)**"
                     % (owned, total, pct))
        if args.report:
            lines.append("- **passing in this run: %d/%d (%.0f%%)**"
                         % (passing, total, pct_pass))
        lines.append("")
        lines += ["| bucket | count |", "| --- | --- |"]
        lines += ["| %s | %d |" % (k, len(buckets[k]))
                  for k in ("green", "red", "flaky", "automated", "parked",
                            "documented", "missing", "not_planned")]
        if orphans:
            lines.append("| orphan | %d |" % len(orphans))
        lines.append("")
        headings = {
            "green": "Green — a test owns it and it passed",
            "red": "Red — a test owns it and it failed",
            "flaky": "Flaky — passed only on retry",
            "automated": "Automated — a test owns it, no run evidence",
            "parked": "Parked — only skip/fixme names it (not coverage)",
            "documented": "Documented only — no test owns it (not coverage)",
            "missing": "Missing — no spec mentions it",
            "not_planned": "Marked manual or not-yet in the inventory",
        }
        for k in ("red", "flaky", "missing", "parked", "documented", "automated",
                  "green", "not_planned"):
            rows = buckets[k]
            if not rows:
                continue
            lines += ["## %s" % headings[k], ""]
            for i, why in rows:
                loc = where.get(i)
                at = " — `%s:%d`" % (loc[0].name, loc[1]) if loc and k in (
                    "green", "automated", "red", "flaky") else ""
                lines.append("- `%s`%s%s" % (i, at, (" — %s" % why) if why else ""))
            lines.append("")
        if orphans:
            lines += ["## Orphan IDs in specs", ""] + \
                     ["- `%s` — %s" % (i, ", ".join(sorted(
                         {p.name for group in mentions[i].values() for p, _ in group})))
                      for i in orphans] + [""]
        if caveats:
            lines += ["## Caveats", ""] + ["- %s" % c for c in caveats] + [""]
        args.out.write_text("\n".join(lines), encoding="utf-8")
        print("\nwrote %s" % args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
