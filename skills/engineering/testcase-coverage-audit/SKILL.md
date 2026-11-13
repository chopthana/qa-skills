---
name: testcase-coverage-audit
description: >
  Audit a test-case set that already exists: find the cases that cannot be run
  as written (an expected result that contradicts itself, two data values in
  one case, an assertion the steps never reach) and the coverage gaps against
  the ticket, the prototype and the shipped code. Use for an existing `.xlsx` /
  CSV / Markdown set and "เคสครบไหม", "เช็คเคสที่เกิดขึ้นได้", "แยกเคสที่
  expected ขัดกันเอง", "coverage พอหรือยัง", "มีเคสซ้ำไหม", or
  /testcase-coverage-audit. Not for writing a new set — that is
  `spec-prototype-to-testcases`.
disable-model-invocation: true
---

# Audit an existing test-case set

A written test case can be wrong in a way that review never catches, because
every line of it reads fine on its own. The failure shows up only when a tester
tries to execute it:

> **Steps** — 6. กรอก ID = 20 หลัก แล้ว Click "สร้าง"  7. เปิด modal ใหม่ กรอก ID = 21 หลัก แล้ว Click "สร้าง"
> **Expected** — 1. กรณี 20 หลัก: บันทึกได้  2. กรณี 21 หลัก: ไม่บันทึก · แสดงข้อความแจ้งว่าให้กรอกไม่เกิน 20 หลัก

Two data sets, two opposite verdicts, one row, one Pass/Fail cell. The tester
cannot record the result. And once you look at the field, the 21-digit branch is
not reachable at all — the input caps at 20, so no "ไม่เกิน 20 หลัก" message ever
appears, and the case fails for a reason that is not a bug.

This skill finds those, and finds what is missing, and leaves the set executable.

## What this skill is not

- Writing a new set from a ticket + prototype → `spec-prototype-to-testcases`.
- Converting a set to YAML / Playwright → `gen-test-cases-to-yaml`, `cases-to-e2e`.
- Running the tests → `e2e-run-evidence`.
- Comparing a design handoff to the app → `design-handoff-check`.

## Ask before you write anything (mandatory)

1. **Where the result goes** — overwrite the same workbook, or write a
   `… (revised).xlsx` beside it. Check for an Excel lock file (`~$<name>.xlsx`)
   and say so if the file is open; overwriting a file Excel holds open gets
   clobbered on save.
2. **TC ID policy for the cases you split out** — continue past the highest
   existing number (traceable to an earlier review), renumber the whole set
   `001–N`, or suffix the parent (`006-a` / `006-b`, which shows where a case
   came from).
3. **Side files** — default is the workbook only. The audit table and the
   open questions go in the chat reply unless the user asks for a file.

Never generate until all three are answered.

## The three sources, and which one wins

Most "missing case" and "wrong expected" findings come from the three sources
disagreeing. Read all three before judging a single case.

| Source | What it is | What it is good for |
| --- | --- | --- |
| **Ticket / spec** | the Jira ACs, field spec, state table | what *should* happen — the expected result |
| **Prototype** | the published design build | the strings as drawn, the flows that exist, what design actually decided |
| **Code** | the shipped implementation | **which states are reachable** — the part no document tells you |

**The spec is the source of truth for expected results.** The code is the source
of truth for *reachability*: whether a tester can get to the state a case
describes. A case whose expected result the spec requires but the code makes
unreachable is not "wrong" — it is a **gap question**: either the code is
missing the rule, or the rule changed and nobody updated the spec. Flag it, keep
the spec's expectation, and ask.

Read the code read-only. Auditing test cases never licenses editing the app.

How to reach each source:

```bash
# prototype: list the screens, then decompile one and dump its strings.
# <proto-skill> is wherever spec-prototype-to-testcases is installed, and the
# base URL comes from the link you were given — the script has no default.
export PROTOTYPE_BASE_URL="https://<the design build's host>/<app>/"
python3 <proto-skill>/scripts/fetch_prototype.py --list
python3 <proto-skill>/scripts/fetch_prototype.py --slug <slug> --strings --out /tmp/proto
```

In the code, the four files that decide reachability for a form screen are the
**validation schema** (what is required, what the max is), the **messages /
labels constant** (the exact strings, and which fields have *no* message), the
**form hook** (when a field unlocks, what a change resets, what the submit path
does on each error), and the **component** (input filtering, disabled states,
what the footer buttons do). Read those four before writing a single finding.

