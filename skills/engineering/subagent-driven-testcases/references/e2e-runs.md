# The E2E branch

Automating a suite is the same controller loop with four things moved. Read this
instead of improvising, then go back to SKILL.md § 3 and run the loop.

| | Case-authoring run | E2E run |
| --- | --- | --- |
| **Inventory** | ACs, field rules, states, strings | **the cases themselves** — one case ID is one obligation |
| **Slice** | a screen section's cases | one spec file, or one area's spec files |
| **Collision** | none — disjoint files | **real** — page objects, helpers and registries are shared |
| **Done** | the review is clean | the review is clean **and the spec ran** |
| **Merge** | renumber IDs into one set | nothing to renumber; prove coverage and run the suite |

## 1. Inventory: the cases are the spine

No surveyor pass over a spec. The inventory is the case set the user points at —
a domain YAML tree, a workbook, `merged.cases.json` from an earlier run of this
skill. Write `<workspace>/inventory.md` from it, one row per case:

```markdown
| ID | Case | Area | Automatable | Note |
| --- | --- | --- | --- | --- |
| `TC-PROMO-004` | ไม่กรอกรหัสแล้วกดบันทึก | promo/create | yes | — |
| `TC-PROMO-019` | ตรวจสอบสีของ badge | promo/list | no — visual | manual only |
| `TC-PROMO-022` | ยกเลิกคำขอที่อนุมัติแล้ว | promo/approve | not yet | needs an approved request on the env |
```

**Automatable is a decision, and it is the user's.** Decide the obvious rows
yourself (`no — visual`, `no — needs a third-party sandbox`) and put the
not-obvious ones in the intake pass: a case the user expects automated and you
silently marked manual is the one complaint this skill cannot absorb. Every row
marked `no` or `not yet` carries its reason into the coverage report — that is
what makes the number honest.

## 2. Phase A before fan-out: the shared surface, serially

A spec suite is not disjoint files. Page objects, route helpers, test data
builders and above all **registry files** — the index that every fixture is
registered in — are touched by every slice. Two authors editing a registry in
parallel is exactly the collision `subagent-driven-development` forbids.

So the run has two phases:

**Phase A — one author, serial.** Read the target project's existing E2E
conventions, then build or extend everything more than one slice needs: page
objects for the screens in scope, their registration, route entries, fixture
assets, env plumbing. It writes no spec. Its report lists, per screen, the
locators and actions now available, with their exact names — that list goes
into every Phase B brief, which is how an author writes against a page object
it is not allowed to read.

**Phase B — fan out, specs only.** An author writes its own spec file(s) and
**may not edit any shared file**. Needs a locator that does not exist? It
reports `NEEDS_CONTEXT` and stops; you amend Phase A (resume that author, one
scoped edit, re-review the shared file) and resume the Phase B author with the
new name. That round-trip costs a few minutes; two authors silently adding the
same locator under two names costs the suite.

Give every Phase B brief the file paths it owns, explicitly, and the sentence
**"files not in this list are read-only for you"**.

## 3. Briefs carry the project's conventions, not your guesses

The producer skill knows the target project: where specs live, the filename
casing, whether a case ID leads the filename, how the case is carried in the
spec header, the evidence contract, the timeout and waiting rules. The brief
points at the producer and copies the conventions that bind this slice —
verbatim. An author inventing a filename pattern or an evidence call produces a
spec that review will send straight back.

Two conventions are load-bearing for coverage and belong in every brief whether
or not the producer stresses them:

- **The case ID appears in the test title** (and in the spec header), spelled
  exactly as the inventory spells it. That string is what maps a run back to a
  case. A spec that covers several cases names every one of them.
- **A spec that cannot assert yet is parked, not deleted and not left red.**
  Behavior drift between the card and the app → the holding pen the producer
  prescribes (`test.fixme` and the disagreement written out). Environment or
  missing data → a skip with a named reason, at the top of the test. A
  permanently red test blocks every run after it; a silently deleted case is a
  coverage lie.

## 4. Done means it ran

An author's `DONE` requires, in its report:

- the command it ran, and the result line (`N passed, M skipped`);
- for every parked test, which construct and why;
- the evidence the run produced, if the producer's contract asks for it.

A spec that was written but never executed is `DONE_WITH_CONCERNS` at best.
Reviewers cannot catch a selector that does not match anything; a run can.

The slice reviewer adds three checks to its gate list for E2E:

- **the header matches the case** — steps and expected results in the spec
  header are the case's, not a paraphrase that drifted;
- **assertions trace to expected results** — one assertion per expected bullet
  the app can satisfy, and no assertion asserting something the case never
  claimed;
- **no sleeps standing in for signals**, no hardcoded sequence numbers, no
  assertion on data a rerun changes.

Run the specs on a **shared** environment and the suite writes real data. Before
Phase B, settle with the user which environment, and whether mutation is
allowed; a destructive slice gets ordered last and ends by restoring state.

## 5. Coverage, instead of a merge

Nothing to renumber — the case IDs already exist. Run:

```bash
python3 <skill-dir>/scripts/coverage_e2e.py \
  --cases <the case source: file or directory> \
  --specs <the project's spec tree> \
  --inventory <workspace>/inventory.md \
  --report <playwright json report, if the suite has been run> \
  --out <workspace>/coverage-e2e.md
```

It reads the case IDs, finds every ID mentioned in every spec, and sorts each
one into:

| Bucket | Meaning |
| --- | --- |
| **green** | an active test names it, and the run report says it passed |
| **red** | an active test names it and the run report says it failed |
| **automated** | an active test names it; no run evidence yet |
| **parked** | the only tests naming it are `fixme` / `skip` |
| **documented** | the ID appears only in a header or comment — no test owns it |
| **missing** | no spec mentions it |
| **orphan** | a spec names an ID the case source does not have |

**`parked` and `documented` are not coverage.** A suite that reports 90%
automated where a third of it is parked is the failure this bucketing exists to
prevent. The report states both numbers, and the final report to the user leads
with green + automated, then names parked and missing with reasons.

`missing` rows that the inventory marked `no` or `not yet` are expected — the
script separates them from the ones nobody got to, which are the rows that go
back into a late slice or into the user's hands as a decision.

## 6. Final review for an E2E run

[references/final-review.md](final-review.md) still applies; add to it:

- **run the whole suite once, serially**, and compare against the sum of the
  slice runs. A spec that passes alone and fails in the suite is state leaking
  between specs — that is a finding, and it is invisible to every slice review.
- **re-run the failures once.** A test that fails then passes is flaky; flaky is
  a finding, not a pass. Name it in the report.
- **review the shared surface as a diff** — the Phase A files, all of them, in
  one reviewer pass. They were written before any spec existed and nobody has
  looked at them since the specs showed what they had to support.
- **the coverage table goes in the report**, bucket by bucket, with every
  `missing` and `parked` row carrying its reason.
