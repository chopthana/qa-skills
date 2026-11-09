# The fix loop

Read this before **every** round, not once per run.

## What triggers it

A coverage verdict of ❌, an executability verdict of not approved, or any
finding the reviewer rated **blocking**. Minor findings do not open the loop —
they go to the ledger and are fixed in the merge wave if at all.

## A round

1. **Resume the author** that wrote the slice — the same agent, by its identity
   from the dispatch result. It still has its brief and its reasoning in
   context, so a resumed author fixes in one turn what a fresh one re-derives in
   five. Send it the review file's path and nothing else.
2. The author fixes its own file, in place, keeping its placeholder IDs. A split
   case becomes `{{S3}}-004` and `{{S3}}-004b` — never a renumber, because the
   review you are about to run points at the old numbers.
3. **Re-review, scoped.** Dispatch a reviewer on the same three paths with one
   added line: "Verify only these findings: `<list>`. New findings on cases you
   are not verifying go in a `## Noted` section, not in the verdict." A scoped
   re-review takes a cheap-to-mid model.
4. **Ledger line, every round:**
   `Slice <N> round <r>: <b> blocking in → <b'> out (<model>)`

## The cap

**Three rounds.** At the end of round 3, stop looping and **adjudicate** every
finding still open:

- **fix it yourself?** No. The controller never writes cases.
- **park it** — record `Parked: <finding> — <ruling> — <cost if wrong>` in the
  ledger, put the same sentence in the case's note field (resume the author for
  that one edit), and carry it into the final report's open questions.
- **re-cut it** — a slice that cannot converge in three rounds usually has a
  boundary through the middle of a behavior. Cut the unresolved part into a new
  slice with a sharper brief and dispatch a fresh author. This is the one exit
  that resets the count, and it is allowed once per slice.

## Escalation

- Round 2 on the same finding: keep the model, sharpen the instruction. A
  finding that survives a round is usually a brief that never carried the value
  the case needed — check the brief before blaming the author.
- Round 3: dispatch a **fresh** author one tier above the stuck one, with the
  brief plus the review file. Say explicitly what the previous author got wrong.

## The breaker

Two slices hitting the cap in one run means the inventory is the problem, not
the authors: items whose exact values were never found, or a conflict nobody
flagged. Stop dispatching, re-read the inventory's `not found in sources` rows,
and either go get those values or park them as a group with one ruling — then
resume the run.

## What never happens in the loop

- The controller editing a slice file.
- An unreviewed fix reaching the merge.
- A finding discarded because you disagree with it. You adjudicate only at the
  cap, and every adjudication is a ledger line.
- A re-review that wanders: new findings on untouched cases are noted, never
  looped on.
