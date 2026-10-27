#!/usr/bin/env python3
"""Validate domain test-case YAML: shape, the five fields, ID format, uniqueness.

Usage:
  validate_cases.py --root DIR [file-or-dir ...] [--skip NAME]... [--id-pattern RE]

  --root DIR       the tree scanned for ID uniqueness (required). With no other
                   path given, every .yaml under it is checked.
  --skip NAME      directory name to ignore, repeatable (default: example)
  --id-pattern RE  override the id format (default: ^[A-Z0-9]+(?:-[A-Z0-9]+)*-\\d{3}$)

Checks, for each file:
  * parses as YAML, root is a mapping
  * either a `cases:` list or a single case at the root — never both shapes,
    and no stray top-level keys in either
  * the five fields are present, correctly typed, and hold no empty strings
  * every id matches the id pattern
  * ids are unique across --root, not just within the files passed in

Exit 0 means clean. Needs PyYAML.
"""

import argparse
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("PyYAML is not installed. Run: pip3 install --user pyyaml")

FIELDS = {"id": str, "scenario": str, "preconditions": list, "steps": list, "expectations": list}
DEFAULT_ID_PATTERN = r"^[A-Z0-9]+(?:-[A-Z0-9]+)*-\d{3}$"


def check_case(case, where, id_re, errors):
    for field, typ in FIELDS.items():
        if field not in case:
            errors.append(f"{where}: missing field `{field}`")
            continue
        value = case[field]
        if not isinstance(value, typ):
            errors.append(f"{where}: `{field}` must be {typ.__name__}, got {type(value).__name__}")
        elif typ is list:
            if not value:
                errors.append(f"{where}: `{field}` must not be empty")
            for i, item in enumerate(value):
                if not isinstance(item, str) or not item.strip():
                    errors.append(f"{where}: `{field}[{i}]` must be a non-empty string")
        elif not value.strip():
            errors.append(f"{where}: `{field}` must not be empty")

    extra = set(case) - set(FIELDS)
    if extra:
        errors.append(f"{where}: unexpected field(s) {sorted(extra)} (a case has only the five)")

    case_id = case.get("id")
    if isinstance(case_id, str) and not id_re.match(case_id):
        errors.append(f"{where}: id `{case_id}` does not match {id_re.pattern}")


def check_file(path, id_re):
    """Return (ids, errors) for one file."""
    errors, ids = [], []
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        return ids, [f"{path}: invalid YAML: {exc}"]
    except UnicodeDecodeError as exc:
        return ids, [f"{path}: not valid UTF-8: {exc}"]

    if doc is None:
        return ids, [f"{path}: file is empty"]
    if not isinstance(doc, dict):
        return ids, [f"{path}: root must be a mapping (a case, or `cases`), got {type(doc).__name__}"]

    if "cases" in doc:
        extra = set(doc) - {"cases"}
        if extra:
            errors.append(f"{path}: a `cases` file must not also have top-level key(s) {sorted(extra)}")
        cases = doc.get("cases")
        if not isinstance(cases, list) or not cases:
            errors.append(f"{path}: `cases` must be a non-empty list")
            cases = []
        for i, case in enumerate(cases):
            where = f"{path}:cases[{i}]"
            if not isinstance(case, dict):
                errors.append(f"{where}: must be a mapping")
                continue
            check_case(case, where, id_re, errors)
            ids.append(case.get("id"))
    else:
        check_case(doc, str(path), id_re, errors)
        ids.append(doc.get("id"))

    return ids, errors


def yaml_files(root, skip):
    return sorted(
        p for p in Path(root).rglob("*.yaml")
        if not any(part in skip for part in p.parts)
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, help="tree scanned for ID uniqueness")
    ap.add_argument("--skip", action="append", default=None, help="directory name to ignore")
    ap.add_argument("--id-pattern", default=DEFAULT_ID_PATTERN)
    ap.add_argument("paths", nargs="*")
    args = ap.parse_args()

    skip = set(args.skip if args.skip is not None else ["example"])
    id_re = re.compile(args.id_pattern)
    root = Path(args.root)
    if not root.is_dir():
        sys.exit(f"--root is not a directory: {root}")

    targets = []
    for p in args.paths or [root]:
        path = Path(p)
        if path.is_dir():
            targets.extend(yaml_files(path, skip))
        elif path.suffix == ".yaml":
            targets.append(path)
        else:
            print(f"skipping non-yaml: {path}")
    targets = sorted(set(targets))

    errors, seen = [], {}
    for path in targets:
        ids, errs = check_file(path, id_re)
        errors.extend(errs)
        for case_id in ids:
            if isinstance(case_id, str):
                seen.setdefault(case_id, []).append(str(path))

    # uniqueness is a property of the whole tree, not of the files passed in
    checked = {p.resolve() for p in targets}
    for path in yaml_files(root, skip):
        if path.resolve() in checked:
            continue
        for case_id in check_file(path, id_re)[0]:
            if isinstance(case_id, str):
                seen.setdefault(case_id, []).append(str(path))

    for case_id, paths in sorted(seen.items()):
        if len(paths) > 1:
            errors.append(f"duplicate id `{case_id}` in {paths}")

    for e in errors:
        print(f"ERROR {e}")
    print(f"{len(targets)} file(s) checked, {len(seen)} unique id(s), {len(errors)} error(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
