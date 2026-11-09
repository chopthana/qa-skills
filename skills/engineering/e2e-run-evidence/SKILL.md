---
name: e2e-run-evidence
description: >
  Run an existing Playwright E2E suite or a scoped test folder, collect that
  run's pass/skip/fail results and screenshots into a separate Excel workbook,
  and build one standalone HTML file that embeds the recorded WebM videos for
  browser playback. Project-agnostic: it hardcodes no suite path, command,
  sheet name or case-ID family, and discovers the project's E2E layout, test
  command, evidence directory and workbook columns at run time — so if a repo
  ships its own evidence skill with those facts baked in, that one wins and
  this one is the portable fallback. Use whenever a user asks to run E2E tests
  and deliver results or evidence in Excel, requests screenshots in a test
  workbook, wants runnable video evidence alongside a workbook, or asks to
  rerun a test folder and gather its output. Do not use to author new test
  cases or to convert source QA cases into Playwright specs; use `cases-to-e2e`
  for that.
disable-model-invocation: true
---

# E2E results → Excel workbook and standalone video viewer

Run only the requested existing tests. Deliver a new workbook whose results
sheet has the columns `ID`, `Topic`, `Expected result`, `Status`, `Reason` and
`Image`, with the outcome also stamped on each case's row of the source sheet,
plus a standalone HTML viewer holding the run videos as embedded WebM data.
Excel does not reliably play WebM attachments or worksheet hyperlinks, so the
HTML companion is the portable video deliverable. It has no external media
dependencies and works offline in any browser with WebM support.

**Nothing here is assumed about the project.** The suite path, the test command,
the evidence directory, the report path, the sheet name, the column letters and
the case-ID family are all discovered or asked for (step 1), and the concrete
values in `> **Worked example**` blocks are one team's answers. If the repo you
are in ships its own evidence skill carrying that project's facts, use that one.

## Workflow

### 1. Discover the suite, the artifacts and the workbook

| What you need | How to find it |
| --- | --- |
| The E2E project root and config | `find . -name 'playwright.config.*' -not -path '*/node_modules/*'` |
| The test command and project name | the E2E package's `package.json` scripts, the lockfile (which package manager), and the config's `projects` (which one is the authenticated project, and which setup project it depends on) |
| Where videos and the JSON report land | the config's `outputDir` and its `reporter` entry. **If no JSON reporter is configured, add `--reporter=list,json` to the run** — the exporter reads JSON, not HTML |
| Where stable screenshots land | the evidence helper in the project's utils fixture; it must write **outside** `outputDir`, which Playwright wipes at the start of every run |
| The source workbook's shape | open it and print the sheet names and the first rows before mapping any column (see below) |
| The case-ID family | read it off the workbook's ID column — it is a required flag, not a default |

```bash
python3 - "<the workbook>" <<'PY'
import sys; from openpyxl import load_workbook
wb = load_workbook(sys.argv[1], read_only=True, data_only=True)
print(wb.sheetnames)
ws = wb[wb.sheetnames[0]]
for i, row in enumerate(ws.iter_rows(max_row=10, max_col=12, values_only=True), 1):
    print(i, [str(c)[:26] if c is not None else "" for c in row])
PY
```

Reuse the repository's conventions; **don't create a second test harness** and
don't move anyone's artifact directories.

### 2. Review side effects before running

Inspect the target specs and fixtures for upload / process / delete / export /
audit / permission changes. Prefer a read-only scope when the request allows
it. If the tests mutate a shared environment, state what the selected tests do
and what state persists or restores **before** starting them. Do not reset or
seed a remote environment unless explicitly asked.

### 3. Prepare a clean artifact run

Keep stable screenshots outside Playwright's `outputDir`. Capture the source
workbook's hash before export, and never write over the source.

### 4. Run the exact requested suite

Include the configured setup-project dependency. **Do not silently narrow the
scope after failures or timeouts.** Report the actual passed / skipped / failed
counts from the run.

### 5. Ask who the tester is, then export

