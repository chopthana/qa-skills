---
name: cases-to-e2e
description: >
  Turn QA test cases — a "Test Result" workbook, CSV/Markdown, or a repo's own
  domain test-case YAML — into runnable Playwright specs inside the project's
  existing E2E project, run them against the environment the project points at,
  and hand back reviewable evidence (watchable video with marked clicks,
  key-moment and close-up screenshots in the HTML report, optionally pass/fail
  written back into the source workbook). Project-agnostic: it hardcodes no
  paths, commands or environments, and discovers the target project's E2E
  layout, package manager, locator strategy and precedent specs at run time —
  so if a repo ships its own E2E skill with the project's facts baked in, that
  one wins and this one is the portable fallback. Use this whenever the user
  hands over a test-case or Test Result file in any format, asks to automate
  test cases or add E2E coverage, asks to run or re-run a case, points at a
  test-case YAML, or wants screenshot/video evidence per case — even when they
  just paste the cases into chat without naming a skill or format.
disable-model-invocation: true
---

# Test cases → Playwright E2E

Two jobs, in order: **agree on scope first, then build.** Most of the cost of
getting this wrong is spent writing specs against the wrong assumptions, so the
intake is not optional ceremony — it is the part that saves the work. The human
stays in the loop at three points: which cases to automate, ambiguities you
could not resolve from the code yourself, and the final results.

Nothing below assumes a directory layout, a package manager or an environment.
**Every path and command in this skill is discovered from the repo you are
in** (§0), and the concrete values in `> **Worked example**` blocks are one
team's answers, not the rule. If the repo you are in ships its own E2E skill
carrying that project's facts, **use that one** — this is the portable
version, and a project-specific sibling outranks it.

## When not to use this

- Writing cases from a spec, a screenshot or a design prototype → the
  case-authoring skills (`create-test-cases-spec`,
  `spec-prototype-to-testcases`).
- Converting a case set into a repo's domain YAML → `gen-test-cases-to-yaml`.
- Running an existing suite and collecting its results into a workbook plus a
  video viewer → `e2e-run-evidence`. This skill authors; that one reports.
- A whole feature's worth of cases, too big for one context →
  `subagent-driven-testcases` drives this skill slice by slice.

## 0. Discover the project's E2E conventions

Read before you plan. Nothing here is assumed; all of it is in the repo.

| What you need | How to find it |
| --- | --- |
| Whether an E2E project exists at all | `find . -name 'playwright.config.*' -not -path '*/node_modules/*'`. More than one hit means more than one harness — ask which is canonical. None means scaffolding, which needs the user's agreement first (`references/scaffold-e2e.md`) |
| Where specs live, and the project names to run | the config's `testDir`, `projects`, `webServer`, `outputDir`, `use.baseURL` |
| How specs are wired | open the newest spec in the suite: its imports tell you whether fixtures are composed in one barrel file, where page objects live, and what the shared utils fixture already offers |
| Route/URL helpers | grep the spec for how it navigates — a route builder, a constants file, or raw strings. If the project has a whitelist, a new route must be added there or the helper will not compile |
| Fixture assets | the directory the existing specs resolve upload files from, and its README |
| Credentials and environment | the gitignored env file plus its committed `*.example` twin — read the example, never the real one |
| Commands | the E2E project's `package.json` scripts (`test`, `lint`, `check:types` or their local names) and the lockfile, which names the package manager |
| Case sources already in the repo | frozen BDD/test-case docs, a domain YAML tree, a `brief.md` per case. Read for context; treat generated or frozen trees as read-only |
| House rules | the repo's own agent/contributor docs (`AGENTS.md`, `CLAUDE.md`, `CONTRIBUTING.md`) and the E2E project's README. **They outrank this skill** |

Then read the **closest precedent spec** — the existing spec whose shape your
cases need (upload→process→result, a permission suite, a read-only grouped
suite) — and imitate it. A precedent in the repo beats any pattern here.

