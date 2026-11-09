---
name: subagent-driven-testcases
description: >
  Run a bulk test-case job as a controller plus fresh subagents: survey the
  sources into one coverage inventory, cut it into disjoint slices, fan out an
  author subagent per slice, review every slice, then merge and renumber into
  one deliverable. Use when a test-case job is too big for one context — a
  whole feature, several screens, 40+ cases, a sprint's worth of conversion,
  or a suite of E2E specs — and the writing itself belongs to another skill
  (spec → workbook, cases → YAML, cases → Playwright) that this one drives.
  Also use for "เขียน test case ทั้งฟีเจอร์", "เคสเยอะมาก", "แบ่งงานให้
  subagent เขียนเคส", "fan out test cases", "coverage ของ E2E", "เคสไหนยัง
  automate ไม่ครบ". Not for a single screen or a handful of cases — call the
  producer skill directly for those.
---

# Subagent-driven test cases

Writing test cases is bulk prose: sixty to two hundred rows of steps and
expected results, each one quoting a string that must be exact. One context
doing all of it degrades — the rows written last are thinner than the rows
written first, because by then the context is full of the rows themselves.

So the writing is delegated. A **controller** (you) owns the sources, the
coverage **inventory**, the **ledger** and the **merge**. An **author**
subagent writes one **slice** and nothing else. A **reviewer** subagent gates
each slice. You never write cases yourself.

**Core principle:** one inventory + disjoint slices + an author per slice +
a reviewer per slice + a merge that owns the IDs = full coverage, in parallel,
at steady quality.

## Fan out — this is not code

`subagent-driven-development` forbids parallel implementers because two agents
editing one tree collide. Test-case slices do not collide: each author writes
**its own file** and never reads another's. So the default here is **fan-out** —
dispatch 3–5 authors at once — and the serialization point moves to the
**merge**, which is the only seat allowed to assign a final TC ID.

That is the whole speed win. A run that would take one context an afternoon
takes four authors one round.

**One run breaks that rule: automating a suite.** Specs are disjoint, but the
page objects, helpers and registries under them are shared, and two authors
editing a registry collide like any two coders. An E2E run therefore builds the
shared surface serially first, then fans out on specs only — and it earns its
coverage differently, because a spec that was never executed proves nothing.
Read [references/e2e-runs.md](references/e2e-runs.md) before setting one up.

## When not to use this

| Situation | Instead |
| --- | --- |
| One screen, under ~20 cases | Call the producer skill directly — slicing costs more than it saves |
| The sources are not settled yet (no ACs, no prototype, no screenshots) | Settle them first; authors cannot interview anyone |
| Auditing or deduping a set that already exists | A coverage-audit skill, then this one only if it asks for new cases |
| Running tests and collecting evidence | An evidence/reporting skill |

## The seats

| Seat | Agent | Context | Writes | Talks to the user |
| --- | --- | --- | --- | --- |
| **Controller** (you) | — | the whole run | ledger, inventory, briefs, merge, report | yes — and only you |
| **Author** | `tc-author` | one slice | `slice-N-cases.json`, `slice-N-report.md` | **no** |
| **Reviewer** | `tc-review` | one slice's diff of a file | `slice-N-review.md` | **no** |
| **Final reviewer** | — (your model) | the merged set | `final-review.md` | **no** |

An author has no user. A producer skill that normally stops to ask about file
names, ID prefixes or side files **must not stop** inside an author — so you
answer those questions once, before the first dispatch, and the answers travel
in the brief. An author that asks a question has been under-briefed: answer it
and resume that same author, never hand the question to the user.

## Rulings, not stalls

A running job does not wait on a human. Slice boundaries, a brief's ambiguity, a
missing default, a slice that turns out to need splitting — decide them. Record
each as `Ruling: <decision> — <why> — <cost if wrong>` in the ledger and keep
going.

**A source conflict is not a stall and not a ruling.** When the spec and the
screen disagree, the case asserts the spec, the note column carries the flag,
and the question goes on the open-questions list for the team. Never silently
pick a side; never park the run waiting for an answer.

Four things stop you: an intake answer you do not have and cannot propose
(see Setup); a write that destroys someone's work (overwriting a workbook that
is open, or a path outside the run's output); anything leaving this machine
(push, share, send); and sources so broken that every slice would be a guess.

**Narration:** at most one short line between tool calls. The ledger and the
report files carry the record.

**Continuous execution:** do not check in between slices. "Should I keep going?"
costs the user their afternoon and buys nothing — they asked for the suite, so
produce the suite.

