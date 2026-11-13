#!/usr/bin/env python3
"""Turn review.json into the review page's HTML.

The page has two modes. It opens in **presentation mode** — four columns, no
controls — so the link can be opened in a meeting with BA and PO. The QA who
owns the review flips the "โหมดรีวิว" switch to reveal the per-case verdict
buttons and the note box.

Case text is embedded in the page verbatim: the whole point of the page is that
a reviewer sees exactly what the workbook holds, newlines included. Only the
verdicts live in the artifact's `db`, so Claude can read them back and apply
them to the workbook.

Publish it with `capabilities: {"db": {}, "user": {"scopes": ["profile"]}}`.
The db defaults are what this page wants: everyone admitted reads, Contributor
and above write — so a BA or PO shared in as Viewer gets a read-only page with
no extra rules.

Usage:
  python3 build_review_page.py --input review.json --output review.html
"""
from __future__ import annotations

import argparse
import json
import os

TEMPLATE = r"""<meta name="claude:viewport-fit-sides" content="cover">
<title>__TITLE__</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+Thai:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
/* Layout: masthead, a sticky review bar, then a workbook-like table whose rows
   carry a verdict stripe on the left edge. Stacks to labelled cards on phones. */
:root {
  --paper: #fbfaf7;
  --card: #ffffff;
  --ink: #1b2420;
  --ink-soft: #5c6b63;
  --rule: #ddddd4;
  --accent: #0f5f52;
  --on-accent: #fbfaf7;
  --accent-soft: #e4efeb;
  --pass: #2f7d4f;
  --fix: #9a5a06;
  --ask: #3f4fa8;
  --pass-bg: #e9f4ed;
  --fix-bg: #fdf0dd;
  --ask-bg: #e9ebf8;
  --shadow: 0 1px 2px rgba(27, 36, 32, .06), 0 8px 24px rgba(27, 36, 32, .05);
  --font-ui: "IBM Plex Sans Thai", "Noto Sans Thai", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  --font-mono: "IBM Plex Mono", ui-monospace, SFMono-Regular, Menlo, monospace;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --paper: #141816;
    --card: #1c2220;
    --ink: #e8ece9;
    --ink-soft: #9aa8a1;
    --rule: #2f3835;
    --accent: #6fc9b4;
    --on-accent: #0d1413;
    --accent-soft: #1d2b28;
    --pass: #7fcf9b;
    --fix: #e5b166;
    --ask: #9aa6ef;
    --pass-bg: #1a2a21;
    --fix-bg: #2d2416;
    --ask-bg: #1e2136;
    --shadow: 0 1px 2px rgba(0, 0, 0, .4), 0 8px 24px rgba(0, 0, 0, .3);
    color-scheme: dark;
  }
}
:root[data-theme="dark"] {
  --paper: #141816;
  --card: #1c2220;
  --ink: #e8ece9;
  --ink-soft: #9aa8a1;
  --rule: #2f3835;
  --accent: #6fc9b4;
  --on-accent: #0d1413;
  --accent-soft: #1d2b28;
  --pass: #7fcf9b;
  --fix: #e5b166;
  --ask: #9aa6ef;
  --pass-bg: #1a2a21;
  --fix-bg: #2d2416;
  --ask-bg: #1e2136;
  --shadow: 0 1px 2px rgba(0, 0, 0, .4), 0 8px 24px rgba(0, 0, 0, .3);
  color-scheme: dark;
}

* { box-sizing: border-box }
body {
  margin: 0;
  background: var(--paper);
  color: var(--ink);
  font-family: var(--font-ui);
  font-size: 15px;
  line-height: 1.55;
  -webkit-text-size-adjust: 100%;
}
body::before {
  content: "";
  position: fixed;
  inset: 0 0 auto;
  height: env(safe-area-inset-top, 0px);
  z-index: 10;
  background: var(--card);
}
.wrap {
  padding-left: max(16px, env(safe-area-inset-left, 0px));
  padding-right: max(16px, env(safe-area-inset-right, 0px));
  padding-block: 0 48px;
  max-width: 1500px;
  margin: 0 auto;
}

/* --- masthead ------------------------------------------------------------ */
.masthead { padding-block: 28px 18px }
.card-id {
  font-family: var(--font-mono);
  font-size: 12px;
  letter-spacing: .12em;
  text-transform: uppercase;
  color: var(--accent);
  margin: 0 0 6px;
}
h1 {
  font-size: clamp(21px, 3.4vw, 30px);
  font-weight: 600;
  line-height: 1.2;
  letter-spacing: -.01em;
  text-wrap: balance;
  margin: 0 0 8px;
}
.file {
  font-family: var(--font-mono);
  font-size: 11.5px;
  color: var(--ink-soft);
  word-break: break-all;
  margin: 0;
}

/* --- review bar --------------------------------------------------------- */
.bar {
  position: sticky;
  top: env(safe-area-inset-top, 0px);
  z-index: 9;
  background: var(--card);
  border: 1px solid var(--rule);
  border-radius: 10px;
  box-shadow: var(--shadow);
  padding: 12px 14px;
  margin-bottom: 20px;
  display: flex;
  flex-wrap: wrap;
  gap: 12px 18px;
  align-items: center;
}
.progress { min-width: 170px; flex: 0 0 auto }
.progress .line {
  font-size: 13px;
  color: var(--ink-soft);
  font-variant-numeric: tabular-nums;
  margin-bottom: 5px;
}
.progress .line b { color: var(--ink); font-weight: 600 }
.track { height: 5px; background: var(--rule); border-radius: 99px; overflow: hidden }
.track i { display: block; height: 100%; width: 0; background: var(--accent); transition: width .25s }

.filters { display: flex; flex-wrap: wrap; gap: 6px; flex: 1 1 auto; min-width: 0 }
.chip {
  font: inherit;
  font-size: 12.5px;
  border: 1px solid var(--rule);
  background: transparent;
  color: var(--ink-soft);
  padding: 4px 10px;
  border-radius: 99px;
  cursor: pointer;
  white-space: nowrap;
}
.chip:hover { border-color: var(--accent); color: var(--ink) }
.chip[aria-pressed="true"] {
  background: var(--accent-soft);
  border-color: var(--accent);
  color: var(--accent);
  font-weight: 600;
}
.chip .n { font-family: var(--font-mono); font-size: 11px; opacity: .8 }

input[type="search"] {
  font: inherit;
  font-size: 13px;
  padding: 6px 10px;
  border: 1px solid var(--rule);
  border-radius: 8px;
  background: var(--paper);
  color: var(--ink);
  min-width: 0;
  width: 190px;
}
.toggle { display: flex; align-items: center; gap: 7px; font-size: 13px; cursor: pointer; white-space: nowrap }
.toggle input { accent-color: var(--accent); width: 16px; height: 16px; cursor: pointer }
.send {
  font: inherit;
  font-size: 13px;
  font-weight: 600;
  background: var(--accent);
  color: var(--on-accent);
  border: 1px solid var(--accent);
  border-radius: 8px;
  padding: 7px 14px;
  cursor: pointer;
  white-space: nowrap;
}
.send:hover { filter: brightness(1.08) }
.send:disabled { opacity: .45; cursor: not-allowed; filter: none }
.readonly {
  font-size: 12.5px;
  color: var(--fix);
  background: var(--fix-bg);
  border: 1px solid var(--rule);
  border-radius: 8px;
  padding: 5px 10px;
}

/* --- set-wide findings -------------------------------------------------- */
.globals {
  background: var(--card);
  border: 1px solid var(--rule);
  border-left: 3px solid var(--accent);
  border-radius: 10px;
  box-shadow: var(--shadow);
  padding: 14px 16px;
  margin-bottom: 20px;
}
.globals h2 { margin: 0 0 2px; font-size: 14px; font-weight: 600; display: flex; align-items: baseline; gap: 8px }
.globals h2 .gcount {
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 400;
  color: var(--accent);
  background: var(--accent-soft);
  border-radius: 99px;
  padding: 1px 8px;
}
.ghint { margin: 0 0 12px; font-size: 12.5px; color: var(--ink-soft) }
.glist { list-style: none; margin: 0 0 12px; padding: 0; display: flex; flex-direction: column; gap: 8px }
.glist:empty { display: none }
.glist li {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  background: var(--paper);
  border: 1px solid var(--rule);
  border-radius: 8px;
  padding: 9px 11px;
  font-size: 13px;
}
.glist .gbody { flex: 1 1 auto; min-width: 0 }
.glist .gtextline { white-space: pre-wrap; overflow-wrap: anywhere }
.glist .gmeta { font-size: 11px; color: var(--ink-soft); margin-top: 4px }
.gdel {
  font: inherit;
  font-size: 11.5px;
  border: 1px solid var(--rule);
  background: transparent;
  color: var(--ink-soft);
  border-radius: 6px;
  padding: 2px 8px;
  cursor: pointer;
  flex: 0 0 auto;
}
.gdel:hover { color: var(--fix); border-color: var(--fix) }
.grow { display: flex; gap: 8px; align-items: flex-start; flex-wrap: wrap }
#gtext {
  flex: 1 1 320px;
  min-width: 0;
  min-height: 62px;
  font: inherit;
  font-size: 13px;
  line-height: 1.5;
  padding: 8px 10px;
  border: 1px solid var(--rule);
  border-radius: 8px;
  background: var(--paper);
  color: var(--ink);
  resize: vertical;
}

/* --- table -------------------------------------------------------------- */
.scroller {
  overflow-x: auto;
  border-radius: 10px;
  border: 1px solid var(--rule);
  background: var(--card);
  box-shadow: var(--shadow);
}
table { border-collapse: collapse; width: 100%; min-width: 980px }
thead th {
  position: sticky;
  top: 0;
  background: var(--accent-soft);
  color: var(--accent);
  text-align: left;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: .04em;
  padding: 10px 12px;
  border-bottom: 1px solid var(--rule);
  white-space: nowrap;
}
tbody td {
  vertical-align: top;
  padding: 13px 12px;
  border-bottom: 1px solid var(--rule);
  font-size: 13.5px;
}
tbody tr:last-child td { border-bottom: 0 }
tr[data-v="pass"] > td:first-child { box-shadow: inset 3px 0 0 var(--pass) }
tr[data-v="fix"]  > td:first-child { box-shadow: inset 3px 0 0 var(--fix) }
tr[data-v="ask"]  > td:first-child { box-shadow: inset 3px 0 0 var(--ask) }

.c-no { width: 56px; font-family: var(--font-mono); font-size: 12px; color: var(--ink-soft); font-variant-numeric: tabular-nums }
.c-no .tc { display: block; font-size: 10px; margin-top: 4px; word-break: break-all; line-height: 1.3 }
.c-topic { width: 20%; min-width: 180px; font-weight: 500 }
.c-topic .meta { display: flex; flex-wrap: wrap; gap: 5px; margin-top: 7px }
.badge {
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: .04em;
  border: 1px solid var(--rule);
  border-radius: 4px;
  padding: 1px 5px;
  color: var(--ink-soft);
  font-weight: 400;
}
.c-steps, .c-exp { width: 30%; min-width: 240px }
.cell { white-space: pre-wrap; overflow-wrap: anywhere }
.note {
  margin-top: 10px;
  padding: 8px 10px;
  border-left: 2px solid var(--rule);
  background: var(--paper);
  border-radius: 0 6px 6px 0;
  font-size: 12px;
  color: var(--ink-soft);
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.c-review { width: 200px; min-width: 180px }

/* --- verdict controls --------------------------------------------------- */
.verdicts { display: flex; flex-wrap: wrap; gap: 5px }
.vbtn {
  font: inherit;
  font-size: 12px;
  border: 1px solid var(--rule);
  background: transparent;
  color: var(--ink-soft);
  border-radius: 6px;
  padding: 4px 9px;
  cursor: pointer;
  white-space: nowrap;
}
.vbtn:hover { color: var(--ink); border-color: var(--ink-soft) }
.vbtn[aria-pressed="true"] { font-weight: 600 }
.vbtn[data-k="pass"][aria-pressed="true"] { background: var(--pass-bg); border-color: var(--pass); color: var(--pass) }
.vbtn[data-k="fix"][aria-pressed="true"]  { background: var(--fix-bg);  border-color: var(--fix);  color: var(--fix) }
.vbtn[data-k="ask"][aria-pressed="true"]  { background: var(--ask-bg);  border-color: var(--ask);  color: var(--ask) }
.fixbox {
  margin-top: 8px;
  width: 100%;
  min-height: 92px;
  font: inherit;
  font-size: 12.5px;
  line-height: 1.5;
  padding: 7px 9px;
  border: 1px solid var(--rule);
  border-radius: 7px;
  background: var(--paper);
  color: var(--ink);
  resize: vertical;
}
.who { font-size: 11px; color: var(--ink-soft); margin-top: 6px }
.applied {
  margin-top: 8px;
  font-size: 11.5px;
  color: var(--pass);
  background: var(--pass-bg);
  border-radius: 6px;
  padding: 6px 8px;
}
.applied .diff { color: var(--ink-soft); white-space: pre-wrap; margin-top: 4px; overflow-wrap: anywhere }

body:not(.reviewing) .c-review { display: none }
body:not(.reviewing) tr > td:first-child { box-shadow: none }

button:focus-visible, input:focus-visible, textarea:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}

/* --- submit sheet ------------------------------------------------------- */
.sheet {
  position: fixed;
  inset: 0;
  background: rgba(10, 16, 14, .5);
  display: grid;
  place-items: center;
  padding: max(16px, env(safe-area-inset-left, 0px));
  z-index: 20;
}
.sheet .box {
  background: var(--card);
  border: 1px solid var(--rule);
  border-radius: 12px;
  box-shadow: var(--shadow);
  padding: 22px;
  max-width: 560px;
  width: 100%;
}
.sheet h2 { margin: 0 0 4px; font-size: 18px; font-weight: 600 }
.sheet .sub { margin: 0 0 16px; font-size: 13px; color: var(--ink-soft) }
.tally { display: flex; gap: 18px; flex-wrap: wrap; margin-bottom: 16px }
.tally div { font-size: 13px; color: var(--ink-soft) }
.tally b { display: block; font-size: 22px; font-weight: 600; color: var(--ink); font-variant-numeric: tabular-nums }
.cmd {
  font-family: var(--font-mono);
  font-size: 12px;
  background: var(--paper);
  border: 1px solid var(--rule);
  border-radius: 8px;
  padding: 10px 12px;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  user-select: all;
}
.sheet .row { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 14px }

.empty { padding: 40px 16px; text-align: center; color: var(--ink-soft); font-size: 14px }
.stale { font-size: 12.5px; color: var(--fix); padding: 0 2px }

/* --- phones ------------------------------------------------------------- */
@media (max-width: 760px) {
  .scroller { overflow-x: visible; border: 0; background: transparent; box-shadow: none }
  table, thead, tbody, tr, td { display: block; width: auto; min-width: 0 }
  thead { display: none }
  tbody tr {
    background: var(--card);
    border: 1px solid var(--rule);
    border-radius: 10px;
    box-shadow: var(--shadow);
    margin-bottom: 14px;
    padding: 4px 2px;
  }
  tbody td { border-bottom: 0; padding: 9px 13px; width: auto; min-width: 0 }
  tbody td[data-label]::before {
    content: attr(data-label);
    display: block;
    font-size: 10.5px;
    letter-spacing: .06em;
    text-transform: uppercase;
    color: var(--accent);
    font-weight: 600;
    margin-bottom: 4px;
  }
  tbody tr > td:first-child { box-shadow: none }
  tr[data-v="pass"] { border-left: 3px solid var(--pass) }
  tr[data-v="fix"]  { border-left: 3px solid var(--fix) }
  tr[data-v="ask"]  { border-left: 3px solid var(--ask) }
  .c-no { display: flex; gap: 8px; align-items: baseline }
  /* as a flex item the id would otherwise shrink to one character per line */
  .c-no .tc { margin-top: 0; flex: 1 1 auto; min-width: 0; word-break: normal; overflow-wrap: anywhere }
  input[type="search"] { width: 100% }
  .bar { position: static }
}
@media (prefers-reduced-motion: reduce) { * { transition: none } }
</style>

<div class="wrap">
  <div class="masthead">
    <p class="card-id">__CARD__ · __COUNT__ เคส</p>
    <h1>__PROGRAM__</h1>
    <p class="file">__FILE_NAME__</p>
  </div>

  <div class="bar">
    <div class="progress">
      <div class="line">รีวิวแล้ว <b id="done">0</b> / <b>__COUNT__</b></div>
      <div class="track"><i id="trackfill"></i></div>
    </div>
    <div class="filters" id="filters">
      <button class="chip" data-f="all" aria-pressed="true">ทั้งหมด <span class="n" data-c="all"></span></button>
      <button class="chip" data-f="todo" aria-pressed="false">ยังไม่รีวิว <span class="n" data-c="todo"></span></button>
      <button class="chip" data-f="pass" aria-pressed="false">ผ่าน <span class="n" data-c="pass"></span></button>
      <button class="chip" data-f="fix" aria-pressed="false">แก้ <span class="n" data-c="fix"></span></button>
      <button class="chip" data-f="ask" aria-pressed="false">ถาม BA <span class="n" data-c="ask"></span></button>
      <button class="chip" data-f="applied" aria-pressed="false">แก้แล้ว <span class="n" data-c="applied"></span></button>
    </div>
    <input type="search" id="q" placeholder="ค้นหาข้อความในเคส" autocomplete="off">
    <label class="toggle" for="mode"><input type="checkbox" id="mode"> โหมดรีวิว</label>
    <button class="send" id="send" hidden disabled>ส่งกลับเพื่อแก้ไข</button>
    <span class="readonly" id="readonly" hidden>มุมมองนี้รีวิวไม่ได้ — ดูได้เท่านั้น</span>
    <span class="stale" id="stale" hidden>ยังอ่านผลรีวิวไม่ได้ ที่เห็นอาจไม่อัปเดต</span>
  </div>

  <section class="globals" id="globals" hidden>
    <h2>แก้ทั้งชุด <span class="gcount" id="gcount">0</span></h2>
    <p class="ghint">สิ่งที่ต้องแก้เหมือนกันทุกเคส พิมพ์ครั้งเดียวพอ ไม่ต้องไล่กด แก้ ทีละเคส</p>
    <ul class="glist" id="glist"></ul>
    <div class="grow">
      <textarea id="gtext" placeholder="เช่น step 4 ทุกเคส เปลี่ยนเป็น Click icon view ของกระดานนั้นบนตาราง"></textarea>
      <button class="send" id="gadd">เพิ่ม</button>
    </div>
  </section>

  <div class="scroller">
    <table>
      <thead>
        <tr>
          <th class="c-no">#</th>
          <th class="c-topic">หัวข้อ</th>
          <th class="c-steps">Precondition + Step</th>
          <th class="c-exp">Expected</th>
          <th class="c-review">รีวิว</th>
        </tr>
      </thead>
      <tbody id="rows"></tbody>
    </table>
  </div>
  <p class="empty" id="empty" hidden>ไม่มีเคสที่ตรงกับตัวกรอง</p>
</div>

<script id="case-data" type="application/json">__CASES_JSON__</script>
<script>
(function () {
  "use strict";

  var DATA = JSON.parse(document.getElementById("case-data").textContent);
  var CASES = DATA.cases;
  var WORKBOOK = DATA.source;

  var rowsEl = document.getElementById("rows");
  var emptyEl = document.getElementById("empty");
  var doneEl = document.getElementById("done");
  var fillEl = document.getElementById("trackfill");
  var qEl = document.getElementById("q");
  var modeEl = document.getElementById("mode");
  var sendEl = document.getElementById("send");
  var readonlyEl = document.getElementById("readonly");
  var staleEl = document.getElementById("stale");
  var globalsEl = document.getElementById("globals");
  var glistEl = document.getElementById("glist");
  var gcountEl = document.getElementById("gcount");
  var gtextEl = document.getElementById("gtext");
  var gaddEl = document.getElementById("gadd");

  var review = {};     // slug -> {tc_id, verdict, note, reviewer_id, updated_at}
  var applied = {};    // slug -> {tc_id, before, after, applied_at}
  var globals = {};    // id -> {text, by, created_at} — findings that hit every case
  var names = {};      // reviewer_id -> display name
  var filter = "all";
  var query = "";
  var db = null, userNs = null, myId = "", canWrite = false;
  var lastBatch = 0;

  /* db path segments allow letters, digits and _ - . ~ : @ + only, so a
     TC ID becomes the doc id through here and travels in the body too. */
  function slug(s) {
    return String(s).replace(/[^A-Za-z0-9_\-.~:@+]/g, "_").slice(0, 180) || "_";
  }
  var SLUG = {};
  CASES.forEach(function (c) { SLUG[c.tc_id] = slug(c.tc_id); });

  function lsGet(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function lsSet(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* private window */ } }

  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }
  function clip(s) { s = String(s); return s.length > 240 ? s.slice(0, 240) + "…" : s; }
  function shortTime(iso) {
    var d = new Date(iso);
    return isNaN(d.getTime()) ? "" :
      d.toLocaleString("th-TH", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
  }

  /* --- rows are built once; filtering only hides them ------------------ */
  CASES.forEach(function (c, i) {
    var tr = document.createElement("tr");
    tr.dataset.tc = c.tc_id;
    tr.innerHTML =
      '<td class="c-no" data-label="#">' + (i + 1) +
        '<span class="tc">' + esc(c.tc_id) + '</span></td>' +
      '<td class="c-topic" data-label="หัวข้อ"><div class="cell">' + esc(c.topic) + '</div>' +
        '<div class="meta">' +
          (c.priority ? '<span class="badge">' + esc(c.priority) + '</span>' : '') +
          (c.type ? '<span class="badge">' + esc(c.type) + '</span>' : '') +
          (c.status ? '<span class="badge">' + esc(c.status) + '</span>' : '') +
        '</div></td>' +
      '<td class="c-steps" data-label="Precondition + Step"><div class="cell">' + esc(c.steps) + '</div></td>' +
      '<td class="c-exp" data-label="Expected"><div class="cell">' + esc(c.expected) + '</div>' +
        (c.note ? '<div class="note">' + esc(c.note) + '</div>' : '') + '</td>' +
      '<td class="c-review" data-label="รีวิว">' +
        '<div class="verdicts">' +
          '<button class="vbtn" data-k="pass" aria-pressed="false">ผ่าน</button>' +
          '<button class="vbtn" data-k="fix" aria-pressed="false">แก้</button>' +
          '<button class="vbtn" data-k="ask" aria-pressed="false">ถาม BA</button>' +
        '</div>' +
        '<textarea class="fixbox" id="fix-' + esc(SLUG[c.tc_id]) + '" hidden ' +
          'placeholder="แก้เป็นอะไร / คำถามถึง BA"></textarea>' +
        '<div class="who"></div>' +
        '<div class="applied" hidden></div>' +
      '</td>';
    rowsEl.appendChild(tr);
  });

  var searchIndex = CASES.map(function (c) {
    return (c.tc_id + " " + c.topic + " " + c.steps + " " + c.expected + " " + c.note).toLowerCase();
  });

  function paintRow(i) {
    var c = CASES[i];
    var tr = rowsEl.children[i];
    var r = review[SLUG[c.tc_id]] || {};
    var v = r.verdict || "";

    if (v) { tr.dataset.v = v; } else { tr.removeAttribute("data-v"); }

    var btns = tr.querySelectorAll(".vbtn");
    for (var b = 0; b < btns.length; b++) {
      btns[b].setAttribute("aria-pressed", btns[b].dataset.k === v ? "true" : "false");
      btns[b].disabled = !canWrite;
    }

    var box = tr.querySelector(".fixbox");
    box.hidden = !(v === "fix" || v === "ask");
    box.readOnly = !canWrite;
    if (document.activeElement !== box) { box.value = r.note || ""; }

    var who = tr.querySelector(".who");
    if (r.reviewer_id) {
      who.textContent = (names[r.reviewer_id] || "ผู้รีวิว") +
        (r.updated_at ? " · " + shortTime(r.updated_at) : "");
    } else {
      who.textContent = "";
    }

    var ap = applied[SLUG[c.tc_id]];
    var apEl = tr.querySelector(".applied");
    if (ap) {
      apEl.hidden = false;
      apEl.innerHTML = "✔ แก้แล้ว" +
        (ap.applied_at ? " · " + esc(shortTime(ap.applied_at)) : "") +
        (ap.after ? '<div class="diff">ของใหม่: ' + esc(clip(ap.after)) + "</div>" : "");
    } else {
      apEl.hidden = true;
    }
  }

  function counts() {
    var n = { all: CASES.length, todo: 0, pass: 0, fix: 0, ask: 0, applied: 0 };
    CASES.forEach(function (c) {
      var v = (review[SLUG[c.tc_id]] || {}).verdict;
      if (v === "pass" || v === "fix" || v === "ask") { n[v]++; } else { n.todo++; }
      if (applied[SLUG[c.tc_id]]) { n.applied++; }
    });
    return n;
  }

  function render() {
    var n = counts();
    var reviewed = n.pass + n.fix + n.ask;
    doneEl.textContent = reviewed;
    fillEl.style.width = (CASES.length ? (reviewed / CASES.length * 100) : 0) + "%";
    Object.keys(n).forEach(function (k) {
      var el = document.querySelector('.n[data-c="' + k + '"]');
      if (el) { el.textContent = n[k] ? String(n[k]) : ""; }
    });

    var shown = 0;
    CASES.forEach(function (c, i) {
      var v = (review[SLUG[c.tc_id]] || {}).verdict || "";
      var ok = filter === "all" ? true
        : filter === "todo" ? !v
        : filter === "applied" ? !!applied[SLUG[c.tc_id]]
        : v === filter;
      if (ok && query) { ok = searchIndex[i].indexOf(query) !== -1; }
      rowsEl.children[i].hidden = !ok;
      if (ok) { shown++; }
      paintRow(i);
    });
    emptyEl.hidden = shown !== 0;
    sendEl.disabled = !canWrite || (reviewed === 0 && !Object.keys(globals).length);
  }

  /* --- findings that hit the whole set -------------------------------- */
  function renderGlobals() {
    var ids = Object.keys(globals).sort(function (a, b) {
      return String(globals[a].created_at || "").localeCompare(String(globals[b].created_at || ""));
    });
    gcountEl.textContent = String(ids.length);
    glistEl.innerHTML = ids.map(function (id) {
      var g = globals[id];
      return '<li data-g="' + esc(id) + '">' +
          '<div class="gbody">' +
            '<div class="gtextline">' + esc(g.text) + "</div>" +
            '<div class="gmeta">' + esc(names[g.by] || "ผู้รีวิว") +
              (g.created_at ? " · " + esc(shortTime(g.created_at)) : "") + "</div>" +
          "</div>" +
          (canWrite ? '<button class="gdel" type="button">ลบ</button>' : "") +
        "</li>";
    }).join("");
    gaddEl.disabled = !canWrite;
    gtextEl.readOnly = !canWrite;
  }

  gaddEl.addEventListener("click", function () {
    var text = gtextEl.value.trim();
    if (!text || !canWrite || !db) { return; }
    var id = "g" + Date.now().toString(36);
    var rec = { text: text, by: myId, created_at: new Date().toISOString() };
    globals[id] = rec;
    gtextEl.value = "";
    renderGlobals();
    render();
    enqueue("global_fixes/" + id, function () {
      return db.collection("global_fixes").doc(id).set(rec);
    }).catch(function () {
      delete globals[id];
      renderGlobals();
      render();
    });
  });

  glistEl.addEventListener("click", function (e) {
    var b = e.target.closest(".gdel");
    if (!b || !canWrite || !db) { return; }
    var id = b.closest("li").dataset.g;
    var kept = globals[id];
    delete globals[id];
    renderGlobals();
    render();
    enqueue("global_fixes/" + id, function () {
      return db.collection("global_fixes").doc(id).delete();
    }).catch(function () {
      globals[id] = kept;
      renderGlobals();
      render();
    });
  });

  /* --- filters, search, mode ------------------------------------------ */
  document.getElementById("filters").addEventListener("click", function (e) {
    var b = e.target.closest(".chip");
    if (!b) { return; }
    filter = b.dataset.f;
    var chips = this.querySelectorAll(".chip");
    for (var i = 0; i < chips.length; i++) {
      chips[i].setAttribute("aria-pressed", chips[i] === b ? "true" : "false");
    }
    render();
  });

  var qt;
  qEl.addEventListener("input", function () {
    clearTimeout(qt);
    qt = setTimeout(function () { query = qEl.value.trim().toLowerCase(); render(); }, 150);
  });

  function setMode(on) {
    document.body.classList.toggle("reviewing", on);
    modeEl.checked = on;
    sendEl.hidden = !on;
    globalsEl.hidden = !on;
    readonlyEl.hidden = !(on && !canWrite);
    lsSet("review-mode", on ? "1" : "0");
  }
  modeEl.addEventListener("change", function () { setMode(modeEl.checked); });

  /* --- one write at a time per document ------------------------------- */
  var chains = {};
  function enqueue(key, fn) {
    var prev = chains[key] || Promise.resolve();
    var next = prev.then(fn, fn);
    chains[key] = next.catch(function () {});
    return next;
  }

  function save(tcId, verdict, note) {
    var key = SLUG[tcId];
    var rec = {
      tc_id: tcId,
      verdict: verdict,
      note: note || "",
      reviewer_id: myId || (review[key] || {}).reviewer_id || "",
      updated_at: new Date().toISOString()
    };
    if (verdict) { review[key] = rec; } else { delete review[key]; }
    render();
    if (!db) { return; }
    enqueue(key, function () {
      var ref = db.collection("cases").doc(key);
      return verdict ? ref.set(rec) : ref.delete();
    }).catch(function (err) {
      if (err && err.code === "invalid_argument") {
        canWrite = false;
        setMode(document.body.classList.contains("reviewing"));
      }
      render();
    });
  }

  rowsEl.addEventListener("click", function (e) {
    var b = e.target.closest(".vbtn");
    if (!b || !canWrite) { return; }
    var tcId = b.closest("tr").dataset.tc;
    var cur = (review[SLUG[tcId]] || {}).verdict;
    save(tcId, cur === b.dataset.k ? "" : b.dataset.k, (review[SLUG[tcId]] || {}).note || "");
  });

  var noteTimers = {};
  rowsEl.addEventListener("input", function (e) {
    var box = e.target.closest(".fixbox");
    if (!box || !canWrite) { return; }
    var tcId = box.closest("tr").dataset.tc;
    clearTimeout(noteTimers[tcId]);
    noteTimers[tcId] = setTimeout(function () {
      save(tcId, (review[SLUG[tcId]] || {}).verdict || "fix", box.value);
    }, 700);
  });

  /* --- ส่งกลับ --------------------------------------------------------- */
  sendEl.addEventListener("click", function () {
    var n = counts();
    n.globals = Object.keys(globals).length;
    lastBatch += 1;
    if (db) {
      enqueue("meta/submission", function () {
        return db.doc("meta/submission").set({
          batch: lastBatch,
          submitted_at: new Date().toISOString(),
          by: myId,
          count_pass: n.pass,
          count_fix: n.fix,
          count_ask: n.ask,
          count_global: n.globals
        });
      }).catch(function () {});
    }
    openSheet(n);
  });

  function openSheet(n) {
    var cmd = '/review-test-cases --apply "' + WORKBOOK + '"';
    var sheet = document.createElement("div");
    sheet.className = "sheet";
    sheet.innerHTML =
      '<div class="box" role="dialog" aria-label="ส่งกลับเพื่อแก้ไข">' +
        "<h2>ส่งกลับเพื่อแก้ไขแล้ว</h2>" +
        '<p class="sub">ผลรีวิวถูกเก็บไว้แล้ว วางคำสั่งนี้ใน Claude Code หนึ่งครั้ง ' +
          "เพื่อให้แก้ไฟล์ต้นทางตามที่รีวิว</p>" +
        '<div class="tally">' +
          "<div><b>" + n.pass + "</b>ผ่าน</div>" +
          "<div><b>" + n.fix + "</b>แก้</div>" +
          "<div><b>" + n.ask + "</b>ถาม BA</div>" +
          (n.globals ? "<div><b>" + n.globals + "</b>แก้ทั้งชุด</div>" : "") +
        "</div>" +
        '<div class="cmd" id="cmdtext">' + esc(cmd) + "</div>" +
        '<div class="row">' +
          '<button class="send" id="copy">คัดลอกคำสั่ง</button>' +
          '<button class="chip" id="close">ปิด</button>' +
        "</div>" +
      "</div>";
    document.body.appendChild(sheet);

    function close() { sheet.remove(); }
    function selectCmd() {
      var r = document.createRange();
      r.selectNodeContents(document.getElementById("cmdtext"));
      var s = window.getSelection();
      s.removeAllRanges();
      s.addRange(r);
    }
    sheet.querySelector("#close").addEventListener("click", close);
    sheet.addEventListener("click", function (e) { if (e.target === sheet) { close(); } });
    sheet.querySelector("#copy").addEventListener("click", function () {
      var btn = this;
      try {
        navigator.clipboard.writeText(cmd).then(function () {
          btn.textContent = "คัดลอกแล้ว";
        }, selectCmd);
      } catch (e) { selectCmd(); }
    });
  }

  /* --- first paint, then light up ------------------------------------- */
  setMode(lsGet("review-mode") === "1");
  renderGlobals();
  render();

  var loadTimer = setTimeout(function () { staleEl.hidden = false; }, 10000);
  function settled() { clearTimeout(loadTimer); staleEl.hidden = true; }

  function resolveNames() {
    if (!userNs || !userNs.profiles) { return; }
    var ids = [];
    function want(id) { if (id && ids.indexOf(id) === -1) { ids.push(id); } }
    Object.keys(review).forEach(function (k) { want(review[k].reviewer_id); });
    Object.keys(globals).forEach(function (k) { want(globals[k].by); });
    if (!ids.length) { return; }
    Promise.resolve(userNs.profiles(ids)).then(function (ps) {
      var changed = false;
      ids.forEach(function (id) {
        var nm = (ps && ps[id] && ps[id].name) || "";
        if (nm && names[id] !== nm) { names[id] = nm; changed = true; }
      });
      if (changed) { render(); renderGlobals(); }
    }, function () {});
  }

  (async function () {
    try {
      userNs = await window.claude.use("user");
      if (userNs) {
        canWrite = userNs.can("data.write") !== false;
        try { myId = (await userNs.id()) || ""; } catch (e) { myId = ""; }
      }
    } catch (e) { /* no user namespace in this view */ }

    try {
      db = await window.claude.use("db");
    } catch (e) { db = null; }

    if (!db) {
      canWrite = false;
      settled();
      setMode(document.body.classList.contains("reviewing"));
      render();
      return;
    }

    db.collection("cases").onSnapshot(function (snap) {
      if (!snap.metadata.fromCache) { settled(); }
      var next = {};
      snap.docs.forEach(function (d) {
        var v = d.data();
        if (v) { next[d.id] = v; }
      });
      review = next;
      render();
      resolveNames();
    }, function () { settled(); });

    db.collection("applied").onSnapshot(function (snap) {
      var next = {};
      snap.docs.forEach(function (d) {
        var v = d.data();
        if (v) { next[d.id] = v; }
      });
      applied = next;
      render();
    }, function () {});

    db.collection("global_fixes").onSnapshot(function (snap) {
      var next = {};
      snap.docs.forEach(function (d) {
        var v = d.data();
        if (v && v.text) { next[d.id] = v; }
      });
      globals = next;
      renderGlobals();
      render();
      resolveNames();
    }, function () {});

    db.doc("meta/submission").get().then(function (snap) {
      var v = snap.exists ? snap.data() : null;
      if (v && typeof v.batch === "number") { lastBatch = v.batch; }
    }, function () {});

    setMode(document.body.classList.contains("reviewing"));
    render();
  })();
})();
</script>
"""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", required=True, help="review.json from extract_cases.py")
    ap.add_argument("--output", required=True, help=".html to write")
    args = ap.parse_args()

    with open(args.input, encoding="utf-8") as fh:
        data = json.load(fh)

    card = data.get("card") or ""
    program = data.get("program") or os.path.splitext(data.get("file_name", "เคสทดสอบ"))[0]
    title = ("รีวิวเคส " + card) if card else "รีวิวเคสทดสอบ"

    payload = {
        "source": data["source"],
        "file_name": data["file_name"],
        "card": card,
        "count": data["count"],
        "cases": data["cases"],
    }
    # A literal </script> inside a cell would end the data block early.
    blob = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")

    html = (TEMPLATE
            .replace("__CASES_JSON__", blob)
            .replace("__TITLE__", title)
            .replace("__CARD__", card or "เคสทดสอบ")
            .replace("__PROGRAM__", program)
            .replace("__FILE_NAME__", data["file_name"])
            .replace("__COUNT__", str(data["count"])))

    with open(args.output, "w", encoding="utf-8") as fh:
        fh.write(html)

    print(f"{title} · {data['count']} cases · {len(html):,} bytes -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