> **Worked example** — one monorepo keeps E2E in a root `e2e/` project of its
> own (specs in `e2e/tests/<feature>/`, page objects in `e2e/fixtures/pages/`,
> a route whitelist in `e2e/helpers/routePath.ts`, assets in
> `e2e/assets/<feature>/`), and its contributor docs forbid a second harness
> inside the frontend package. Another repo keeps a flat `tests/` beside
> `playwright.config.ts` with no page objects at all. Read the repo; do not
> carry either layout over.

House rules that are easy to get wrong anywhere, once you have found the local
answers:

- **E2E talks to the app through the browser.** Every precondition, action,
  assertion and cleanup goes through the UI. The spec opens no side channel of
  its own: no `page.request` / `request` fixture / `APIRequestContext`, no
  `fetch` to an API path, no database client, no backend CLI, no seeding
  script. Two exceptions, each limited to the use case named: the user
  explicitly instructs it, or the test case itself specifies that backend
  interaction. Record the exception (who asked or which case, and why) in the
  spec's header comment. Observing requests the app itself sends
  (`page.waitForResponse`) is not a side channel. A precondition the UI cannot
  reach gets a named `test.skip` or a question to the human — never an API
  shortcut.
- **Find the project's locator strategy before writing one.** Grep the
  existing specs: if `data-testid` is absent from the app, role + accessible
  name is the only strategy, and your locators must follow suit rather than
  asking for test IDs to be added.
- **Match shipped strings verbatim** — including typos and the exact dash or
  space characters the app renders. Verify every label against the code that
  renders it, not against the case file: QA paraphrases, the UI's literal text
  wins. Labels also come from server-side data (seeded permission names,
  default row order, status pages, a route's query-param schema), so when a
  locator or a precondition depends on a server-side data shape, grep that
  side instead of guessing.
- **Accessible names absorb their neighbours.** A sortable column header's
  name swallows the sort control's text, so `exact: true` never matches —
  anchor at the start of the name instead. A negative label often contains the
  positive one as a substring (Thai `ไม่ได้รับ` contains `ได้รับ`), so badge
  assertions need exact or anchored matching.
- **Run the project's own gates before declaring done.** Type-aware lint rules
  (`no-floating-promises`, `require-await`) are errors in most Playwright
  setups, and a missing `await` passes review and fails the suite.

## 1. Intake — reach a shared understanding before writing anything

If the user handed over a test-case file, read it first and come back with what
you found, so the questions are concrete rather than generic. Case sources vary
— **find, don't assume**: a "Test Result" workbook (locate the sheet holding
the cases, the header row, and which columns carry title/steps/expected/status),
CSV/Markdown, a domain YAML tree (a `cases:` list with
`scenario`/`preconditions`/`steps`/`expectations`), or one `brief.md` per case
directory. For a workbook, print its shape before relying on a column mapping:

```bash
python3 - "<the workbook>" <<'PY'
import sys; from openpyxl import load_workbook
wb = load_workbook(sys.argv[1], read_only=True, data_only=True)
print(wb.sheetnames)
ws = wb[wb.sheetnames[0]]
for row in ws.iter_rows(max_row=8, max_col=12, values_only=True):
    print([str(c)[:28] if c is not None else "" for c in row])
PY
```

Ask about the five things below — but **only the ones you cannot already
answer** from the file, the repo, or what the user said. Never ask a question
whose answer is sitting in the file you were just given. Ask them in one pass;
where the repo makes an answer obvious, state your assumption instead of
asking.

1. **Feature and where it lives** — which page/route/module is under test.
   Confirm against the repo, don't assume from the file's title.
2. **Which cases** — all of them, one section, or only the ones still
   untested? Say how many are in each state and let the user choose.
3. **Assets the test needs** — upload files, seeded data, a specific
   login/permission state, or UI-only? This is the question people most often
   forget, and the one that decides whether a case is automatable at all.
