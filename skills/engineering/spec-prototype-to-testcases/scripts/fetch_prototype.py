#!/usr/bin/env python3
"""Inspect a published design prototype and decompile one of its screens.

Works on a prototype built as a Vite SPA: index.html loads an entry bundle; the
entry bundle declares a `routes` array where each route has a slug, a title, and
a lazy `import("./<Screen>-[hash].js")` chunk. This script maps slugs -> chunk
and can download + beautify one chunk so you can read the real screen behavior.

The prototype's base URL is yours to supply — pass --base, or set
PROTOTYPE_BASE_URL. There is no built-in default: a design build belongs to the
team that published it, not to this script.

Usage:
  PROTOTYPE_BASE_URL=https://prototypes.example.com/app/ python3 fetch_prototype.py --list
  python3 fetch_prototype.py --base https://prototypes.example.com/app/ --slug promo-code-settings --out /tmp/proto
  python3 fetch_prototype.py --slug promo-code-settings --strings

No third-party packages needed (stdlib only).
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import urllib.error
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (compatible; spec-prototype-to-testcases)"}


def _get(url: str) -> str:
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        sys.exit("HTTP %s fetching %s — is the base URL right, and the build "
                 "published?" % (exc.code, url))
    except urllib.error.URLError as exc:
        sys.exit("could not reach %s (%s) — check the base URL, your network "
                 "and any VPN the prototype sits behind" % (url, exc.reason))


def _entry_asset(base: str) -> tuple[str, str]:
    """Return (entry_html, entry_asset_filename)."""
    html = _get(base)
    m = re.search(r'src="\./assets/([^"]+\.js)"', html)
    if not m:
        sys.exit("could not find the entry bundle in index.html")
    return html, m.group(1)


def discover_routes(base: str) -> list[dict]:
    _, entry = _entry_asset(base)
    js = _get(base + "assets/" + entry)

    routes: list[dict] = []
    # Each route: {slug:"x",title:"y",...,Component:...import("./Chunk-hash.js")}
    for m in re.finditer(r'slug:"([^"]+)"', js):
        slug = m.group(1)
        window = js[m.start(): m.start() + 4000]
        chunk = None
        cm = re.search(r'import\("\.\/([^"]+\.js)"\)', window)
        if cm:
            chunk = cm.group(1)
        tm = re.search(r'title:"([^"]*)"', window)
        title = tm.group(1) if tm else ""
        routes.append({"slug": slug, "title": title, "chunk": chunk})
    return routes


def beautify(js: str) -> str:
    """Cheap structural pretty-print: break after ; { } and before imports."""
    out = re.sub(r"([;{}])", r"\1\n", js)
    return out


# --------------------------------------------------------------------------- #
# String inventory + typo scan                                               #
# --------------------------------------------------------------------------- #

THAI = "\u0E01-\u0E5B"
# Combining marks that stack on a Thai base character.
TONE = "\u0E48-\u0E4B"
ABOVE = "\u0E31\u0E34-\u0E37\u0E47"
BELOW = "\u0E38-\u0E3A"
MARKS = TONE + ABOVE + BELOW + "\u0E4C-\u0E4E"

_STR_LITERAL = re.compile(
    r'"((?:[^"\\\n]|\\.)*)"' r"|'((?:[^'\\\n]|\\.)*)'" r"|`((?:[^`\\]|\\.)*)`",
    re.S,
)
_TRANSLATION_KEY = re.compile(r"^[a-z0-9_]+(?:\.[a-z0-9_]+)+$")
_PLACEHOLDER = re.compile(
    r"\b(TODO|FIXME|XXX|xxx|Lorem|lorem|undefined|NaN)\b|\[object Object\]"
)
_LOOKALIKE = re.compile("[\u0400-\u04FF\u0370-\u03FF]")


def _unescape(s: str) -> str:
    try:
        return s.encode("utf-8").decode("unicode_escape").encode("latin-1").decode("utf-8")
    except Exception:
        return s


def extract_strings(js: str) -> list[str]:
    """Ordered, de-duplicated UI-looking string literals from a chunk."""
    seen: dict[str, None] = {}
    for m in _STR_LITERAL.finditer(js):
        raw = next(g for g in m.groups() if g is not None)
        if "\\u" in raw or "\\x" in raw:
            raw = _unescape(raw)
        s = raw
        if not s or len(s) > 400:
            continue
        has_thai = re.search("[" + THAI + "]", s) is not None
        # English copy looks like a sentence/label: a space, or an initial capital.
        looks_latin_ui = bool(re.match(r"^[A-Z][A-Za-z]", s)) or (
            " " in s and re.search(r"[A-Za-z]{3}", s) is not None
        )
        if not (has_thai or looks_latin_ui):
            continue
        # Drop obvious code, not copy.
        if re.match(r"^[a-z-]+:[^ ]|^#[0-9a-fA-F]{3,8}$|^[./]|^https?://", s):
            continue
        if re.search(r"[{}<>$]|=>|\bfunction\b", s):
            continue
        seen.setdefault(s, None)
    return list(seen)


def _edit1(a: str, b: str) -> bool:
    """True when a and b are exactly one edit apart."""
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) > len(b):
        a, b = b, a
    i = 0
    while i < len(a) and a[i] == b[i]:
        i += 1
    if len(a) == len(b):
        return a[i + 1:] == b[i + 1:]
    return a[i:] == b[i + 1:]


def scan_suspicious(strings: list[str]) -> list[tuple[str, str]]:
    """(reason, string) pairs worth a human look. Each is a candidate, not a verdict."""
    out: list[tuple[str, str]] = []

    def flag(reason: str, s: str) -> None:
        out.append((reason, s))

    for s in strings:
        if "\u00a0" in s:
            flag("NBSP U+00A0", s)
        for zw, name in (("\u200b", "U+200B"), ("\u200c", "U+200C"),
                         ("\u200d", "U+200D"), ("\ufeff", "U+FEFF")):
            if zw in s:
                flag("zero-width " + name, s)
        if "  " in s:
            flag("double space", s)
        if s != s.strip():
            flag("leading/trailing space", s)
        m = re.search("([" + MARKS + "])\\1", s)
        if m:
            flag("repeated mark U+%04X" % ord(m.group(1)), s)
        if re.search("[" + TONE + "]{2}", s):
            flag("two tone marks in a row", s)
        if re.search("[" + TONE + "][" + ABOVE + "]", s):
            flag("tone mark before a vowel (wrong order)", s)
        if re.search("[" + MARKS + "]", s) and re.match("^[" + MARKS + "]", s):
            flag("string starts with a combining mark", s)
        if re.search(r"\s[,.;:!?]", s):
            flag("space before punctuation", s)
        if re.search(r",[^\s\u0E01-\u0E5B0-9]", s):
            flag("no space after comma", s)
        if _PLACEHOLDER.search(s):
            flag("placeholder / debug text", s)
        if _TRANSLATION_KEY.match(s):
            flag("looks like a translation key", s)
        if _LOOKALIKE.search(s):
            flag("Cyrillic/Greek lookalike character", s)
        if re.search("[\u0E50-\u0E59]", s) and re.search(r"[0-9]", s):
            flag("Thai digits mixed with Arabic digits", s)

    # Same word spelled two ways: one edit apart, both long enough to matter.
    thai = [s for s in strings if re.search("[" + THAI + "]", s) and len(s) >= 4]
    for i, a in enumerate(thai):
        for b in thai[i + 1:]:
            if _edit1(a, b):
                flag("one edit apart from `%s` — one of them is wrong" % b, a)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", default=os.environ.get("PROTOTYPE_BASE_URL"),
                    help="prototype base URL, trailing slash included; "
                         "defaults to $PROTOTYPE_BASE_URL")
    ap.add_argument("--list", action="store_true", help="list routes and chunks")
    ap.add_argument("--slug", help="route slug to decompile")
    ap.add_argument("--out", default="/tmp/proto", help="output dir for the beautified chunk")
    ap.add_argument("--raw", action="store_true", help="save the raw (non-beautified) chunk too")
    ap.add_argument("--strings", action="store_true",
                    help="also dump the screen's UI strings and scan them for typo candidates")
    args = ap.parse_args()

    if not args.base:
        sys.exit("no prototype base URL: pass --base or set PROTOTYPE_BASE_URL "
                 "(e.g. https://prototypes.example.com/app/)")
    if not args.base.endswith("/"):
        args.base += "/"

    if args.list or not args.slug:
        routes = discover_routes(args.base)
        print(f"{'slug':<26} {'chunk':<44} title")
        print("-" * 100)
        for r in routes:
            print(f"{r['slug']:<26} {str(r['chunk']):<44} {r['title']}")
        if not args.slug:
            return 0

    routes = discover_routes(args.base)
    match = next((r for r in routes if r["slug"] == args.slug), None)
    if not match or not match["chunk"]:
        sys.exit(f"slug not found or has no chunk: {args.slug}")

    os.makedirs(args.out, exist_ok=True)
    url = args.base + "assets/" + match["chunk"]
    raw = _get(url)
    raw_path = os.path.join(args.out, match["chunk"])
    if args.raw:
        with open(raw_path, "w", encoding="utf-8") as fh:
            fh.write(raw)

    pretty_path = os.path.join(args.out, f"{args.slug}.pretty.js")
    with open(pretty_path, "w", encoding="utf-8") as fh:
        fh.write(beautify(raw))

    print(f"slug      : {match['slug']}")
    print(f"title     : {match['title']}")
    print(f"chunk url : {url}")
    print(f"pretty    : {pretty_path}")
    if args.raw:
        print(f"raw       : {raw_path}")

    if args.strings:
        strings = extract_strings(raw)
        strings_path = os.path.join(args.out, f"{args.slug}.strings.txt")
        with open(strings_path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(strings) + "\n")

        suspects = scan_suspicious(strings)
        suspect_path = os.path.join(args.out, f"{args.slug}.suspect.txt")
        with open(suspect_path, "w", encoding="utf-8") as fh:
            for reason, text in suspects:
                fh.write(f"{reason}\t{text}\n")

        print(f"strings   : {strings_path} ({len(strings)})")
        print(f"suspects  : {suspect_path} ({len(suspects)})")
        for reason, text in suspects:
            print(f"  [{reason}] {text!r}")
        if not suspects:
            print("  (no typo candidates — still read the strings file yourself)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
