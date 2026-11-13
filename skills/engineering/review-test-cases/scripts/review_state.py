#!/usr/bin/env python3
"""Remember which artifact page belongs to which workbook.

`--apply` runs in a later session than the one that published the page, so the
artifact URL has to survive outside the conversation. One small JSON file per
workbook, keyed by the workbook's absolute path, kept out of the user's
Test-cases folder so nothing clutters what they share with BA.

Usage:
  python3 review_state.py set --workbook "<path>" --url "<artifact url>"
  python3 review_state.py get --workbook "<path>"
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time

STATE_DIR = os.path.expanduser("~/.cache/qa-skills/review-test-cases")


def resolve(path: str) -> str:
    if not os.path.isfile(path) and not path.lower().endswith(".xlsx") \
            and os.path.isfile(path + ".xlsx"):
        path += ".xlsx"
    return os.path.abspath(path)


def state_path(workbook: str) -> str:
    key = hashlib.sha1(resolve(workbook).encode("utf-8")).hexdigest()[:16]
    stem = os.path.splitext(os.path.basename(resolve(workbook)))[0]
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in stem)[:60]
    return os.path.join(STATE_DIR, f"{safe}-{key}.json")


def load(workbook: str) -> dict:
    p = state_path(workbook)
    if not os.path.exists(p):
        return {}
    try:
        with open(p, encoding="utf-8") as fh:
            return json.load(fh)
    except (ValueError, OSError):
        return {}


def save(workbook: str, **fields) -> str:
    os.makedirs(STATE_DIR, exist_ok=True)
    data = load(workbook)
    data["workbook"] = resolve(workbook)
    data.update(fields)
    data["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    p = state_path(workbook)
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)
    return p


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("action", choices=["set", "get"])
    ap.add_argument("--workbook", required=True)
    ap.add_argument("--url")
    ap.add_argument("--batch", type=int)
    args = ap.parse_args()

    if args.action == "set":
        if not args.url and args.batch is None:
            sys.exit("set needs --url and/or --batch")
        extra = {}
        if args.url:
            extra["artifact_url"] = args.url
        if args.batch is not None:
            extra["last_applied_batch"] = args.batch
        print(save(args.workbook, **extra))
        return 0

    data = load(args.workbook)
    if not data:
        print("")
        sys.exit("no review page recorded for this workbook — publish one first")
    print(json.dumps(data, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