Before generating anything, ask the person whose name goes in the source
sheet's tester column: it is the person who ran the tests and generates the
file, and it is stamped on every case that got a result. **Never guess it** from
the git user or the machine. Pass it as `--tester "<name>"`; the script refuses
to run without `--tester` (or an explicit `--no-tester`, only when the person
said to leave the column blank).

Then run this skill's `scripts/export_e2e_evidence.py` with the source
workbook, the current Playwright JSON report, the stable screenshot directory
and the output workbook. It writes a separate workbook with the exact source
case IDs in source order and preserves untouched OOXML parts. Statuses come
from the current report; a missing screenshot stays a placeholder and never
changes a test result.

What the sheet says, per case:

| Column / sheet | Content |
| --- | --- |
| `Expected result` | the source sheet's expected-result cell (`--expected-col`), so a reviewer reads the outcome next to what the run was meant to confirm |
| `Status` | `Passed` only when the run passed and no bullet is held; otherwise `Not pass`. A case that could not be confirmed — the test failed, was skipped or held as a drift `test.fixme`, or no test in this run carries its ID — is `Not pass`, never a third state |
| `Reason` | empty for a `Passed`; for `Not pass`, the held bullet's drift reason, the cleaned assertion message (expected/received, no call log), or why the case could not be tested (the skip or `NOT TESTED` note, or `Not automated: no test in this run carries this case ID.`) |
| `Image` | the case's input files (pictures of them) stacked above its result frame — see *The input file sits in the Image cell* |
| source sheet, tester column (`--tester-col`) | the `--tester` name, on every case with an outcome (both `Passed` and `Not pass`). A row with no cell in that column gets one, styled like the row's status cell |
| source sheet, status column (`--status-col`) | the pass label of the workbook's own dropdown (`--pass-label`) for a `Passed`, the fail label (`--fail-label`) for a `Not pass` |

`ID`, `Topic`, `Expected result` and `Reason` are aligned top-left with
wrapping; `Status` is centred. Only the source sheet's status, tester and
test-date cells change (their style is kept); every other source cell is
untouched. If the source sheet tints pending rows through a conditional format
keyed on the status cell, a stamped row loses the tint — that is expected.

**A conflict goes into the evidence with its reason.** When a case's bullet is
held because the app contradicts the case (a drift `test.fixme`, per
`cases-to-e2e` § 1), the case's other bullets may all pass — but the case as a
whole is NOT confirmed, so it is `Not pass`, stamped like any other. Its
`Reason` gives the held bullet's reason, and the same note appears above its
video (or its group video) in the viewer. The reason is the fixme's
`{ annotation: { type: 'drift', description } }`: the bullet, what the case
expects, what the app shows, why, and who must rule. Before exporting, check
that every held fixme in scope carries one; add a missing one to the spec and
rerun, because the reason is read from the report.

### 6. Build the video viewer

The same script writes a sibling `<workbook-stem>_videos.html`, embedding the
run's WebM videos for the case IDs in the workbook as data URIs. No video
sidecar directory and no codec conversion is required. A browser with WebM
support is the player; Excel is not.

### 7. Verify before delivery

Confirm that the new sheet has exactly the six headers, that IDs and row order
match the source, that every `Not pass` row has a reason explaining it, that the
source sheet's status column holds the pass label for exactly the `Passed`
cases and the fail label for every other case, and that the tester column (and
test date) holds the given values on exactly those rows. Confirm every held
case's `Reason` gives its drift reason, that a case which read an input file
shows that file above its result in the Image cell, that screenshots are
embedded wherever current-run attachments exist, and that source cells and hash
are unchanged. Check every `<video>` has embedded data, open the HTML in a
browser and play a sample through `timeupdate`, and validate the workbook
ZIP/XML. If no video was captured, say so instead of fabricating one.

**Look at every case image as well.** The asserted value must be in frame,
whole and outlined. A value clipped at a table's scroll edge (`999,999.9` for
`999,999.99`) reads as a product defect. So does an absence case with no
reference showing the item was ever uploaded. Fix either in the spec per
`cases-to-e2e` § 4 (zoom-to-fit, `<CASE-ID>-reference`), rerun, and only then
deliver.

### 8. Deliver both files

