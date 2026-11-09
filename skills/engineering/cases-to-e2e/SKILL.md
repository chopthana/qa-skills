---
name: cases-to-e2e
description: >
  Turn QA test cases — a Test Result workbook, CSV/Markdown, or a repo's own
  domain test-case YAML — into runnable Playwright specs in the project's
  existing E2E suite, run them, and hand back reviewable evidence (watchable
  video with marked clicks, close-up screenshots, optional pass/fail
  write-back). Use whenever someone hands over test cases in any format, asks
  to automate them or add E2E coverage, asks to run or re-run a case, or wants
  per-case screenshot/video evidence. A repo's own E2E skill wins over this one.
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

**Open every spec with the case carried as the header doc comment**,
in the shape given in
[references/spec-and-evidence.md](references/spec-and-evidence.md) — the
case file supplies the business content; you fill in Route and the labelled
Steps from your derivation. A grouped spec carries one block per covered
case plus its adaptations.

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

**Before you debug a failure, check it against
[references/flow-mechanics.md](references/flow-mechanics.md)** — slow processing
flows, silent no-ops, duplicate accessibility nodes, persisted reruns,
conditional dialogs, missing assets, an unreachable base URL. Each entry there
cost somebody a session already.

### Hand the spec writing to a subagent

Writing a spec means reading the references above, the project's precedent
specs, its page objects and its fixtures — and then a run's worth of failure
output. That is a lot of context for work whose product is one file, so **it
does not belong in the context that is talking to the user.**

Dispatch **one subagent per case group** (`model: "sonnet"`,
`effort: "medium"`). If the target repo ships its own spec-writing agent, use
that one — it already carries the project's facts. Otherwise use `tc-author`.

Each dispatch carries, as **paths, never pasted content**: the case file, this
skill's `references/spec-and-evidence.md` and `references/flow-mechanics.md`,
the §0 discovery notes, the precedent spec to imitate, and the output spec path.
It returns the spec path, its run result line, and what it had to park.

Keep for yourself: §0 discovery, §1 intake, §2 mapping, the fixme rulings, and
§7's report. Those are judgment and they are the conversation.

## 4. Evidence contract

**Assertions are for the machine; the evidence is for a human who wasn't
watching the run.** Headless video renders no pointer, so a fast,
cursor-less video verifies nothing. Every spec carries
`test.use({ video: "on" })`, every click goes through the marked-click
helper, every case ends with a spotlight check on the exact element its
Expected names, and every capture is named by case ID.

The four required helpers, what each must do, and the per-case rules —
including zoom-to-fit for clipped values, showing an input file when an
Expected value comes from it, absence cases, and reading the PNGs before
reporting — are in
[references/spec-and-evidence.md](references/spec-and-evidence.md).
**Read it before writing the first spec of a feature.**

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

A run prints thousands of lines and the verdict is a handful of numbers, so
**dispatch the run itself** (`tc-e2e-run`, `model: "haiku"`, `effort: "low"`)
with the project directory, the exact command, the artifact directory and a
summary path. It returns counts, the failing test IDs with their first error
line, and the skip reasons — never the reporter output. You read the summary
file only for the failures you are actually going to act on.

Type-check and lint stay with you: they are fast and their output is short.

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

PowerShell 5.1 has no `&&` and cannot parse `VAR=value cmd`. The same
commands in its own syntax, plus the `try { } finally { }` scoping an
override needs, are in [references/windows.md](references/windows.md).

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

Hand these to the spec-writing subagent as paths. Read one yourself only when
you are the one writing.

- `references/spec-and-evidence.md` — the spec header's shape and the full
  evidence contract (the four helpers, zoom-to-fit, showing an input file,
  absence cases, reading the PNGs). **Required before the first spec.**
- `references/flow-mechanics.md` — the failure modes that have already cost
  somebody a session. Read before debugging a failure.
- `references/windows.md` — PowerShell syntax and override scoping. Windows
  only.
- `references/scaffold-e2e.md` — starting a Playwright project from nothing,
  for a repo that has no E2E yet (only with the user's agreement).
- `references/fixtures-and-writeback.md` — generating fixture workbooks,
  seeded data, and writing evidence or pass/fail back into the source workbook.
  Read only when a case needs one of those.