## Setup

### 1. Pick the producer, and find it on disk

This skill writes no cases and knows no formats. It drives a **producer skill**,
chosen per run:

| The run produces | Producer |
| --- | --- |
| New cases from a ticket/PRD + a prototype or screenshots | the spec-to-cases skill available here |
| A repo's domain test-case YAML from existing case files | the case-conversion skill available here |
| Runnable E2E specs from existing cases | the cases-to-E2E skill available here — **and [references/e2e-runs.md](references/e2e-runs.md), which changes four steps of this loop** |

Discover what is installed instead of assuming — list the skill roots in play
(the project's own skills directory, the user's, the plugin cache) and name the
candidate back to the user if more than one fits. Record in the ledger:

- the producer's **name**,
- the **absolute path to its `SKILL.md`**, and
- the absolute path of any generator script it owns (the thing that turns cases
  into the deliverable).

The path matters: a producer with `disable-model-invocation: true` cannot be
auto-invoked by a subagent, so the brief tells the author to **read that
SKILL.md file first** and follow it. For a model-invoked producer the brief
names it and the author invokes it. Either way the producer's rules bind the
author, and this skill never restates them.

### 2. Settle the intake once

Producer skills ask before they generate — deliverable name, TC ID prefix,
optional side files, where the output goes. Ask all of it **now**, in one pass,
with a concrete proposal per question, because every answer has to be in the
briefs. Then write the answers into the ledger as the **intake block**, verbatim,
and paste that block into every brief.

If the producer defines its own intake questions, read its SKILL.md yourself
first and ask that list. An intake question you cannot answer and cannot
propose an answer for is one of the four stops.

### 3. Workspace and ledger

Run this skill's `bash scripts/tc-workspace <run-slug>` by its absolute path to
get the run's directory — everything for THIS run lives there: ledger,
inventory, briefs, slice files, reports, reviews, merge output. Another run's
directory is never yours to write.

Then check for `<workspace>/progress.md`. **If it exists, read
[references/resuming.md](references/resuming.md) before anything else.**
Otherwise create it, with its identity as the first line:

```text
# testcase-sdd ledger — producer: <name> — sources: <what they are> — out: <path>
```

Context does not survive compaction; the ledger does. Controllers that lost
their place have re-dispatched slices that were already written and merged a
double set of cases into the deliverable. After compaction, trust the ledger and
the files on disk over your own memory of what you dispatched.

## 1. Survey: one inventory, before any slicing

Dispatch **one** surveyor subagent (capable model) over all the sources. It
writes `<workspace>/inventory.md` and returns only counts.

The inventory is the run's spine: every acceptance criterion, field rule, screen
state, section, flow and user-visible string, each with a stable item ID. It is
the thing that makes fan-out safe — slices are cut from it, authors **claim**
items from it, and the final review proves every item was claimed or **parked**
with a reason. Nothing can be silently dropped by a subagent that only ever saw
one slice.

Format and item-ID conventions: [references/inventory.md](references/inventory.md).

Read the inventory yourself once. It is the only source document you keep in
your own context all run.

## 2. Cut the slices

A **slice** is one author's whole job: a coherent group of inventory items,
8–20 cases' worth. Slices are **disjoint** — one item has exactly one owning
slice — and cross-cutting items (end-to-end happy path, wording sweeps) get
their own slice, dispatched last.

Cutting rules, sizes and a worked example:
[references/slicing.md](references/slicing.md).

Write the slice table into the ledger before dispatching anything:

```text
| slice | what | items claimed | model | state |
```

Every inventory item appears in exactly one row's claim list, or in a
`Parked:` line with a reason. Check that before you dispatch — an item that
belongs to no slice is a case nobody will write, and the final review will
find it hours later.

## 3. Fan out the authors

Run `bash scripts/tc-workspace <run-slug> --brief <N>` to get the brief path,
write the brief, then dispatch. 3–5 authors in flight; more than that and your
own turn-handling becomes the bottleneck.

A brief carries exactly five things:

1. one line on what this feature is and where this slice sits in it;
2. the **intake block**, verbatim;
3. the slice's inventory items, **copied in full with their exact values** —
   every string, label, message, boundary number and option list the author
   must quote. The author never reads the spec, the inventory or another
   slice's cases;
4. the producer: its name, its SKILL.md path, and "read/invoke this first — it
   owns the case format and the writing rules";
5. the output contract: the slice file path, the ID placeholder convention, the
   report file path, and the report shape.