4. **Accounts and permissions** — who does each case log in as? Either
   dedicated accounts per role/permission combo (a human provisions them; each
   becomes an opt-in `storageState` following the project's existing setup
   project), or **one privileged account that grants and revokes its own
   permissions through the app's admin UI** before the flow (the self-grant
   pattern — see §3). Prefer the self-grant model when the roles themselves are
   not UI-observable: E2E sees permission _capabilities_, never role names, so
   several role-variants of one permission combo are one test, not several.
   Getting this wrong is expensive — one project scaffolded seven identities
   and tore them all out when the user said "one account is enough".
5. **Output wanted** — specs only? specs plus screenshots/video per case?
   evidence written back into the source workbook (→ `e2e-run-evidence`)? a
   separate report?

**Also settle, without a round trip if you can infer it:** the target
environment (a local stack vs the deployed shared one the config's base URL
points at), and whether running the suite mutates real data (uploads,
processing runs, permission flips) — if it does, say so plainly before running
anything, and plan the restore.

### Flag and resolve before writing code

- **Preconditions you cannot create from the UI, or the account cannot hold.**
  If a suite does not seed its environment, a precondition that is not
  reachable through the UI or an existing environment state is a question for
  the human, not an invitation to invent an API shortcut.
- **Ambiguous labels or steps.** Verify against the code that renders them.
  List every step you derived in your report — QA owns the business intent, so
  they confirm the how before it becomes the regression contract.
- **Expectation wording vs the shipped UI idiom.** QA authors write
  expectations without having read the code, so an Expected bullet's _wording_
  is their guess at how the outcome renders; the _intent_ — the behaviour being
  verified — is the contract. Before turning a bullet into an assertion, read
  the feature code and ask what the app actually shows when the expectation
  holds. If it satisfies the intent through a different idiom than the bullet
  names, assert the shipped idiom and record the translation in the spec header
  and the report.

  > **Worked example** — `No table is shown.` on a page whose table chrome
  > always renders really means "no data is visible": assert zero data rows
  > plus the empty state, not a hidden `<table>`. The literal assertion is
  > guaranteed red against correct behaviour.

  Name each bullet's target in one sentence before writing the assertion —
  what it verifies, and whether that target is a _business_ outcome (the data
  or result) or a _UI behaviour_ (what the app renders or keeps). Translation
  re-renders the same target in the shipped idiom; it never trades layers.
  `The table shows every record again` is not satisfied by `table` being
  visible — that asserts the behaviour while abandoning the business target
  (the records), so the count and rows must match. A purely behavioural bullet
  (`the chip remains shown, not auto-reset`) stays behavioural and is asserted
  as itself, not folded into its business neighbour. The intent moving is
  drift (next bullet); only the wording moving is translation, and a
  translation is never silent.
- **Expectations that contradict the app (case drift).** Automate every
  Expected bullet the app actually satisfies — judged on the translated
  intent, not the literal wording. For a bullet the app cannot satisfy, write
  the case as `test.fixme` carrying the case ID and what the app really does —
  **the fixme is the holding pen**, and the drift is always a finding in your
  report. Give the fixme its reason as an annotation,
  `test.fixme(title, { annotation: { type: 'drift', description } }, body)`,
  naming the bullet, what the case expects, what the app shows, why (the code
  or rule behind it) and who must rule. `e2e-run-evidence` prints that reason
  beside the case's evidence, so a reviewer sees why the case is held. Hold
  only the drifting bullet: the case's other bullets keep running. Never ship
  an assertion that can only fail — a guaranteed-red blocks evidence for every
  case serial after it, and the human, not you, rules whether the case file or
  the app moves.
- **Conditions only verifiable outside the browser** (audit logs, database
  rows, job side effects). Playwright sees only the browser. This is not drift
  — there is no assertion to fixme. If the UI evidences the same effect (an
  audit or history page), assert there and note the substitution; otherwise
  leave it out, list it under **Out of scope** in the spec header, and say it
  needs manual or API-level verification.

## 2. Map the cases onto the project