Link the `.xlsx` and its sibling standalone `.html`. Explain that video playback
happens in the HTML companion, not inside Excel. Include run counts and state
skips, failures and any shared-environment side effects accurately.

## Commands

Run the suite with the project's own script, then export:

```bash
# in the E2E project directory — <pkg> and the project name come from step 1
<pkg> test --project=<authenticated project> <testDir>/<requested-scope> \
  --reporter=list,json

python3 <skill-dir>/scripts/export_e2e_evidence.py \
  --tester   "<the name the person gave>" \
  --source   "<source workbook>.xlsx" \
  --out      "<source workbook> (automated).xlsx" \
  --sheet    "<the sheet holding the cases>" \
  --tc-prefix "<the case-ID family, e.g. PROMO-CODE>" \
  --report   "<the JSON report path from the config>" \
  --evidence "<the stable screenshot dir>" \
  --video-root "<the config's outputDir>"
```

`--sheet` and `--tc-prefix` are **required and have no defaults** — read both
off the workbook in step 1. `--first-row`, `--id-col`, `--topic-col`,
`--expected-col`, `--status-col`, `--tester-col` and `--date-col` default to one
common layout, so **pass them explicitly** for any workbook whose columns you
have not confirmed match; the exporter exits with
`no IDs matching <prefix>-<number> found in <sheet>` when the mapping is wrong,
which is the signal to go back and read the sheet. Override the viewer path with
`--video-html`. The script refuses to overwrite the source or to duplicate the
results sheet. All workbook and viewer logic lives in this skill's own
`scripts/export_e2e_evidence.py`; no other skill's scripts are used.

For a workbook whose status dropdown is in another language, give the labels it
actually uses:

> **Worked example** — a Thai dropdown reading `รอทดสอบ, ผ่าน, ไม่ผ่าน` needs
> `--pass-label ผ่าน --fail-label ไม่ผ่าน`. An English one may read
> `Pass, Pass with condition, Not pass, Waiting to test`, where the defaults
> already fit. Read the dropdown; don't assume either.

**The input file sits in the Image cell, above the result.** A case's input
evidence is any attachment named `<CASE-ID>-<kind>`, where kind is `excel`,
`csv`, `tsv`, `txt`, `text`, `json`, `input` or `file`, and never a
`-close-up`. The exporter stacks them in the case's Image cell top to bottom:
the input files first (what went in), then the result frame (what came out).
Each picture is scaled to fit, all within 540 px, so the row stays under
Excel's 409 pt limit. Kinds:

- **A picture** (`.png`/`.jpg` — for example the workbook-capture helper's
  `-excel` frame with its marked cells) is embedded as is.
- **A text file or raw body** (CSV, TXT, JSON, a `testInfo.attach` body) is
  drawn into a picture first: a title bar with the file name, line numbers, the
  first 40 lines. It picks a font with Thai glyphs (Tahoma or Thonburi on
  macOS, Tahoma or Leelawadee on Windows, Noto Sans Thai or Garuda on Linux);
  set `E2E_EVIDENCE_FONT` to override it. Without one, Thai draws as boxes and
  the exporter warns.
- **A workbook attached as itself** (`.xlsx`) is skipped with a warning.
  Capture it with the workbook-capture helper instead, which draws the sheet
  and marks the cells the case reads (`cases-to-e2e` § 4).

`--no-input-image` leaves the inputs out. `--update` embeds only the result
frame, and warns which cases also have input pictures.

### Several runs into one workbook

Cases needing different seeded data come from separate runs. Pass each run's
report with its own `--report`. A case takes the last report that ran it; a run
that skipped it, because its data was not seeded there, does not override the
run that did. Playwright empties its output directory at the start of every run,
so copy each run out before the next one, then point that copy's report at its
new home:

```bash
cp -R "<outputDir>" "$KEEP/run-1"
python3 -c "import sys;p=sys.argv[1]+'/report.json';s=open(p).read();open(p,'w').write(s.replace(sys.argv[2],sys.argv[1]))" \
  "$KEEP/run-1" "$PWD/<outputDir>"
# … next seed + run, copied the same way, then:
python3 <skill-dir>/scripts/export_e2e_evidence.py --tester "<name>" --source … --out … \
  --sheet … --tc-prefix … --report "$KEEP/run-1/report.json" --report "$KEEP/run-2/report.json"
```