Template: [author-prompt.md](author-prompt.md).

**ID placeholders.** An author never invents a final ID — it numbers its cases
`{{S<N>}}-001`, `{{S<N>}}-002`, … in its own file. The merge assigns real IDs.
Two parallel authors cannot collide on a number they are not allowed to write.

**Agent and model per seat.** This plugin ships the seats as agents, so their
models are pinned and you do not re-decide them every dispatch:

| Seat | Agent | Model | Effort |
| --- | --- | --- | --- |
| Author, mechanical slice (every string is in the brief; the cases are a drill: required-empty, too-long, duplicate, trim) | `tc-author` | sonnet | `low` |
| Author, judgment slice (state tables, combinations, a brief that describes behavior in prose) | `tc-author` | sonnet | `medium` |
| Slice reviewer | `tc-review` | sonnet | `high` |
| One source file → the target format | `tc-convert` | sonnet | `medium` |
| Bulk extraction, a suite run | `tc-extract`, `tc-e2e-run` | haiku | `low` |
| **Surveyor and final reviewer** | none — most capable | yours | `high` |

**Always name the model and the effort explicitly**, even when dispatching a
named agent. An omitted model inherits yours, which is the most expensive one in
the run, and that default is how a cheap fan-out quietly becomes an expensive
one.

The surveyor and the final reviewer are the two seats worth your own model: the
survey decides what the whole run will cover, and the final review is the last
thing between a silent drop and the deliverable. Everything between them is work
with a brief, and work with a brief is sonnet's.

What never goes in a dispatch: the whole spec, the whole inventory, prior
slices' cases, a summary of the run so far, or any case text at all. Everything
crosses between seats as a **file path**. Case text that enters your context
stays there for every later turn of the run.

**While you wait**, keep working: write the next brief, package the last review,
update the ledger. When genuinely idle, wait in bounded stretches, and between
stretches post one status line and reconcile your live children — list them and
chase any that finished without reporting.

## 4. Review every slice

Never merge an unreviewed slice, and never accept a review missing either
verdict: **coverage** (every claimed item has a case) and **executability**
(every case can actually be run and recorded).

The reviewer gets three paths — the brief, the slice file, the author's report
— plus the binding constraints copied verbatim from the producer's rules and the
intake block. It returns `slice-N-review.md`.

The gate list, and how to write the review, live in
[reviewer-prompt.md](reviewer-prompt.md). The two findings that recur most, and
that a one-context run almost always ships:

- **two data sets in one row** — steps try 20 digits and 21 digits, expected
  says "20 saves, 21 rejects", and the tester has one Pass/Fail cell and cannot
  record either. Split.
- **an assertion the steps never reach** — the case checks a message for a state
  the screen cannot be put into. Flag as a question; do not quietly rewrite it.

Do not pre-judge findings for a reviewer. If your prompt contains "do not flag"
or "at most minor", you are buying yourself a quiet review, and you will pay for
it in the merge.

## 5. Fix loop

Triggered by a ❌ coverage verdict, a not-approved executability verdict, or any
finding the reviewer rates blocking.

Read [references/fix-loop.md](references/fix-loop.md) and follow it — **again
before every round**, even if you read it earlier this run. It holds the round
cap, the escalation, the parking rule and the ledger line each round writes, and
your memory of it does not survive compaction.

## 6. Merge — the only seat that assigns IDs

**On an E2E run there is nothing to renumber** — the case IDs already exist, and
this step is the coverage proof instead: `scripts/coverage_e2e.py`, described in
[references/e2e-runs.md](references/e2e-runs.md) § 5. The rest of this section
is the case-authoring path.

When every slice is clean or parked, merge in slice order:

```bash
python3 <skill-dir>/scripts/merge_slices.py \
  --workspace <workspace> \
  --prefix "<the confirmed TC ID prefix>" \
  --inventory <workspace>/inventory.md \
  --meta-file <workspace>/meta.json   # top-level fields the generator needs
```

It renumbers `{{S<N>}}-nnn` into `<PREFIX>-001…N` in slice order, passes every
other field through untouched, writes `merged.cases.json` and `coverage.md`, and
prints an **ACTION REQUIRED** block you read before you build anything:

- **unclaimed items** — in the inventory, in no slice. A cutting mistake. Cut a
  late slice for them and dispatch it.
- **near-duplicate cases** — two slices wrote the same case. Also a cutting
  mistake: keep one, and record which slice lost it in the ledger.
