---
name: spec-prototype-to-testcases
description: >
  Turn a Jira / PRD feature spec plus its published design prototype into a QA
  test-case workbook in your team's own `.xlsx` template. Reads the spec for
  rules and acceptance criteria, decompiles the deployed prototype bundle for
  the real screen behavior, validates wording and scans the prototype's strings
  for typos. Use whenever someone hands over a ticket and a prototype link
  (…/#<slug>) and asks for test cases, test scenarios, a QA sheet, or coverage
  "ตาม spec" — even if they never name the format. A big feature hands the
  case-writing to `subagent-driven-testcases`, with this skill as its producer.
disable-model-invocation: true
---

# Spec + prototype → Test Case workbook

Produce QA test cases from **two sources that must be compared**:

1. **The spec** — the Jira story / PRD / acceptance criteria pasted or linked.
2. **The prototype** — the deployed design build, a Vite SPA whose screens are
   lazy-loaded JS chunks keyed by route slug. **Its base URL is an input, not a
   constant**: take it from the link the user sent (trim back to the root
   before the `#`), or ask. Set it once per session as `PROTOTYPE_BASE_URL` so
   every script call below picks it up.

The spec says what *should* happen; the prototype shows what was actually built.
They disagree more often than not. This skill keeps them separate, states each
difference as an **open question for the team** instead of silently picking one,
and still ships the workbook so work can start.

Output: **just the `.xlsx`**, mirroring your team's own test-case template
exactly (see `references/template-format.md`). Cases not answerable yet get
flagged in the note column.

**The workbook is the only default deliverable.** The JSON case source and the
gap report are **optional** — ask before creating them (§ Ask before you
generate). Do not write extra files unprompted. Test cases are reviewed first,
then (separately) fed to `gen-test-cases-to-yaml`; this skill stops at the
reviewable workbook.

## When not to use this

- Converting an existing workbook / CSV / YAML to another format → use
  `testcase-to-domain` (YAML) or `cases-to-e2e` (Playwright).
- Running tests or collecting evidence → `e2e-run-evidence`.

## Ask before you generate (mandatory)

**Always ask the user before naming the file or the cases — never assume.**
Ask these questions first (use the AskUserQuestion tool), then generate:

1. **File name** — follow the team's own convention, which you **discover
   rather than assume**: list the folder their existing workbooks live in and
   copy the pattern off the neighbours. Propose the name you will use from the
   ticket and ask the user to confirm or correct the ticket key and the card
   name.

   > **Worked example** — one team names them
   > `Test Case - <TRACKER> - {ticket_no} - {card_name}.xlsx`, e.g.
   > `Test Case - QAP - 1041 - [Catalog][Promo] ตั้งค่ารหัสโปรโมชัน — Add Promo Code.xlsx`.
   > Another drops the prefix entirely. Read the folder, don't carry this one
   > over.
2. **TC ID prefix** — propose a prefix (see `references/template-format.md`
   § TC ID conventions) and ask the user to confirm it or pick another. Offer
   the suggested prefix as the first option.
3. **Optional side files** — the default is to write **only the `.xlsx`**. Ask
   whether the user also wants the optional helpers:
   - the **JSON case source** (`*.cases.json`) — lets the workbook be regenerated
     or later converted; not needed for review.
   - the **gap report / open questions** (`*.gap-and-questions.md`) — the
     spec-vs-prototype differences and questions for the team.

   Offer "workbook only (recommended)" as the first option. If the user does not
   ask for them, keep the questions inside the workbook's note column and
   mention the gaps in the chat reply instead of writing files.

Only start generating once these are answered. If the user already stated either
in their message, still confirm the others.

## Workflow

### 1. Collect the two sources

- **Spec**: read it verbatim. If a URL, fetch it; if pasted, use the text. Pull
  out every **acceptance criterion (AC)**, every **field rule** (required,
  format, duplicate/uniqueness scope, defaults), and every **state/edge-case**
  row. These become cases directly.
- **Prototype**: identify the route slug (e.g. `promo-code-settings`) from the
  hash the user gave. Then:

  ```bash
  # the prototype's root, taken from the link the user sent — once per session
  export PROTOTYPE_BASE_URL="https://<the design build's host>/<app>/"
  # list routes + chunk map from the entry bundle
  python3 <skill-dir>/scripts/fetch_prototype.py --list
  # decompile one screen (downloads + beautifies its chunk)
  python3 <skill-dir>/scripts/fetch_prototype.py --slug promo-code-settings --out /tmp/proto
  ```

  Without that variable (or `--base`) the script stops and says so — it ships
  with no default host.

  The script prints the route's title, its chunk URL, and a beautified copy at
  `/tmp/proto/<slug>.pretty.js`. Read it for: exact labels, defaults, option
  lists, the option-filtering logic, validation banners/messages, and which
  flows exist (create vs edit).

  **A beautified chunk is tens of thousands of lines of machine-generated
  JavaScript and it is the biggest thing in this skill.** Never open it whole.
  Go at it with `grep -n` for what you actually need — the label, the message,
  the option array, the `required`/`maxLength`/`disabled` near a field name —
  and read the twenty lines around each hit:

  ```bash
  grep -n -E '"[^"]*(ต้อง|ไม่|สำเร็จ|ผิดพลาด)[^"]*"' /tmp/proto/<slug>.pretty.js | head -40
  grep -n -E 'maxLength|required|disabled|defaultValue|options:' /tmp/proto/<slug>.pretty.js | head -40
  ```

  The `--strings` dump below is the cheaper path to every label, so reach for
  the chunk only for **behavior** the strings cannot tell you.

  Add `--strings` to also dump every UI string in that chunk and scan it for
  typo candidates — see § 3.

### 2. Build a traceability matrix

For each spec item, record what the prototype does. Classify:

| Class | Meaning |
| ----- | ------- |
| **match** | Prototype implements the rule — case asserts spec behavior |
| **gap** | Prototype misses/differs — case still asserts **spec**, and the row is flagged |
| **extra** | Prototype has something the spec does not (e.g. an edit flow) — raise as a scope question |

Write this matrix into the workbook's header area or a `Gap & Questions` sheet
(see below). **Never** silently resolve a mismatch.

### 3. Check the wording and hunt typos

A case that asserts "แสดงข้อความ error" asserts nothing. Wording is the part of a
screen QA *can* check and nobody does — so **every string the user reads is either
asserted in a case or raised as a question**, and each string is checked for typos
*before* it is copied into an expected result.

Dump the screen's strings and scan them:

```bash
python3 <skill-dir>/scripts/fetch_prototype.py --slug <slug> --strings --out /tmp/proto
```

It writes `<slug>.strings.txt` (every UI string in that chunk, de-duplicated) and
`<slug>.suspect.txt` (candidates + reason), and prints the candidates.

**The scanner is a first pass, not the check.** It catches only what a machine can:
NBSP and zero-width characters, double or trailing spaces, repeated or misordered
Thai tone marks, space before punctuation, placeholders and translation keys that
leaked into labels (`TODO`, `[object Object]`, `common.button.save`),
Cyrillic/Greek lookalikes, Thai digits mixed with Arabic, and two strings one edit
apart (the same word spelled two ways). **It cannot read Thai — read
`<slug>.strings.txt` line by line yourself** for:

- ตัวสะกดผิดที่ยังอ่านออก — ตัวสะกดเสียงใกล้กัน (`น`/`ล`, `ร`/`ล`, `ศ`/`ษ`/`ส`),
  ตัวการันต์หาย, สระหายไปหนึ่งตัว
- คำเดียวกันที่ spec กับ prototype สะกดไม่เหมือนกัน
- ศัพท์ที่ความหมายเพี้ยน หรือคำที่ไม่มีที่อื่นในระบบใช้
- label ที่อ่านแล้วไม่รู้ว่าหมายถึงอะไร
- ตัวพิมพ์ใหญ่/เล็กไม่คงเส้นคงวาในคำเดียวกันคนละที่
- หน่วยหรือเครื่องหมายที่หาย — `%`, สกุลเงิน, จุดทศนิยม, ตัวคั่นหลักพัน

**Scope caveat:** `--strings` reads *that screen's chunk only*. Strings owned by
shared components (pagination, toasts, date picker) live in other chunks, so a
label missing from the dump is **not** proof the screen does not show it — check
the rendered screen before calling it absent.

Then decide per string, and **never silently pick a side**:

| Where the typo is | What goes in the workbook |
| --- | --- |
| prototype only; spec spells it right | assert the **spec** spelling; the note column flags the prototype typo as a UI bug |
| spec only; prototype spells it right | assert the **prototype** spelling; the note column says the spec has the typo |
| both agree, but it reads wrong | assert the text **as built**; the note column carries the question — do not "fix" it in the expected result |
| cannot tell which was intended | expected result quotes what is built; note-column marker + the question |

**ถ้ามันไม่สมเหตุสมผล ให้ตั้งคำถามเสมอ** A wording question costs one line in
the note column and one sentence in the reply. Guessing costs a test case that asserts
the wrong string — and then gets "fixed" by changing the app. There is no quota on
questions.

### 4. Expand into cases

**Above about 20 cases, hand this step to `subagent-driven-testcases`.** That
skill is the fan-out controller for exactly this shape of work — it surveys the
sources into one inventory, cuts disjoint slices, dispatches an author per slice
and merges with one seat owning the IDs. It drives **this** skill as its
producer, so the case format and the rules below still govern; what changes is
who holds them in context.

Hand it: the traceability matrix from §2, the strings and suspect files from §3,
the intake answers you already collected, and this SKILL.md as the producer. It
needs them because an author never goes looking for a value itself.

Below that threshold, slicing costs more than it saves — write the cases here.
Either way the coverage sources are the same, in this order:

1. **Every AC** → at least one case each.
2. **Every field rule** → required-empty, format, duplicate-in-scope,
   duplicate-out-of-scope, trim, default-absent.
3. **Every screen state / edge case** in the spec's State table.
4. **Happy path** end-to-end.
5. **Reasonable additions** — behavior the spec implies but does not spell out
   that a tester would try (e.g. boundary values, mixed-scope duplicates,
   refresh-after-create). The user explicitly wants these added.
6. **Wording** → assert the exact string for every button and field label, every
   validation / error message, the empty-state heading *and* its sub-text, the
   result-count line, every column header, and every option in a dropdown. Quote
   them, never paraphrase: `ตรวจสอบว่าแสดงข้อความ "ไม่พบข้อมูล" และ
   "โปรดตรวจสอบรายละเอียดการค้นหา"`. One wording case per state is enough — do
   not write a case per label.

**Do not invent features the spec/Jira does not mention.** If the prototype has
them (edit flow, filters, tabs) but the ticket does not, they are **out of
scope** — capture them in the gap report / open questions, not as cases, unless
the user asked to include the listing screen.

### 5. Write the workbook

Use the **file name and TC ID prefix the user confirmed** in "Ask before you
generate". The generator always needs the cases as JSON, but **that JSON is a
build input, not a deliverable**: by default write it to a temp path, generate
the workbook, and delete the temp file. Keep a `*.cases.json` next to the
workbook **only if the user opted into the optional side file**.

The generator reproduces the template: frozen panes, yellow header, borders,
the `ลำดับ` formula, the `ประเภทการทดสอบ` dropdown from the `test` named range,
the priority dropdown from `list!$D$1:$D$3`.

```bash
# write cases to a temp json, build the workbook (default: workbook only)
python3 <skill-dir>/scripts/build_workbook.py \
  --input  "$TMP/cases.json" \
  --output "<the file name the user confirmed>.xlsx" \
  --program "<Program name shown in F2>"
```

If (and only if) the user asked for the JSON source, write `cases.json` to its
final path and build from there instead.

`cases.json` shape (see `references/template-format.md` for every option):

```json
{
  "program": "ตั้งค่ารหัสกะการทำงาน",
  "type": "System Test",
  "cases": [
    {
      "tc_id": "PROMO-CODE-SETTING-001",
      "topic": "ตรวจสอบการเปิด modal เพิ่มรหัสกะ",
      "steps": ["เข้าสู่ระบบ", "Click กะการทำงานของสาขา", "Click ตั้งค่าหน่วยงาน"],
      "expected": ["สดง modal ...", "..."],
      "note": "กรณีปกติราบรื่น",
      "priority": "Medium",
      "status": "Waiting to test"
    }
  ]
}
```

Field rules:

- `tc_id` — stable, `<AREA>-<FEATURE>-NNN`, mirroring the ID family the
  team's existing sheets already use (read one before you coin a new prefix).
  **Use the prefix the user confirmed** and never reuse a number.
- `steps` / `expected` — arrays; the generator numbers them `1.`, `2.`, … with
  newlines, matching the source workbooks.
- **A precondition is never a numbered step.** The team's workbooks put the
  state that must already exist in a parenthetical first line of the steps
  cell, then a blank line, then the numbered actions — and the actions start
  from the first click a tester makes:

  ```
  (Precondition มีการ daily sync ตอน 4.00AM โดยมีสาขา C01B เข้ามาในระบบ ประเภท NBA สถานะ รอเปิดทำการ)

  1. เข้าสู่ระบบ
  2. Click กะการทำงานของสาขา
  3. Click ตั้งค่าสาขา
  ```

  So pass `steps` as a **string** in that shape whenever a case needs set-up
  data, and as an array only when it needs none. One parenthesis, the literal
  word `Precondition`, no colon, prose with `·` between items — never
  `1. จัดเตรียม: …`, never a `Pre-condition:` label, never set-up folded into
  step 1. Read a recent workbook from the same team before you write the first
  case and copy the shape you find there.
- `note` (the note column) — `กรณีปกติราบรื่น` for normal cases; for a flagged case
  start with a marker, e.g. `⚠️ TBC Q2: ID (HRIS) duplicate scope`. A wording
  finding names both spellings and which side it is on, e.g.
  `⚠️ TYPO: prototype `<as built>` / spec `<as specified>` — asserting spec`.
- `priority` — `High` / `Medium` / `Low`. `status` — default `Waiting to test`.

### 6. Report back

Deliver: the **workbook path** and the case count. Also state the
**typo / wording findings** (what the scanner flagged, what reading the strings
turned up, and which side each one is on) and the
**spec↔prototype gap report / open-questions list** — in the chat by default,
or in a `*.gap-and-questions.md` file only if the user opted into that side
file. The user will take the questions to the team, so phrase each one as a
decision ("Should ID (HRIS) be unique across all Partitions, or within a
Partition?").

## Rules

- **Workbook only by default.** Produce just the one `.xlsx`, named by the
  convention you read off the team's existing workbooks. The JSON source and
  the gap report are optional — ask first, and write them only if the user
  says yes.
- **Ask before naming.** Never generate until the user has confirmed the
  workbook file name, the TC ID prefix, and whether they want the optional
  side files. Always offer your
  suggestion and let them pick.
- **Spec is the source of truth for expected results.** A prototype that
  disagrees is a bug or a decision, never the assertion — unless the user says
  otherwise. Flag, don't silently follow the prototype.
- **Thai wording is reproduced verbatim** from the spec/prototype inside quotes;
  do not retranslate a label that an assertion depends on. Verbatim means
  character-for-character — **but a string that has a typo in it is flagged in
  the note column, never copied in as though it were correct** (§ 3).
- **Wording is coverage, not polish.** "แสดงข้อความ error" is an incomplete
  expected result; quote the message. Every user-visible string on the screen is
  asserted somewhere or listed as a question.
- **Never edit a typo away silently.** Correcting the spelling inside an expected
  result hides the bug, and makes the case wrong if the team decides the built
  text stays.
- **One case = one behavior.** Split a case that tests two rules.
- **Flag, never drop.** Every AC, field rule, and edge case in the spec is
  either a case or explicitly listed as covered elsewhere / not testable.
- **Keep scope to the ticket.** Out-of-ticket prototype features are questions,
  not cases.

## References

- `references/template-format.md` — the exact workbook layout (sheets, columns,
  named range, data validation, styles) and the `cases.json` schema.
- `scripts/fetch_prototype.py` — list routes / decompile a screen chunk;
  `--strings` dumps that screen's UI strings and flags typo candidates.
- `scripts/build_workbook.py` — write the `.xlsx` from `cases.json`.
- `evals/evals.json` — smoke expectations for the generator.
