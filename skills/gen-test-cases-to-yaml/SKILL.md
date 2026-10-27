---
name: gen-test-cases-to-yaml
description: Batch-convert a whole folder of QA test-case files (a sprint drop of .xlsx workbooks, CSV, or Markdown) into a repo's own domain test-case YAML tree — translated into English, staged in one folder, reconciled row-by-row so nothing is dropped, then imported in a single pass. Use for "gen-test-cases-to-yaml", "แปลง test case ทั้งโฟลเดอร์", "เอา test cases sprint N เข้า project", "convert the sprint-16 test cases", or any request that points at a directory of test-case files rather than a single document.
---

# Folder of QA test cases → domain YAML (batch import)

One sprint drop in, one import out. The single-document version of this job is
the `testcase-to-domain` skill; this skill is the folder-level pipeline around
it: inventory the whole folder, convert every workbook into a **staging
folder**, prove row-by-row that nothing was lost, then move the staged tree
into the repo **in one pass**.

The target tree's own `README.md` (step 2 finds it, as `$ROOT/README.md`) is
the canonical format. If this skill ever disagrees with it, follow that README
and say so.

## Source folder

The user names the folder, or the sprint it belongs to. With neither, list the
directory their drops live in and ask which one — never guess between sprints.
Many teams keep them per sprint, e.g. `~/Desktop/Test-cases/<team>-sprint-<N>/`.

`scan_folder.py` works out each workbook's layout itself (step 1), so no shape
is assumed here. What to look for in its output:

- a **legend sheet** (status / priority lookup values) — reported as `non-case`,
  correctly ignored
- a **case sheet** whose header is often not row 1, with one row per test case
- a **ticket key**, usually in the filename — the traceability key to carry into
  the YAML header comments

> **Worked example** — CJ Express QA drops are named
> `Test Case - ALC - <ticket> - [People Tech][<area>] <topic>.xlsx`, with a
> `list` legend sheet and a `TestResult` sheet whose header is row 4:
> `ลำดับ` / `ประเภทการทดสอบ` / `TC ID` / `หัวข้อ` /
> `กรณีทดสอบและขั้นตอนการทดสอบ` / `ผลการทดสอบที่คาดหวัง` / `สถานะ` / `Tester` /
> `Test date` / `หมายเหตุ` / `ระดับความสำคัญ` / `Remark for Pass with Condition`.

## Workflow

Work in a staging directory for the whole run; use the session scratchpad
directory (or `<repo>/.test-case-staging/<sprint>` when there is none). Call it
`$STG` below. Nothing lands in the repo until step 6.

### 1. Inventory the folder

```bash
python3 <skill-dir>/scripts/scan_folder.py "<source folder>" \
  --json "$STG/source.json" > "$STG/source.md"
```

`source.json` is the accounting baseline; `source.md` is the full content dump
to convert from — read it, do not re-open the workbooks by hand.

The script exits non-zero when a file is unreadable (password-protected or
legacy-encrypted workbooks are common in these drops, e.g. `CDFV2 Encrypted`).
**Report unreadable files to the user before converting anything** and let them
choose: re-export the file, or proceed without it and leave that ticket for
later. Never let one unreadable workbook stop the other tickets.

Record per file: ticket, sheet, case-row count, total. These numbers are what
step 5 checks against.

### 2. Plan the placement

Where cases live and how IDs are spelled belong to the **target repo**, not to
this skill. Read them out of the tree before planning anything — never carry a
path or an ID prefix over from another project.

```bash
# find the root the repo keeps domain test cases in, and call it $ROOT
find . -type d -name "domain" -path "*test-case*" -not -path "*/node_modules/*"

cat "$ROOT/README.md"                                    # the tree's own format rules, if any
ls "$ROOT"                                               # existing domains
ls -d "$ROOT"/*/*/                                       # existing features
python3 <skill-dir>/scripts/id_index.py --root "$ROOT"   # every ID family in use
```

**`$ROOT/README.md`, where it exists, outranks this skill.** Follow it and tell
the user if the two disagree.

Then write `$STG/plan.md`: one line per source file → target
`<domain>/<feature>/` + ID family + how many cases. Three rules:

- **Reuse before inventing.** The `ls` and `id_index.py` output above *is* the
  vocabulary. Map each workbook onto the existing `<domain>/<feature>/` that
  already holds the same product area; a directory with similar cases in it is
  the answer, however the workbook happens to be named.