Regenerating from the original this way keeps every feature: input pictures,
held reasons, held cases recorded (and stamped) as `Not pass`. `--update` does
not. Use this whenever the earlier runs' copies still exist.

### Adding cases to a workbook already delivered

When the source workbook's results sheet already holds earlier runs, pass
`--update` and the delivered viewer as `--base-video-html`. **Don't regenerate
from the original instead**: the earlier runs' screenshots and videos exist only
inside the delivered files, because later runs overwrite the evidence directory.
Reviewers also re-save workbooks in Excel or WPS, which turns them into shared
strings with extra namespaces.

`--update` fills only rows whose status is still pending (`Waiting to test`, or
`Not run` from a workbook delivered before every unconfirmed case became
`Not pass`) and that the current report now covers; it also stamps the source
sheet's status cell, tester and test date for the rows it fills, and reads the
results sheet's columns **by header**, so a workbook delivered with an earlier
four-column layout (`ID`, `Topic`, `Status`, `Image`) is updated in its own
layout. It writes those cells in place (inline strings, style kept), appends
their images to the sheet's existing drawing, and leaves every other row, image
and part byte-identical. The new viewer is the old one's sections,
byte-identical, plus the new cases' sections, in workbook order. A row that
already has a result is never overwritten — rerun without `--update` from the
original workbook to replace results.

```bash
python3 <skill-dir>/scripts/export_e2e_evidence.py --update \
  --source "<workbook> (automated, 001-143).xlsx" \
  --base-video-html "<workbook> (automated, 001-143)_videos.html" \
  --out "<workbook> (automated, 001-171).xlsx" \
  --sheet "<sheet>" --tc-prefix "<PREFIX>" \
  --report "<report.json>" --video-root "<outputDir>"
```

Verify an update by diffing the parts: only the results sheet, its drawing and
the drawing's rels may change, and the new images must be added parts. Check
that IDs, topics and order still match the source. In the viewer, every old
section must be unchanged. A browser pane may refuse a `file://` open from a
downloads folder, so play samples with headless Playwright Chromium from the
E2E project instead.

## Safety and interpretation

- A passed test may have no screenshot if its spec captured none; preserve the
  pass and show `No screenshot captured`.
- Grouped IDs use their test's screenshot and video when available;
  step-specific outcomes take precedence over the parent test outcome. **Don't
  infer a pass from an artifact.**
- A skip-shape annotation marks the named case skipped; a `test.skip` /
  `test.fixme` reason, or an annotation whose type says `NOT TESTED`, becomes
  the row's `Reason`. A workbook ID no test reports is `Not pass` with the
  not-automated reason: an unconfirmed case is not a pass. A drift
  `test.fixme` (a held bullet) likewise makes its case `Not pass`, with the
  drift reason.
- A test that must say why a case was not covered without skipping the test
  (the rest of its grouped cases already ran) pushes
  `test.info().annotations.push({ type: '<CASE-ID> NOT TESTED', description })`.
- The pass label is the workbook's own; nothing is ever written as
  `Waiting to test` — every case ends up either `Passed` or `Not pass`.
- Playwright folder counts are **test** counts, not workbook case-ID counts;
  grouped cases and fixmes/skips make them differ.
- The video HTML contains base64 media and grows with the videos. It is a
  single file, not a streaming viewer; keep the report's video attachments
  available until the viewer has been generated.
- **A silent skip usually means the environment, not the suite.** A spec gated
  on a local URL skips without a word when the env file points the base URL at
  a shared environment; override it inline for that run. A generic server error
  on every processing case is likewise the environment — read the service logs
  before rerunning. `cases-to-e2e` § 3 has both.
- If the run is blocked by missing environment access, authentication, browsers
  or dependencies, **do not claim a completed run.** Finish any export that can
  be truthfully generated from an existing current-run report and say exactly
  which prerequisite blocked new results.