## Workflow

### 1. Extract the set

```bash
python3 <skill-dir>/scripts/audit_testcases.py --input "<workbook>.xlsx"
```

It reads the common two-sheet workbook format (a results sheet whose header
is not row 1 — the layout `spec-prototype-to-testcases` documents), or a CSV
or Markdown table, and prints every case as `id | topic | steps | expected |
note`, then runs the mechanical checks below and prints the candidates.

**Run it twice: `--quiet` for yourself, full output to a file for the
reviewers.** The full dump of a 120-case workbook is the largest thing in this
audit and you need none of it — only the flags, and later the specific cases a
reviewer points at.

```bash
python3 <skill-dir>/scripts/audit_testcases.py --input "<workbook>.xlsx" --quiet
python3 <skill-dir>/scripts/audit_testcases.py --input "<workbook>.xlsx" \
  > "$WORK/cases.txt"
```

`--quiet` gives you the counts, the flagged IDs with their check names, and the
per-check tally. `$WORK/cases.txt` is what §3's reviewers read, off disk.

### 2. Run the mechanical pass

The script flags candidates by pattern. It is a **first pass, not the audit** —
it catches shape, never meaning. Every candidate is read by hand before it
becomes a finding, and the checks it cannot do you do yourself (§3).

| Check | Flags |
| --- | --- |
| `success+failure` | expected asserts both a save and a non-save (`บันทึกสำเร็จ` next to `ไม่บันทึก`) |
| `two-data-values` | two different quantities / values for one field (`20 หลัก` … `21 หลัก`) |
| `case-prefixed` | expected lines that open with `กรณี …:` — one row carrying two scenarios |
| `conditional` | expected hedged with `หาก…`, `ถ้า…`, `(ถ้ามี)` — unverifiable as written |
| `phased` | expected numbered by step phase (`ขั้นที่ 1:` / `ขั้นที่ 2:`) — check it is one progressive flow, not two cases |
| `step-expected-drift` | a value asserted in expected that no step ever enters (the white-badge expected under a pink-badge step) |
| `near-duplicate` | two cases whose topic+steps are ≥85 % similar |
| `overstuffed` | more than 5 expected lines, or expected spanning 3+ fields |
| `clean-note-dirty-expected` | note says `กรณีปกติราบรื่น` while expected carries `⚠️` / `TBC` |
| `unreachable-hint` | expected asserts an error on a field the same case says is `disable` |

### 3. Read for what a machine cannot see

The script cannot read Thai and cannot execute the screen. Someone has to read
every case — but reading cases is bounded, mechanical attention, not judgment,
so **fan it out**.

Dispatch `tc-review` in **chunk-audit** mode, one per ~40 cases
(`model: "sonnet"`, `effort: "high"`). Each gets: `$WORK/cases.txt`, its case-ID
range, the sources the set should agree with, and its own findings path
(`$WORK/findings-<range>.md`). Each returns counts and the flagged IDs — the
findings stay in its file.

Reviewers work within their chunk. **Cross-case contradictions between chunks
are yours**, and so is everything in §4 and §5: a reviewer that only saw cases
001–040 cannot know that 078 disagrees with 012. Collect the per-chunk findings,
then read the flagged cases yourself — by ID, out of `cases.txt` — and rule on
them.

The things to look for, in a chunk or by hand:

- **Internal contradiction in one assertion.** "ช่องรับเฉพาะตัวเลข" and
  "บันทึกไม่ได้เมื่อมีตัวอักษร พร้อมข้อความใต้ช่อง" cannot both be true: if the
  field filters letters out, the submit error is never reached. Pick which one
  the spec means, and split.
- **Unreachable state.** An expected result the tester cannot arrive at:
  a required-error on a field that is still `disable`, a 21st character in a
  field capped at 20, a "ทุกช่องบังคับขอบแดง" where two of the required fields
  have no message defined at all.
- **Step ↔ expected drift.** The steps choose pink, the expected talks about
  white. The steps select only the shift pattern, the expected needs the
  partition too.
- **Cross-case contradiction.** Two cases describing the same state with
  different results — one says the dropdown is "ว่าง", the other says it shows
  "ไม่พบ". Merge them, or make the difference explicit.