- **A genuinely new product area gets a new `<domain>/<feature>/`**, lowercase
  kebab-case, named after the product area the way *the repo* names it — not
  after the workbook's filename or the ticket. Propose the name in the plan
  rather than asking open-endedly; ask only when two existing homes are equally
  plausible.
- **Match the tree's own ID shape.** The sheet owns the ID (next section), but
  where you must coin one, derive it from the placement the way this repo
  already does. `id_index.py` shows whether its families lead with the domain
  (`<DOMAIN>-<FEATURE>-NNN`) or with the feature, and whether they carry a topic
  segment. Match the dominant shape; do not introduce a third.

> **Worked example** — in the CJ Express people-admin repo `$ROOT` is
> `docs/test-cases/domain/`, and the lookup returns domains `configuration/`,
> `permission/`, `incentive/`, `shift/` with families such as
> `CONFIG-INCENTIVE-<VARIANT>`, `PERMISSION-INCENTIVE-<VARIANT>`,
> `AUDIT-INCENTIVE`, `INCENTIVE-<VARIANT>-<TOPIC>`. That is what one repo's
> vocabulary looks like, not a vocabulary to apply elsewhere.

#### The sheet owns the ID

**The workbook's `TC ID` is the case `id`, copied verbatim.** QA tracks runs by
that ID, so a repo ID that differs forces everyone to translate between two
sets of numbers. Do not "improve" a sheet ID: not its prefix, not its spelling,
not its numbering — even when another family in the tree looks tidier. Only
when the sheet cannot supply a usable ID do you ask (below). The source TC ID
always stays in the `# Source:` comment as well, so a case is traceable even
after someone renames it in the sheet.

Four things make a sheet ID unusable. Each one is a **question for the user, not
a decision of yours** — and every question arrives with a concrete proposal:

| What the sheet has | Ask, proposing |
| --- | --- |
| no `TC ID` column, or blank cells | the prefix you would use, derived from the placement (`shift/branch-setting/` → `SHIFT-BRANCH-SETTING-001..0NN`), numbered in sheet-row order |
| one ID reused on several rows (e.g. 15 sorting rows all `Branch-setting-042`) | keeping the first and numbering the rest on from it (`042..056`), or having QA renumber the sheet — say which rows collide |
| an ID that cannot be a case id — lowercase, spaces, no `-NNN` suffix (the format is `^[A-Z0-9]+(?:-[A-Z0-9]+)*-\d{3}$`) | the normalized spelling (`Config-Incentive-Sale-003` → `CONFIG-INCENTIVE-SALE-003`) |
| an ID already used elsewhere in the tree (`id_index.py` reports it) | the next free counter in that family, naming the file that already holds it |

Ask once, for all of them together, with the full list in the question — never
drip-feed one question per row. Put the recommended answer first. Then record
what the user chose in the report, and in `mapping.csv`'s `note` for the rows it
touched.

**Prefer fixing the sheet over diverging from it.** When the user says they will
correct the workbook, wait for it, then re-run step 1 and diff the scan against
the previous `source.json` (rows added/removed, TC IDs changed) before touching
any YAML — a sheet edit can land off by a row. After the fix, `id` and sheet
`TC ID` should be identical for every case; the report says so as a count
(`TC ID == id: 93/93`), which is the number the user actually checks.

### 3. Convert into staging

Write files to `$STG/tree/<domain>/<feature>/<scenario>.yaml`, mirroring
`$ROOT`'s own tree shape, so step 6 is a single move into `$ROOT`.

Group by behavior, not by spreadsheet row order: variants of one rule that
share setup go in one file as a `cases` array; a source row that tests two
behaviors becomes two cases. One file per scenario, lowercase kebab-case.

**Follow the header comment the target tree already uses** — open a neighbouring
file in `$ROOT` and copy its shape. Where the tree has no convention, use this:

```yaml
# Converted from "<source filename>" (sheet <sheet name>)
# Topic: <what this file covers> (TC <first id>..<last id>)
# <one line per translation convention this file relies on>
cases:
  # Source: <ticket> <sheet TC ID>
  - id: "<sheet TC ID, verbatim>"
    scenario: "<the behaviour or rule under test>"
    preconditions:
      - "<data, permission, role, route or starting state>"
    steps:
      - "<one user or system action>"
    expectations:
      - "<one observable result>"
```

Three lines are not optional, whatever the tree's style:

- `# Converted from` — the source filename and sheet, so a reader can go back to
  the workbook.
- `# Source:` above **every** case — the ticket and the sheet's TC ID. This is
  the only place the source ID survives, since the case schema is exactly five
  fields.
