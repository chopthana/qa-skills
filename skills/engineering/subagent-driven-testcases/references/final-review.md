# Final review and finishing

The slice reviews were task-scoped: each one saw one file. Nobody has yet read
the set the way a tester receives it — as one document, in order, start to
finish. That is this review, and it runs **once**.

## Dispatch

One reviewer, **most capable model**. Give it paths, never content:

- `<workspace>/merged.cases.json` — the whole set, real IDs
- `<workspace>/coverage.md` — the merge's claim/parked/duplicate report
- `<workspace>/inventory.md` — the obligations
- the intake block and the producer's rules, verbatim
- the deliverable path, if the producer's generator has already run

It writes `<workspace>/final-review.md` and returns counts only.

## What only this review can see

| Check | Why a slice reviewer could not do it |
| --- | --- |
| **Cross-slice duplicates** | Two authors wrote the same behavior from two briefs; each file looked fine alone |
| **One string, two spellings** | Slice 3 quotes "บันทึก", slice 5 quotes "บันทึกข้อมูล" for the same button. One of them is wrong and the set now disagrees with itself |
| **ID integrity** | Real IDs assigned at merge: unique, gapless, in the confirmed prefix, in slice order |
| **Coverage against the inventory** | The claim union, now that every slice has reported — including whether a parked item's reason still holds |
| **Order and readability** | A set a tester can work top to bottom, not one that jumps between screens |
| **Vocabulary drift** | Priority, status and test-type values pulled from different vocabularies by different authors |
| **The set as a day's work** | Thirty cases whose first six steps are identical is correct and fine; thirty cases that each re-seed the same data is a set nobody will run |

## The single fix wave

Collect every blocking finding, group them **by owning slice**, and send one
message per slice to that slice's author. One wave, one scoped re-review of the
whole merged file, then re-run the merge (IDs may shift — that is why renumbering
belongs to the merge and not to an author).

If the wave's re-review is not clean, the remaining findings are **parked with
rulings** and carried into the report. There is no second wave; a set that needs
one has a cutting or inventory problem that another round will not fix.

## Finishing

1. Build or rebuild the deliverable from `merged.cases.json` with the producer's
   own generator.
2. Verify the artefact exists and is openable — a workbook that no one can open,
   a YAML tree the repo's validator rejects, a spec file that does not parse is
   not a deliverable. Run the producer's validator if it has one.
3. Write the closing ledger block: deliverable path, case count, coverage
   numbers, parked list, and the slice table with its final states.
4. Report to the user (SKILL.md § 8).
5. Leave the workspace. Delete it only when the user says the deliverable is
   accepted — it is the only record of how the set was built, and the first
   thing to read when a reviewer asks "where did this case come from?".