- **double-claimed or unknown items** — a slice claimed an item another slice
  owns, or an item ID that is not in the inventory. Fix the claim, not the ID.
- **placeholder problems** — an author wrote a real ID, or another slice's
  number. The case still merged; check it is the case you think it is.
- **ID map** — placeholder → final ID, in `coverage.md`, so a review finding
  against `{{S3}}-004` can still be traced after renumbering.

`--check-only` re-runs the report without writing, which is how you confirm a
fix wave before rebuilding the deliverable.

Then build the deliverable with the **producer's own generator**, from
`merged.cases.json`. This skill never writes an `.xlsx`, a YAML tree or a spec
file itself — if the producer's generator does not take this shape, convert in
one step here and say so in the ledger.

## 7. Final review

Read [references/final-review.md](references/final-review.md) and follow it: one
capable reviewer over the whole merged set, one fix wave, then finish.

## 8. Report

Deliver, in the chat, in the user's language:

- the deliverable path and the case count;
- **coverage**: `claimed <n>/<total> inventory items, <k> parked` — and each
  parked item with its reason. On an E2E run this is the bucket table from
  `coverage-e2e.md` instead, led by green and automated, with every parked,
  missing and orphan row carrying its reason;
- **open questions** for the team, each phrased as a decision ("Is the ID unique
  across all partitions, or within one?"), not as an observation;
- **wording and typo findings**, with which side each one is on;
- what the run cost: slices, rounds, and anything a reviewer could not verify.

Leave the workspace in place until the user has accepted the deliverable — it is
the only evidence of how the set was built.

## Rules

- **You never write a case.** Not one, not "just the last three", not a fix the
  reviewer asked for. Resume the author. A controller that writes cases has no
  reviewer and is back to one degrading context.
- **Files, not messages.** Briefs, cases, reports, reviews all cross as paths.
- **One inventory, one owner per item.** Disjoint slices or duplicate cases.
- **IDs belong to the merge.** Placeholders everywhere upstream.
- **Flag, never drop; flag, never resolve.** Every inventory item ends as a case
  or a parked line with a reason. Every source conflict ends as a flagged case
  plus an open question.
- **The producer owns the format.** Case shape, wording rules, file naming,
  verbatim-string policy — read them from the producer and pass them to the
  author; never restate or override them here.
- **No skipped review.** An unreviewed slice does not reach the merge.

## Common rationalizations

| Excuse | Reality |
| --- | --- |
| "Slicing is overhead, I'll just write them" | Row 80 written by a full context is the one that ships wrong. That is the cost you are paying to save the slicing. |
| "I'll run the authors one at a time to be safe" | Authors write disjoint files. Serial fan-out is this skill with its one advantage switched off. |
| "The author asked a question, I'll ask the user" | The author is under-briefed. Answer it from the sources and resume it. The user already answered the intake. |
| "Both slices should cover login, it's safer" | It is two cases with two IDs for one behavior, and the merge will find it after the author seat is gone. |
| "This slice is small, skip the review" | Small slices ship the two-data-sets-in-one-row case as often as big ones. |
| "I'll fix the reviewer's three findings myself, it's faster" | Unreviewed edits by the seat that owns the merge are how a set with a clean review ships broken. |
| "The spec and the screen disagree — I'll pick the screen, it's what's built" | Silent picks are how a case asserts the wrong string and then the app gets "fixed" to match it. Flag and ask. |
| "The ledger is bookkeeping" | The ledger is what is left after compaction. Without it, controllers re-dispatch merged slices. |

## References

- [author-prompt.md](author-prompt.md) — the author dispatch template.
- [reviewer-prompt.md](reviewer-prompt.md) — the slice reviewer template and gate list.
- [references/inventory.md](references/inventory.md) — inventory format, item IDs, the surveyor's brief.
- [references/slicing.md](references/slicing.md) — how to cut slices, with a worked example.
- [references/e2e-runs.md](references/e2e-runs.md) — automating a suite: the serial shared-surface phase, the run-green gate, and the coverage buckets.
- [references/fix-loop.md](references/fix-loop.md) — rounds, cap, escalation, parking.
- [references/final-review.md](references/final-review.md) — the merged-set review and finishing.
- [references/resuming.md](references/resuming.md) — picking up an existing ledger.
- `scripts/tc-workspace` — the run's directory and its file paths.
- `scripts/merge_slices.py` — renumber, dedupe, prove coverage (case authoring).
- `scripts/coverage_e2e.py` — case→spec coverage in buckets, run-report aware (E2E).