- a note naming any convention the file leans on, when the source is not in
  English — e.g. that backticked text is the original-language UI label while
  the prose around it is translated (see step 4).

> **Worked example** — a Thai-language workbook in the people-admin repo
> produces this, where the backticks hold the exact Thai UI labels:
>
> ```yaml
> # Converted from "Test Case - ALC - 2276 - [People Tech][Shift] ตั้งค่าสาขา — Search bar.xlsx" (sheet TestResult)
> # Topic: Branch search bar — code/name field validation (TC SHIFT-BRANCH-SETTING-028..031)
> # Thai text in backticks is the exact UI label / message; English around it is a translation.
> cases:
>   # Source: ALC-2276 SHIFT-BRANCH-SETTING-028
>   - id: "SHIFT-BRANCH-SETTING-028"
>     scenario: "Search by branch code or name (`รหัส / ชื่อสาขา`) with only 3 characters"
>     preconditions:
>       - "A user who can open Branch working shifts (`กะการทำงานของสาขา`) > Branch settings (`ตั้งค่าสาขา`)"
>     steps:
>       - "Log in"
>       - "Click Branch settings (`ตั้งค่าสาขา`)"
>       - "Enter `001` in the branch code/name field"
>       - "Click Search (`ค้นหา`)"
>     expectations:
>       - "An error message is shown under the field, e.g. `ระบุอย่างน้อย 4 ตัวอักษร เช่น 0001 , สีลม...`"
>       - "The branch code/name field is outlined in red"
> ```

Record each row in `$STG/mapping.csv` as you go:

```csv
source_file,sheet,source_row,source_tc_id,new_id,target_path,note
Test Case - ALC - 2276 - ....xlsx,TestResult,5,SHIFT-BRANCH-SETTING-028,SHIFT-BRANCH-SETTING-028,shift/branch-setting/search-field-validation.yaml,
Test Case - ALC - 2276 - ....xlsx,TestResult,20,Branch-setting-042,SHIFT-BRANCH-SETTING-043,shift/branch-setting/column-sorting.yaml,"source TC ID reused on rows 19-33; user approved numbering 042..056"
```

`source_tc_id` and `new_id` are normally the same string — the sheet owns the
ID. They differ only on a row where the user answered one of the questions in
step 2, and that row's `note` says which answer it was. A mapping full of
differing rows means you renamed IDs instead of asking.

`target_path` is relative to the `--staging` directory passed in step 5 (so it
starts at the domain name, with no `domain/` prefix). Two staged files sharing a
basename cannot be told apart otherwise, and `reconcile.py` will reject them.

`source_file` is the basename exactly as `source.json` prints it;
`source_row` is the spreadsheet row from the scan. A row you deliberately do
not convert gets `new_id` = `SKIPPED` and a reason in `note`.

### 4. Translate into English without losing anything

- **English prose, Thai labels verbatim in backticks.** Any UI label, button,
  message, status, placeholder or column name an assertion depends on stays in
  Thai inside backticks, with the English gloss around it:
  `Click Search (\`ค้นหา\`)`. Never translate a label an assertion checks for.
- **A `(Precondition …)` line inside the steps cell is a precondition**, not a
  step. These workbooks routinely open the steps column with the scenario setup
  in parentheses — move it to `preconditions`, keep the numbered lines as
  `steps`, and do not let the steps repeat setup the preconditions already
  assert.
- **An `ข้อมูลเพิ่มเติม` ("additional information") tail in an expected-result
  cell is a rule, not an assertion.** Keep it: either as the expectation's
  reason or as a `#` comment on the case, so the calculation rule survives.
- **Expand numbered cells into list items**, one per line, numbering stripped.
  A `1. / 2. / 3.` expected-result cell becomes several `expectations` items —
  never one blob.
- **Merge every expected-result column** into one `expectations` list.
- **Derive missing preconditions** from what the steps obviously require (role,
  seeded data, route, starting page) and flag them in the report.
- **Expectations are observable assertions**, not implementation details, and
  not one particular rendering guess. `ไม่แสดง table` on a page whose table
  chrome always renders → `No data rows are shown.`
- **Data values are data.** Branch codes, times, headcounts, amounts, dates and
  the BigQuery/source-table names a cell mentions (`MP_Daily_Oper`) belong in
  the case — in `preconditions` when they are setup, in `expectations` when
  they are the assertion.