| Case field | Lands in |
| --- | --- |
| Route | the project's route helper or URL constants (add the route if the helper whitelists them) |
| Page actions | a new or existing page object, registered wherever the project composes its fixtures |
| Steps | `test.step()` blocks — one per case step, or per step of your derivation |
| Expected | `expect()` assertions, one per bullet the app can satisfy, phrased in the shipped UI's idiom (not the bullet's literal wording — see §1) |
| Inputs | committed assets resolved through the project's asset helper (self-skip when absent) or env vars (§5); the cells an Expected reads → the workbook capture in §4 |

Spec filenames follow the project's existing casing (lowercase in most
suites); case IDs stay uppercase in titles, step names and evidence names.
Name specs after their scope, with the case ID leading only when it is real:
`<case-id>-<behavior>.spec.ts` when the spec covers one case — a failure, or an
ID quoted in a bug report, then maps to its file with one `ls` — or a plain
scope name for a grouped suite, whose describe title and header list the
covered IDs instead.

**One spec per case is the norm.** Group cases that share unavoidable state
into one `test.describe.serial` spec with a `test.step` per case — permission
combos, expensive shared setup — and prefer one test per case otherwise,
because QA reads the HTML report per case. Reuse an existing page object when
the page already has one; add only the locators and actions your case needs.

