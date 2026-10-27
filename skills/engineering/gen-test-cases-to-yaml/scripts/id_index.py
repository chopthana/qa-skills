#!/usr/bin/env python3
"""Index the IDs already used in the domain test-case tree.

Usage:
  id_index.py --root DIR [--prefix PREFIX]... [--paths]

Prints every `<PREFIX>-NNN` family found, how many IDs it holds, the highest
counter in use, any gaps, and the next free counter — so a batch conversion can
continue numbering instead of colliding. With --prefix, only those families are
printed (and a family that does not exist yet is reported as free from 001).
"""

import argparse
import re
import sys
from pathlib import Path

ID_LINE_RE = re.compile(r"^\s*(?:-\s*)?id:\s*[\"']?([A-Z0-9][A-Z0-9-]*)[\"']?\s*$")
ID_RE = re.compile(r"^(?P<prefix>[A-Z0-9]+(?:-[A-Z0-9]+)*)-(?P<num>\d{3})$")


def collect(root, skip_example=True):
    families = {}
    malformed = []
    for path in sorted(Path(root).rglob("*.yaml")):
        if skip_example and "example" in path.parts:
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            m = ID_LINE_RE.match(line)
            if not m:
                continue
            case_id = m.group(1)
            parsed = ID_RE.match(case_id)
            if not parsed:
                malformed.append((case_id, str(path)))
                continue
            family = families.setdefault(parsed.group("prefix"), {})
            family.setdefault(int(parsed.group("num")), []).append(str(path))
    return families, malformed


def gaps(numbers):
    present = set(numbers)
    return [n for n in range(1, max(present) + 1) if n not in present] if present else []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, help="the domain test-case tree to index")
    ap.add_argument("--prefix", action="append", default=[])
    ap.add_argument("--paths", action="store_true", help="list the files each family lives in")
    args = ap.parse_args()

    root = Path(args.root)
    if not root.is_dir():
        sys.exit(f"no such directory: {root}")

    families, malformed = collect(root)
    wanted = [p.upper() for p in args.prefix] or sorted(families)

    print(f"# ID index for {root}\n")
    for prefix in wanted:
        family = families.get(prefix)
        if not family:
            print(f"{prefix}: unused — free from 001")
            continue
        numbers = sorted(family)
        dupes = [n for n in numbers if len(family[n]) > 1]
        line = (
            f"{prefix}: {len(numbers)} id(s), max {numbers[-1]:03d}, "
            f"next free {numbers[-1] + 1:03d}"
        )
        missing = gaps(numbers)
        if missing:
            line += f", gaps {[f'{n:03d}' for n in missing]}"
        if dupes:
            line += f", DUPLICATES {[f'{n:03d}' for n in dupes]}"
        print(line)
        if args.paths:
            for path in sorted({p for paths in family.values() for p in paths}):
                print(f"    {path}")

    if malformed:
        print("\n# ids that do not match <PREFIX>-NNN")
        for case_id, path in malformed:
            print(f"  {case_id}  ({path})")

    total = sum(len(f) for f in families.values())
    print(f"\n{len(families)} family/families, {total} id(s) indexed")


if __name__ == "__main__":
    main()