- **`หมายเหตุ` / `Remark` cells**: if the text adds testable information, turn
  it into a precondition, an expectation, or a `#` comment on the case. Only
  pure run bookkeeping (`กรณีปกติราบรื่น`) may be dropped, and the report says so.
- **Run-tracking columns are excluded by design**: `สถานะ`, `Tester`,
  `Test date`, `ระดับความสำคัญ`, `ประเภทการทดสอบ`. They describe a test run, not
  the case. Name this exclusion once in the report instead of per case.
- Quote YAML values containing `:`, `#`, leading `-`/`{`/`*`, or trailing
  spaces. Thai text with a colon inside a backtick still needs the quotes.

### 5. Reconcile, then validate

Accounting first — this is the gate that makes "nothing dropped" a fact
rather than a claim:

```bash
python3 <skill-dir>/scripts/reconcile.py \
  --source "$STG/source.json" --map "$STG/mapping.csv" --staging "$STG/tree"
```

It fails on any unaccounted source row, any staged case that traces back to no
source row, duplicate IDs, and a `target_path` that does not hold the ID it
claims. Add `--allow-unreadable` / `--allow-skipped` only after the user has
seen and accepted those files and rows.

Then the format gate, against the live tree so IDs are unique repo-wide:

```bash
python3 .agents/skills/testcase-to-domain/scripts/validate.py \
  --root "$ROOT" "$STG/tree"
```

Fix everything both report. Do not proceed to step 6 with either one red.

### 6. Import in one pass

Only once steps 5's gates are green, move the whole staged tree in at once:

```bash
rsync -a "$STG/tree/" "$ROOT"/              # or: cp -R
python3 .agents/skills/testcase-to-domain/scripts/validate.py \
  --root "$ROOT" "$ROOT"
git status --short "$ROOT"
```

Re-run the validator on the merged tree — an ID collision can only appear
after the merge. Check `git status` against your plan: the count of new files
must match, and no existing file may be modified unless the plan said so.

This is a docs-only change, so it goes straight to `main` with one commit for
the whole sprint drop (`docs(test-cases): ALC-2275, ALC-2276, ALC-2426 sprint 16
domain cases`) — no branch, no MR. Ask for the go-ahead before committing.

### 7. Report

- a table: source file → ticket → source case rows → target files → ID range
- how many cases have `id` identical to the sheet's `TC ID`, as a count
  (`TC ID == id: 93/93`), and one row per case where it still differs, with why
- the ID questions you asked and what the user answered (point at
  `mapping.csv` for the row-by-row detail)
- every assumption: new domain/feature names, derived preconditions, cases
  split or merged, reworded expectations, dropped bookkeeping remarks
- files that could not be read, rows deliberately not converted, with reasons
- the run-metadata columns excluded by design

## Never drop a case

Every case row in the inventory ends up either as a staged case in
`mapping.csv` or as an explicit `SKIPPED` row with a reason in the report.
`reconcile.py` enforces it; do not reach for `--allow-skipped` to make a
red gate green. A silent gap is worse than an imperfect conversion — the user
is trusting this pipeline with sprint coverage.

Equally: never invent a case the source does not contain. Padding a thin
workbook is the same failure in the other direction.

## Scripts

Next to this SKILL.md (use the skill base directory shown when the skill loads):

- `scripts/scan_folder.py <folder|file>… [--json OUT] [--format md|none] [--recursive]`
  — extracts every case row from .xlsx/.xlsm/.csv/.tsv; maps Thai and English
  column headers by meaning; resolves merged cells; flags unreadable files with
  remediation. Exit 1 if any file is unreadable.
- `scripts/id_index.py [--root DIR] [--prefix P]… [--paths]` — ID families
  already in use, max counter, gaps, next free counter, duplicates.
- `scripts/reconcile.py --source source.json --map mapping.csv --staging DIR`
  — source-row ↔ mapping ↔ staged-YAML accounting. Exit 0 = nothing lost.

Reused from the `testcase-to-domain` skill, which lives **inside the
people-admin repo**, not next to this skill. Both paths are relative to that
repo's root, so run them from there:

- `.agents/skills/testcase-to-domain/scripts/validate.py` — the five-field
  schema, shape, ID format and tree-wide uniqueness gate.
- `.agents/skills/testcase-to-domain/scripts/read_xlsx.py` — raw whole-sheet
  dump, for when a workbook's layout defeats `scan_folder.py`'s header
  detection.

In a repo that has no `testcase-to-domain`, `reconcile.py` still gates the
no-loss accounting, but the schema gate is missing: check the five fields and
ID uniqueness another way and say in the report that you did.