When the cases form a **mutation suite** on a shared environment (permission
flips, processed runs), make it serial, order steps so destructive actions run
last, and end with a **restore test** that returns the environment to its prior
state (re-granting the account's original permissions, for instance). Say in
the spec header what persists and what is restored.

> **Worked example** — one suite covers a promo-code catalog screen:
> `promo-code-001-create-duplicate-code.spec.ts` is one case, while
> `catalog-permissions.spec.ts` is serial and covers `CATALOG-PERM-001`…`014`
> with one step per combo and a final restore test.

## 3. Build

Work in this order; each step de-risks the next.

**Fixture assets first.** If the feature ingests files, prefer generating them
from a checked-in spec over hand-crafting binaries — a spec is reviewable in a
diff and a binary is not (`references/fixtures-and-writeback.md`). Give each
fixture file exactly one defect so a failure names its own cause, and document
what each file is for.

**Then the page object**, mirroring the project's existing ones: locators as
getters, actions as methods, no assertions inside. Register it where the
project composes fixtures. The self-grant pattern lives here too: a fixture
action that flips the account's permissions through the admin UI — marked
clicks, a named evidence capture of the permission matrix _after_ save and
reload (a state a reviewer cannot re-derive later), a reload so the profile
refetch picks the new flags up, and a branch for "nothing changed" (see flow
mechanics). Specs verify the account actually holds the combo the case assumes
before asserting: if not, `test.skip` with the exact reconfiguration needed —
**a mis-set environment skips, it never asserts-fails.**

**Then the specs.** Title every `test` and `test.step` with the case ID — the
ID is what maps a run back onto the case and a failure onto a written
expectation.

**Open every spec with the case carried as the header doc comment**, in this
shape. The case file supplies the business content; you fill in Route and the
labelled Steps from your derivation. The spec gets read far more often than the
case file, and the header is where QA confirms your derivation:

```markdown
## <CASE-ID>: <short title>

- **Route:** /<app path> (<page state, e.g. result page, empty state>)
- **Precondition:** <data/setup that must exist before the case runs>
- **Inputs:** <files or values this case uploads/enters, or "none"; for a file, the sheet, row and column each Expected value is read from>
- **Steps:**
  1. <action, using the exact visible label>
  2. <action>
- **Expected:**
  - <observable result, written as the shipped UI actually presents it → each bullet becomes one assertion; note any wording translated from the case file>
- **Evidence:** <optional; default is video + key-moment + final screenshots, plus `<CASE-ID>-excel` when an Expected value comes from an input file>
- **Out of scope:** <optional, things this case deliberately does not verify>
```

In the TS file it becomes a leading `/** … */` block; keep the labels in the
Steps verbatim, since a reader maps them against the locators below. A grouped
spec carries one block per covered case (or one merged block listing every case
ID) plus its adaptations.

**Assert the card, not the app — but through the fixme gate.** The ticket and
its design are the authority on _behaviour_; the shipped UI is the authority on
_labels_. Where the app and the card disagree on behaviour, the honest red test
is defect evidence — but a permanently red test blocks every run that follows
it, so the drift ships as `test.fixme` with the disagreement spelled out, and a
human rules which side moves. When the _test case_ is what is wrong (stale
precondition, a number copied from another case), fix the case file and say so
in the report. **Never change application code to make a test pass.** Where the
card is silent, shipped behaviour becomes the reference and you say so
explicitly.

### Flow mechanics that have already bitten — respect them

- **Processing flows are slow.** Playwright's default timeout is 30–60s.
  Upload → process → result flows need an explicit `test.setTimeout(...)` and
  long waits on the result navigation — reached by URL, not by a heading whose
  accessible name swallows adjacent icons.
- **Wait on signals, not clocks.** `page.waitForResponse()`, `waitForURL`, a
  wait-for-API helper. The only sanctioned sleeps serve the human watching the
  video: the holds inside the marked-click and capture helpers (§4). Never
  sleep as a substitute for a signal.
- **The app can silently no-op.** Handlers that return early when nothing
  changed (a save that presents no confirm modal when no field was touched)
  will hang a fixture that unconditionally waits for the confirmation. The
  fixture branches on "did anything actually change".
- **Default sorts bury old rows pages deep.** A record from months ago is
  unreachable by paging a hundred-row history — navigate with the route's own
  query params instead.

  > **Worked example** — one history screen validates `?mode=month&period=YYYY-MM`
  > in its route schema, so the spec jumps straight to the month it needs.
- **Design systems can render duplicate accessibility nodes** (a disabled
  shadow checkbox beside the real one) — strict mode then double-matches. Scope
  by element + role or `.first()`, and confirm against the page snapshot from
  an actual failure (Playwright's `error-context.md`) rather than theorizing.
- **Reruns persist.** Upload and process write real records on a shared
  environment; sequence numbers advance every rerun. Assert by shape (a regex),
  never a hardcoded sequence. For filenames carrying a timestamp, validate
  against the click window in the app's own timezone, with about a minute of
  tolerance.
- **Warning dialogs are conditional.** A rerun hits a "this file was already
  uploaded" dialog where a first run does not. Handle both with a `.or()` race
  and then branch on `isVisible()`.
- **Missing assets skip, not fail.** `test.skip(!fs.existsSync(...))` at the
  **top of the test**, not inside a step — a mid-test skip abandons a run that
  has already captured evidence. A green run may legitimately contain skips;
  say so in your report.
- **Reach preconditions without writing to the shared environment.** "A
  processed run exists" does not mean "run upload and process first" — find an
  existing one through the read-only history or report page, and `test.skip`
  with a named reason when the environment has none.
- **A `webServer` timeout is not a spec failure.** When Playwright times out
  booting, the configured base URL was unreachable (network/VPN down,
  environment asleep). Probe reachability before rerunning, and print only the
  status — never echo the URL or any credential.
- **A local-only suite needs the local URL explicitly.** The default env file
  may point the base URL at the shared environment, in which case a spec gated
  on localhost skips silently while an ungated sibling writes its run to the
  shared one. Override per run, not in the file — dotenv never overrides an
  already-set variable, so a one-off `BASE_URL=... <test command>` is enough.
- **A generic server error is environment until proven otherwise.** An
  unspecific "something went wrong" page hides its cause, and an identical
  rerun fails identically. Read the service's own logs before rerunning.

  > **Worked example** — one stack runs its data warehouse as a Docker
  > emulator, so the team reads
  > `docker logs "$WAREHOUSE_CONTAINER" --since 10m | grep ERROR` and has seen
  > two causes there: a "table not found" on an empty project id (one env var
  > unset) seconds after upload, and a 20-second dial timeout to an internal
  > service (off the network). Find your stack's equivalent log; the container
  > name is yours to supply, never a default.

## 4. Evidence contract (every spec, no exceptions)

```ts
test.use({ video: "on" }); // spec-scoped; survives a global-config change
```

**Assertions are for the machine; the evidence is for a human who wasn't
watching the run.** Headless video renders no pointer, so a fast, cursor-less
video verifies nothing: a reviewer cannot tell where a click landed, or see a
result the test blows past in three seconds. Make every run watchable.

The contract needs four helpers in the project's shared utils fixture. Reuse
the project's equivalents if they exist; otherwise add them, with these names
or the project's own naming:

| Helper | What it must do |
| --- | --- |
| `spotlightClick(locator)` | outline the element, hold ~600ms before and after the click, leave the outline on so every click stays marked and the interaction is retraceable |
| `captureEvidence(name)` | rest the state ~1.5s, screenshot to a **stable directory outside Playwright's `outputDir`**, and attach the PNG to the report |
| `spotlightCheck(locator(s), '<CASE-ID>')` | scroll the target into view, outline it in a second colour, hold, then capture a close-up (`<CASE-ID>-close-up.png`) followed by the viewport frame with the outline still on (`<CASE-ID>.png`) |
| `showWorkbook(file, '<CASE-ID>-excel', { where, columns, note })` | render an input spreadsheet in the test's page the way a spreadsheet app shows it, highlight the rows and cells the case reads, outline them, and capture close-up then frame |

Then, per case:

- **Click through the marked-click helper**, routed through a page-object
  action (`openExportModal()`, `setPermissions()`…) so specs read as steps and
  the holds live in one place. Review-critical flows (permission setup,
  destructive confirms) get this even when a plain click would do.
- **Capture key moments as named evidence**, not just the end state: any state
  a reviewer cannot re-derive from the app later (a permission matrix
  mid-suite, a form half-filled, the row you picked) gets its own capture.
  Because every test ends on a capture, the end-state hold comes for free.
- **Show the point every case is about — scroll to it, mark it, zoom on it.**
  `expect()` leaves no trace: a value checked in a row forty rows down is
  invisible in the video and below the fold of a full-page shot, so the
  reviewer sees a page and has to take the pass on faith. Each case therefore
  ends with a spotlight check on the exact element(s) its Expected names: the
  cell, the one row, the seven column headers, the two rows an absent record
  would sit between. A locator resolving to many elements outlines them all;
  several locators go in as an array. A case that reads two screens gets one
  spotlight per screen, suffixed (`<CASE-ID>-page-2`).

  **Check whether `fullPage` even works in this app** before relying on it: in
  a shell whose main pane scrolls inside itself, `fullPage` yields one viewport
  frame of wherever the pane happens to be scrolled — which is what "the
  screenshots don't scroll" means when QA says it.
- **The value must be whole in the frame.** Wide tables scroll horizontally at
  a 1280px viewport and clip their right-hand columns; `999,999.99` shot as
  `999,999.9` reads to QA as a missing decimal — a false format defect. Give
  the spotlight helper a zoom-to-fit option and pass it whenever the point is a
  list or a right-hand column: it should zoom out the way Ctrl − does, for
  vertical *and* horizontal overflow, with an unchanged frame size and a floor
  around 40%. **Never enlarge the viewport**, because testers' screens differ.
  Outline every element the case asserts, not the first one — a `.nth(6)` cell
  is one cell of the first row, so give the page object a column locator
  instead.
- **Show the file when an Expected value comes from it.** A reviewer holding
  the evidence does not hold the upload, so a result value the file decides —
  an amount it sets, a name it carries, a row it lists or zeroes — cannot be
  checked from the result frame alone. Draw the file before the app is opened:
  `where` picks rows by header text, `columns` names the cells the value comes
  from, `note` says in one line what they decide. Decide **per Expected
  bullet**, not per case: a value some other system or the engine decides (a
  reason code, a failing row's `0.00`, a computed count) gets no file, because
  showing one claims a link that is not there. The test that uploads shows the
  whole file first (no `where`), so the video holds the input before the app
  reads it. Capture the file **before** the result, so the result frame stays
  the case's last match. Make the helper throw when `where` matches no row or
  names a missing column, so the evidence never shows a file with nothing
  marked.

  An input that is not a spreadsheet (CSV, TXT, JSON, a raw body) is attached
  as itself, named by case: `testInfo.attach('<CASE-ID>-csv', { path })` or
  `testInfo.attach('<CASE-ID>-input', { body, contentType: 'text/plain' })`.
  `e2e-run-evidence` draws it and stacks it above the result. A plain
  attachment marks no cell, so when the case reads particular rows of such a
  file, name them on the header's **Inputs** line.
- **An absence case shows its reference too.** "X is not shown" proves nothing
  alone, because the reviewer cannot tell X was ever in the input. Show the
  precondition first, where it can still be seen: the file itself for what the
  file holds, or the upload's preview for what the app read from it — upload
  the same file, stop before the confirm step so nothing is written, and
  spotlight X's row as `<CASE-ID>-reference`. Then mark the neighbours X would
  sit between on the result. Cite the source rows in the report too.
- **Read the PNGs before reporting.** Open each case's frame and close-up and
  check that the asserted value is in frame, whole and outlined. A green test
  whose evidence doesn't show its point is a test defect to fix, not a pass to
  hand over. Sampling is not enough: one green run shipped frames whose row sat
  under the sticky header. Sweep every capture for the outline colour and open
  each one the sweep flags.
- **Name captures by case ID, nothing else.** A workbook exporter finds a
  case's image by that ID in the attachment name and keeps the **last** match,
  which is why the spotlight helper attaches the close-up first and the frame
  last. A descriptive name is fine only for a key moment belonging to no single
  case (`setup`).
- **Downloads**: assert on `suggestedFilename()` and contents; for a
  spreadsheet, read it with the project's own reader (date cells arrive as
  serial numbers, not dates).

Named screenshots stay under a stable evidence directory, outside Playwright's
cleaned `outputDir`, and are also attached to the HTML report; per-test WebM
files stay under the run's results directory. When results are wanted in Excel,
use `e2e-run-evidence`: its workbook carries ID, topic, expected result,
status, reason and image, and its standalone HTML companion embeds the videos.
Don't add unreliable WebM hyperlinks to Excel.

## 5. Plumb inputs and env without leaking them

The E2E project's env file is gitignored and already holds the base URL and
whatever credentials the setup project signs in with. For each new external
input:

1. A getter in the project's typed env module, following its existing pattern
   (required vs optional-or-undefined; `~` expansion and `path.resolve` for
   file paths).
2. Its type in the project's env type declaration.
3. A line in the committed `*.example` file with a **placeholder** — never a
   real path, URL, credential, or the file itself. Workbooks and credentials
   stay out of the repository; the case file references them by name only.

If the spec cannot run yet because a human must set a variable or provision an
account, still finish the code and say exactly which name is missing.

## 6. Verify, then run

Use the project's own scripts, discovered in §0 — not the ones below, which are
one repo's names:

```bash
# from the E2E project directory
<pkg> check:types && <pkg> lint
<pkg> test --project=<the authenticated project> <testDir>/<area>/<spec>.spec.ts
```

A setup project that signs in once and saves `storageState` runs automatically
as a dependency when the config declares it. A non-local base URL means the
deployed frontend is used as is (no dev-server boot); a local URL starts the
`webServer`. The first run on a machine needs an install and a browser
download (`playwright install`). Do not seed or reset a shared environment —
its existing data is the fixture unless the user says otherwise.

### Windows PowerShell

Windows PowerShell 5.1 has no `&&`, and `VAR=value cmd` does not parse. The
same commands in its own syntax:

```powershell
<pkg> -C <e2e-dir> check:types; if ($?) { <pkg> -C <e2e-dir> lint }

try {
  $env:BASE_URL = 'http://localhost:3000'
  <pkg> -C <e2e-dir> exec playwright test <spec> --project=<project>
} finally { Remove-Item Env:BASE_URL -ErrorAction SilentlyContinue }
```

- **Scope every override with `try { } finally { }`.** `$env:` lasts for the
  whole session, and dotenv never overrides an already-set variable. A leftover
  base URL sends every later run — shared-environment runs included — to
  localhost. `finally` clears it on Ctrl+C too.
- **POSIX `make` recipes need Git Bash**, called by its full path: a bare
  `bash` resolves to WSL's, a different filesystem and network. Check
  `make --version` when a recipe needs GNU-only syntax.
- **A relative `-C <dir>` resolves against the current directory**, so running
  it from inside that directory looks for `<dir>/<dir>`.
- **If Playwright reports `EPERM … playwright-transform-cache` and then
  `No tests found`**, the transform cache directory is not writable: point
  `PWTEST_CACHE_DIR` at an ignored folder for the run, inside the same
  `try { } finally { }`.

### When the stack, not the spec, is broken

Check the stack before blaming the spec: every service the run needs must be
listening, the API port the frontend calls must match the one the backend
serves, and a dependency that lives behind the corporate network needs either
that network or a local mock. A permissions-reset or seeding project some
suites run before every invocation can be skipped by env var — if you skip it,
it shows as skipped tests, so report them.

## 7. Report honestly

Say what ran, what passed, and **what was skipped and why** — a green run with
silent skips is worse than a red one. State the executed-case count, not just
"all passed". Include:

- Pass/fail per case, and artifact paths (evidence directory, HTML report,
  videos).
- Every Expected bullet excluded as needing verification outside the UI.
- Every step you derived rather than took from the case.
- Every assumption resolved by reading code (label corrections, sequence-shape
  decisions, account-model choices).
- Every drift finding, kept in its own category: **app defect** (the app
  deviates from an unambiguous card — living as a fixme until ruled), **card
  defect** (the card contradicts itself or the design), **test defect** (the
  test asserted neither). Do not edit a case file's expectation to match
  observed behaviour — translating its wording to the shipped idiom while the
  tested target stays the same is the one licensed change, and it is always
  reported, never silent.
- What the run mutated on a shared environment, and what was restored.

## Guardrails

- **Never commit or echo credentials, environment URLs, or input workbooks.**
  They live only in the gitignored env file and on disk outside the repo.
- **Never edit generated or frozen trees** (a generated route tree, a frozen
  test-case history) and nothing outside the E2E project and the case-source
  files, except reading application code for labels.
- **Never add a second framework or a shared helper package.** Hand-written
  in-project fixtures and the project's existing helpers only.
- Don't broaden a case to make it pass, and never weaken it silently: drift
  gets the fixme treatment and a line in your report — the human decides
  whether the case file or the app moves.
- If another writer is editing the same E2E tree concurrently (duplicates
  appearing in files you touched), stop and ask the human before consolidating
  — read what exists, verify it, keep the strongest version; don't clobber live
  work.
- If a stale copy of this skill is shadowing it (the invocation reports a base
  directory you did not install), stop and remove that copy first: specs
  written from an old snapshot drop the evidence contract above — no marked
  clicks, no close-ups, captures not named by case ID.

## Precedents to look for in the target repo

Before starting a new feature, find the existing spec closest to your case
shape and imitate it. Look for one of each:

| Shape | What to copy from it |
| --- | --- |
| Serial permission/mutation suite | self-grant setup, per-case steps, restore test, case-header block |
| Upload → process → download, with file validation | long timeouts, signal waits, env-driven input, download assertions |
| Case-pattern header carrying the workbook source | how derivations and workbook corrections are recorded |
| Read-only grouped multi-case spec | the grouping justification, `test.fixme` / `test.skip` discipline |
| Asset self-skip | the top-of-test existence check |
| The shared utils fixture | upload, download, wait-for-API, marked click, spotlight check, workbook capture — reuse, don't reinvent |

If the repo has none of these, you are the precedent: write the first one to
the standard above, and say so in your report.

## References

- `references/scaffold-e2e.md` — starting a Playwright project from nothing,
  for a repo that has no E2E yet (only with the user's agreement).
- `references/fixtures-and-writeback.md` — generating fixture workbooks,
  seeded data, and writing evidence or pass/fail back into the source workbook.
  Read only when a case needs one of those.
