# Fixture files, seeded data, and evidence written back

Read this when a case needs a generated upload file, a seeded data population,
or the run's results written back into the source QA workbook. The main
`SKILL.md` covers everything else; none of this is needed for a UI-only case or
one that runs against existing environment state.

## Building fixture workbooks

**Do not hand-craft `.xlsx` by hand, and do not commit a binary nobody can
review.** Look for a generator the repo already has — a spec-driven builder
under its test-data or scenario directory — and invoke it in place rather than
copying or modifying it. Only if there is none, write one that takes a
checked-in JSON/YAML spec and emits the workbook, so the fixture is reviewable
in a diff.

Two things to check before trusting a generator's output:

- **A built-in layout may hardcode one feature's headers.** If the feature
  under test uses a different key column, pass an explicit header list instead
  of naming the built-in layout.
- **Give each fixture file exactly one defect**, so a failing row names its own
  cause.

> **Worked example** — one repo keeps a Go builder invoked as
> `go run . -spec <path>/workbooks.json -out <dir>`, whose default layout
> assumes the key column is `Store code`; a sibling feature keys on
> `Promo code`, so
> its spec supplies `headers` explicitly. Find the repo's own generator and its
> own flags; neither of those is a convention.

## Seeded data

A calculation case may need a seeded data population, not just an input file.
If the repo has a seeding harness, read whatever "expected results" file it
emits and assert **those** numbers instead of deriving your own.

Three traps that recur wherever such a harness exists:

- **Generated artefacts rot.** When the target period is computed relative to
  today (for example "the run month minus two"), every generated artefact goes
  stale and is gitignored. Regenerate before trusting a number.
- **Period length changes the arithmetic.** Thresholds and pro-rata divisors
  depend on the month's length, so a case about a 30-day month, a 31-day month
  and February each need a separately seeded run. Have the spec read the period
  out of the input file and pick its assertion from that, rather than
  hardcoding one month.
- **Seeding usually replaces, not appends.** A `CREATE OR REPLACE`-style seed
  evicts whatever else is in the dataset. Say so before running it, and never
  run it against a shared environment without being asked to.

## Evidence back into the workbook (only if asked)

The sibling skill `e2e-run-evidence` owns this: it reads the Playwright JSON
report plus the stable evidence directory and writes a **new** workbook —
per-case status, reason, input pictures and result frame, with the source
sheet's status/tester cells stamped and every other byte of the source
preserved — alongside a standalone HTML viewer with the videos embedded. Use
it instead of writing a second exporter.

Whichever exporter is used, it can only work if the specs hold up their end:

- Screenshots go to a **stable path named for the case** (`<CASE-ID>.png`),
  **outside Playwright's `outputDir`** — Playwright wipes that directory at the
  start of every run, so evidence from an earlier run disappears when the next
  one starts.
- Get the report as JSON (`--reporter=list,json`).
- If the suite has to run several times (different seeded data, different
  environments), keep each run's results directory and report before the next
  run overwrites it, then pass every report to the exporter. A case takes the
  last report that actually ran it; a run that skipped it must not override the
  run that did.
- A case that was not executed keeps its pending status and gets a reason
  saying why. **Never fabricate a screenshot or a pass.**

### Why workbook write-back is not just openpyxl

An exporter that must preserve a real QA workbook does zip surgery — copying
every part of the source byte-for-byte and rewriting only the few it must. That
is not over-engineering. openpyxl reads only `<xdr:pic>` out of a drawing part
and silently drops every other shape: round-tripping one real QA workbook
through it destroyed text boxes on one sheet, seven rectangles on another, and
an external link's cached values, and the spreadsheet app then showed a repair
dialog on open.

If you extend such a module, two traps cost a debugging round each:

- Overwriting a cell that held a formula leaves `xl/calcChain.xml` stale and
  the app repairs the file. Drop that part and set `fullCalcOnLoad`.
- A cell regex must stop at a self-closing `<c …/>`; a pattern that scans on to
  the next `</c>` swallows the following cell whole. That silently deleted the
  master of a shared-formula group.

After writing a workbook, verify before handing it over: every source part
still present (bar ones you meant to drop), every XML part parses, no cell in
the edited sheet vanished, and no shared formula left orphaned.