- **Silent duplication.** A `[Cancel]` block that re-tests what three earlier
  cases already cover. Keep the specific ones, drop the summary, say so.
- **A rule stated instead of observed.** "การตรวจสอบซ้ำครอบคลุมทุก Partition"
  is a rule, not something a tester sees on screen. Either it has steps that
  demonstrate it or it belongs in the note.

### 4. Find the cases that are missing

Coverage is not "every AC has a case". Walk these, in order, and each one that
produces nothing is worth saying so out loud:

1. **Every AC** → at least one case.
2. **Every field rule** → required-empty, format rejected *at the gate that
   actually rejects it*, length boundary (the highest accepted value and the
   first rejected one, **as separate cases**), duplicate in scope, duplicate out
   of scope, trim, leading zeros, case sensitivity, paste as well as typing.
3. **Every enable/disable gate** → each precondition failing on its own. A field
   unlocked by two conditions needs a case per condition, not one case.
4. **Every reset / cascade** → what a change clears, and what it keeps. These
   two are different cases and the second is almost always missing.
5. **Every exit** → the button, Escape, the backdrop, and the one where the user
   undoes their edit before leaving.
6. **Every error path** → each dialog's *appearance* and what its OK button
   does, as two cases, because they differ (one returns to the form, one closes
   it). Plus the transport failure with no response body.
7. **After-success side effects** → which tab is shown, whether filters and
   paging survive, whether the empty state clears, whether a double-click
   creates two records.
8. **Every loading state** that the code actually has a flag for.
9. **Wording**, one case per state: labels, placeholders, each error message,
   the banner, the toast, dropdown-empty text, column headers. Quote them.
   Include a case that asserts a *neighbouring* feature's words do **not** leak
   in (an edit-mode button in a create modal).
10. **Scope** — a prototype flow the ticket does not mention is a question, not
    a case.

### 5. Report

Deliver the revised workbook path and the case count, then in the reply:

- **Split** — each parent case, what it became, and why in one clause.
- **Corrected** — expected results that contradicted the code's reachability.
- **Merged / dropped** — duplicates, with what survives.
- **Added** — grouped by the §4 bucket that produced them.
- **Open questions** — phrased as decisions for the team, not observations:
  "Should ID (HRIS) be unique across all partitions, or within one?"

## Rules

- **One case = one Pass/Fail.** If a tester cannot put a single verdict in the
  row, it is two cases. This is the whole point.
- **Preconditions keep the team's own shape.** The set you are auditing belongs
  to a team that already writes preconditions one way; a revision that invents
  a second way is a finding you created. Read a recent workbook from the same
  team (not only the one under audit) and match it. The shape in this team's
  sheets is a parenthetical first line in the steps cell, then a blank line,
  then the numbered actions, which begin at the first click:

  ```
  (Precondition มีการ daily sync ตอน 4.00AM โดยมีสาขา C01B เข้ามาในระบบ ประเภท NBA สถานะ รอเปิดทำการ)

  1. เข้าสู่ระบบ
  2. Click กะการทำงานของสาขา
  3. Click ตั้งค่าสาขา
  ```

  The literal word `Precondition`, no colon, prose with `·` between items.
  `1. จัดเตรียม: …` and a set-up sentence folded into step 1 are both drift —
  rewrite them, and say in the report that you did. Take the shape from a
  recent workbook of the same team rather than from this description.
- **A boundary is two cases.** The last accepted value and the first rejected
  one never share a row.
- **Appearance and dismissal are two cases.** A dialog showing up and what its
  button does are different behaviors with different outcomes.
- **Never resolve a disagreement silently.** Spec vs prototype vs code → keep
  the spec's expectation, flag the row, ask the question. There is no quota on
  questions.
- **Never delete coverage to make the count smaller.** A duplicate is merged and
  reported; nothing disappears without a line in the reply.
- **Never edit the app's code.** This skill reads code. It changes test cases.
- **Say what you could not check.** A case that needs branch data you do not
  have, or a native browser control you cannot assert, is called out as such —
  not quietly left to look covered.

## References

- `scripts/audit_testcases.py` — extract a set and run the mechanical pass.
- `references/conflict-patterns.md` — each conflict shape with a real before /
  after split.
- `spec-prototype-to-testcases` — the workbook format, the prototype fetcher,
  and `build_workbook.py` for writing the revised set back out.
